"""Natural-language search (PLAN.md C2): hybrid vector + full-text + trigram, then ranking."""

import logging
import re
import time
from dataclasses import dataclass

from sqlalchemy import exists, false, func, literal, or_, select
from sqlalchemy.orm import Session

from app import schemas
from app.discovery import config as cfg
from app.discovery import embeddings
from app.discovery.query_parser import parse_query
from app.discovery.scoring import freshness, loc_for, locations, proximity, reason, tsquery_or
from app.models import Community, Item, ItemAudience, ItemRequest, Membership, SearchLog
from app.services import serializers
from app.services.viewer import ViewerContext
from app.services.visibility import (
    DISCOVERY_ITEM_STATUSES,
    item_visible_clause,
    request_not_expired_clause,
    request_visible_clause,
)

log = logging.getLogger(__name__)
MAX_LIMIT = 50


@dataclass
class Filters:
    category: str | None = None
    community_id: int | None = None
    scope: str | None = None
    max_walk_min: int | None = None
    transaction_type: str | None = None
    condition: str | None = None
    available_only: bool = True
    available_from: object = None
    available_until: object = None


def _query_vec(text: str) -> list[float] | None:
    try:
        return embeddings.embed_query(text)
    except embeddings.EmbeddingUnavailable as exc:
        log.warning("semantic search off: %s", exc)
        return None


def _in_my_dorm(owner_col, viewer: ViewerContext):
    if viewer.dorm_id is None:
        return false()
    return exists().where(
        Membership.user_id == owner_col, Membership.community_id == viewer.dorm_id
    )


def item_conditions(viewer: ViewerContext, f: Filters) -> list:
    conds = [
        item_visible_clause(viewer),
        Item.owner_id != viewer.user_id,
        Item.visibility != "private",
        Item.status.in_(("available",) if f.available_only else DISCOVERY_ITEM_STATUSES),
    ]
    if f.category:
        conds.append(Item.category == f.category)
    if f.community_id is not None:
        conds.append(
            exists().where(
                ItemAudience.item_id == Item.id, ItemAudience.community_id == f.community_id
            )
        )
    if f.scope == "dorm":
        conds.append(_in_my_dorm(Item.owner_id, viewer))
    if f.transaction_type:
        conds.append(Item.transaction_type == f.transaction_type)
    if f.condition:
        conds.append(Item.condition == f.condition)
    if f.available_until is not None:
        conds.append(or_(Item.available_from.is_(None), Item.available_from <= f.available_until))
    if f.available_from is not None:
        conds.append(or_(Item.available_until.is_(None), Item.available_until >= f.available_from))
    return conds


def request_conditions(viewer: ViewerContext, f: Filters) -> list:
    conds = [
        request_visible_clause(viewer),
        ItemRequest.requester_id != viewer.user_id,
        ItemRequest.status == "open",
        request_not_expired_clause(),
    ]
    if f.category:
        conds.append(ItemRequest.category == f.category)
    if f.scope == "dorm":
        conds.append(_in_my_dorm(ItemRequest.requester_id, viewer))
    return conds


def _candidates(db, model, conds, text: str, vec, name_col) -> set[int]:
    ids: set[int] = set()
    if vec is not None:
        ids |= set(
            db.scalars(
                select(model.id)
                .where(*conds, model.embedding.is_not(None))
                .order_by(model.embedding.cosine_distance(vec))
                .limit(cfg.CANDIDATES_VECTOR)
            )
        )
    tsq = tsquery_or(text)
    if tsq is not None:
        ids |= set(
            db.scalars(
                select(model.id)
                .where(*conds, model.search_tsv.op("@@")(tsq))
                .order_by(func.ts_rank_cd(model.search_tsv, tsq).desc())
                .limit(cfg.CANDIDATES_FTS)
            )
        )
    # `<%` is word_similarity ≥ pg_trgm.word_similarity_threshold (0.6 = TRGM_MIN) and can use
    # the trigram GIN index on name, unlike calling word_similarity() on every row.
    ids |= set(
        db.scalars(
            select(model.id)
            .where(*conds, literal(text).op("<%")(name_col))
            .order_by(func.word_similarity(text, name_col).desc())
            .limit(cfg.CANDIDATES_TRGM)
        )
    )
    return ids


def _signals(db, model, ids, text, vec, name_col):
    """id → (row, semantic, keyword) for the candidate ids."""
    if not ids:
        return {}
    tsq = tsquery_or(text)
    sem = (1 - model.embedding.cosine_distance(vec)) if vec is not None else None
    cols = [
        model,
        sem if sem is not None else literal(0.0),
        func.ts_rank_cd(model.search_tsv, tsq) if tsq is not None else literal(0.0),
        func.word_similarity(text, name_col),
    ]
    rows = db.execute(select(*cols).where(model.id.in_(ids))).all()
    max_rank = max((float(r[2] or 0) for r in rows), default=0.0) or 1.0
    out = {}
    for row, s, rank, trgm in rows:
        semantic = max(float(s or 0.0), 0.0)
        kw_trgm = float(trgm or 0.0) if (trgm or 0) >= cfg.TRGM_MIN else 0.0
        keyword = max(float(rank or 0.0) / max_rank, kw_trgm)
        out[row.id] = (row, semantic, keyword)
    return out


def semantic_gate(signals: dict) -> float:
    """Minimum semantic score for a candidate with no keyword overlap."""
    provider = embeddings.provider_name()
    top = max((sem for _, sem, _ in signals.values()), default=0.0)
    return max(cfg.SEMANTIC_FLOOR[provider], top - cfg.SEMANTIC_MARGIN[provider])


def _weights(near_me: bool) -> dict[str, float]:
    w = dict(cfg.SEARCH_WEIGHTS)
    if near_me:
        w["proximity"] = cfg.NEAR_ME_PROXIMITY_WEIGHT
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def _walk_limit(viewer: ViewerContext, f: Filters, near_me: bool) -> int | None:
    if f.max_walk_min is not None:
        return f.max_walk_min
    if near_me and viewer.lat is not None:
        return viewer.walking_radius_min
    return None


def rank_items(
    db: Session,
    viewer: ViewerContext,
    parsed: schemas.ParsedQuery,
    f: Filters,
    explicit_category: bool,
    explicit_type: bool,
) -> list[tuple[Item, float, str]]:
    text = parsed.text
    conds = item_conditions(viewer, f)
    walk_limit = _walk_limit(viewer, f, parsed.near_me)
    if not text:
        rows = db.scalars(
            select(Item).where(*conds).order_by(Item.created_at.desc()).limit(cfg.BROWSE_POOL)
        ).all()
        signals = {r.id: (r, 0.0, 0.0) for r in rows}
    else:
        vec = _query_vec(text)
        ids = _candidates(db, Item, conds, text, vec, Item.name)
        signals = _signals(db, Item, ids, text, vec, Item.name)

    floor = semantic_gate(signals)
    rows = [s[0] for s in signals.values()]
    dorms, places = locations(db, {r.owner_id for r in rows}, {r.pickup_place_id for r in rows})
    w = _weights(parsed.near_me)
    ranked = []
    for item, semantic, keyword in signals.values():
        loc = loc_for(viewer, item.owner_id, item.pickup_place_id, dorms, places)
        if walk_limit is not None and (loc.distance is None or loc.distance > walk_limit):
            if not (viewer.dorm_id is not None and loc.dorm_id == viewer.dorm_id):
                continue
        prox = proximity(viewer, loc)
        if not text:
            # browse: same dorm first, then distance, then newest
            score = (1.0 if prox == 1.0 else 0.0) * 10 + prox + 0.001 * freshness(item.created_at)
        else:
            if keyword <= 0 and semantic < floor:
                continue
            score = (
                w["semantic"] * semantic
                + w["keyword"] * keyword
                + w["proximity"] * prox
                + w["freshness"] * freshness(item.created_at)
            )
            if parsed.category and not explicit_category and item.category == parsed.category:
                score += cfg.PARSED_CATEGORY_BOOST
            if parsed.transaction_type and not explicit_type:
                if item.transaction_type == parsed.transaction_type:
                    score += cfg.PARSED_TYPE_BOOST
            score *= cfg.AVAILABILITY_FACTOR.get(item.status, 0.3)
        ranked.append((item, round(score, 4), reason(viewer, loc, item.status)))
    ranked.sort(key=lambda t: (-t[1], -t[0].id))
    return ranked


def rank_requests(
    db: Session, viewer: ViewerContext, parsed: schemas.ParsedQuery, f: Filters
) -> list[ItemRequest]:
    text = parsed.text
    conds = request_conditions(viewer, f)
    if not text:
        rows = db.scalars(
            select(ItemRequest).where(*conds).order_by(ItemRequest.created_at.desc()).limit(200)
        ).all()
        signals = {r.id: (r, 0.0, 0.0) for r in rows}
    else:
        vec = _query_vec(text)
        ids = _candidates(db, ItemRequest, conds, text, vec, ItemRequest.title)
        signals = _signals(db, ItemRequest, ids, text, vec, ItemRequest.title)
    rows = [s[0] for s in signals.values()]
    dorms, places = locations(db, {r.requester_id for r in rows}, {r.pickup_place_id for r in rows})
    floor = semantic_gate(signals)
    w = _weights(parsed.near_me)
    scored = []
    for req, semantic, keyword in signals.values():
        loc = loc_for(viewer, req.requester_id, req.pickup_place_id, dorms, places)
        prox = proximity(viewer, loc)
        if not text:
            score = (10 if prox == 1.0 else 0) + prox + 0.001 * freshness(req.created_at)
        else:
            if keyword <= 0 and semantic < floor:
                continue
            score = (
                w["semantic"] * semantic
                + w["keyword"] * keyword
                + w["proximity"] * prox
                + w["freshness"] * freshness(req.created_at)
            )
        scored.append((req, score))
    scored.sort(key=lambda t: (-t[1], -t[0].id))
    return [r for r, _ in scored]


def search_communities(db: Session, viewer: ViewerContext, text: str) -> list[schemas.Community]:
    text = text.strip()
    if len(text) < 2:
        return []
    pattern = "%" + re.sub(r"([%_\\])", r"\\\1", text) + "%"
    rows = db.scalars(
        select(Community)
        .where(Community.name.ilike(pattern, escape="\\"))
        .order_by(Community.kind, Community.name)
        .limit(5)
    ).all()
    return serializers.communities_out(db, list(rows), viewer)


def search(
    db: Session,
    viewer: ViewerContext,
    *,
    q: str,
    kind: str,
    filters: Filters,
    offset: int,
    limit: int,
) -> schemas.SearchResponse:
    start = time.monotonic()
    offset, limit = max(offset, 0), min(max(limit, 1), MAX_LIMIT)
    parsed = parse_query(q)
    explicit_category = filters.category is not None
    explicit_type = filters.transaction_type is not None
    # Explicit params override what was parsed; parsed category/type stay soft boosts.
    if filters.scope is None:
        filters.scope = parsed.scope
    if filters.transaction_type is None and parsed.transaction_type == "give":
        filters.transaction_type = "give"  # "free …" means free; borrow/swap stay soft boosts
    if filters.available_from is None and filters.available_until is None:
        filters.available_from, filters.available_until = (
            parsed.available_from,
            parsed.available_until,
        )

    items: list[schemas.ItemCard] = []
    requests: list[schemas.RequestCard] = []
    communities: list[schemas.Community] = []
    next_offset = None
    result_ids: list[int] = []

    if kind in ("all", "items"):
        ranked = rank_items(db, viewer, parsed, filters, explicit_category, explicit_type)
        page = ranked[offset : offset + limit]
        result_ids = [i.id for i, _, _ in page]
        browse = not parsed.text
        items = serializers.item_cards(
            db,
            [i for i, _, _ in page],
            viewer,
            {i.id: (None if browse else s, r) for i, s, r in page},
        )
        next_offset = offset + limit if len(ranked) > offset + limit else None
    if kind in ("all", "requests"):
        reqs = rank_requests(db, viewer, parsed, filters)
        if kind == "requests":
            page_r = reqs[offset : offset + limit]
            next_offset = offset + limit if len(reqs) > offset + limit else None
        else:
            page_r = reqs[:5] if offset == 0 else []
        requests = serializers.request_cards(db, page_r, viewer)
    if kind in ("all", "communities") and offset == 0:
        communities = search_communities(db, viewer, parsed.text or q)

    latency = int((time.monotonic() - start) * 1000)
    try:
        db.add(
            SearchLog(
                user_id=viewer.user_id,
                raw_query=(q or "")[:500],
                parsed=parsed.model_dump(mode="json"),
                filters={k: str(v) if v is not None else None for k, v in vars(filters).items()}
                | {"kind": kind, "offset": offset, "limit": limit},
                result_item_ids=result_ids,
                latency_ms=latency,
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 — logging must never break search
        db.rollback()
        log.exception("search log failed")
    return schemas.SearchResponse(
        parsed=parsed,
        items=items,
        requests=requests,
        communities=communities,
        next_offset=next_offset,
    )
