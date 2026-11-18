"""Request ↔ item matching (PLAN.md C3) + anonymous pings for private haves (C5).

score = 0.65·semantic + 0.15·keyword + 0.20·proximity, kept if ≥ MATCH_MIN_SCORE.
- Public matches: items the requester can see AND whose owner can see the request.
  Top 10 go to request_matches; the top 5 distinct owners get a `match` notification.
- Private matches (visibility='private', pings_enabled): only items whose owner can see the
  request. Stored with anonymous=true, NEVER returned to anyone; the top 5 distinct owners get
  an anonymous `private_match` ping (≤ 3 per person per 24 h, never twice per request).
Who was already notified is read from the notifications table, so re-matching after an edit
pings only new people.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, delete, exists, func, literal, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.discovery import config as cfg
from app.discovery.embeddings import EmbeddingUnavailable, embed_passages, provider_name
from app.discovery.scoring import loc_for, locations, proximity, reason
from app.discovery.texts import request_text
from app.models import (
    Item,
    ItemRequest,
    Membership,
    Notification,
    RequestAudience,
    RequestMatch,
    User,
)
from app.services.notifications import notify
from app.services.viewer import ViewerContext, build_viewer
from app.services.visibility import item_visible_clause, request_is_expired

log = logging.getLogger(__name__)
MATCH_STATUSES = ("available", "reserved")
MATCH_NOTIFY_PER_OWNER_PER_DAY = 10  # anti-spam for prolific lenders


@dataclass
class Scored:
    item: Item
    score: float
    reason: str


def pair_score(semantic: float, keyword: float, prox: float) -> float | None:
    """Total match score, or None if the pair isn't relevant enough (proximity never rescues it)."""
    w = cfg.MATCH_WEIGHTS
    rel_part = w["semantic"] * max(semantic, 0.0) + w["keyword"] * max(keyword, 0.0)
    relevance = rel_part / (w["semantic"] + w["keyword"])
    if relevance < cfg.MATCH_MIN_RELEVANCE[provider_name()]:
        return None
    total = rel_part + w["proximity"] * prox
    return round(total, 4) if total >= settings.match_min_score else None


def _owner_can_view(aud_ids: list[int]):
    if not aud_ids:
        return literal(False)
    return exists().where(Membership.user_id == Item.owner_id, Membership.community_id.in_(aud_ids))


def _keyword_expr(req_name):
    """All request words in the item (full-text), or a near-identical name (typo tolerance)."""
    tsq = func.plainto_tsquery("english", req_name)
    ws = func.word_similarity(req_name, Item.name)
    return func.greatest(
        case((ws >= 0.6, ws), else_=0.0),
        func.least(func.ts_rank_cd(Item.search_tsv, tsq) * 5.0, 1.0),
    )


def score_items(
    db: Session, viewer_for_distance: ViewerContext, req: ItemRequest, conds: list, limit: int = 200
) -> list[Scored]:
    """Score candidate items (already filtered by `conds`) against one request."""
    name = (req.item_name or req.title or req.raw_text or "")[:200]
    sem = (1 - Item.embedding.cosine_distance(req.embedding)) if req.embedding is not None else None
    kw = _keyword_expr(name)
    q = select(Item, sem if sem is not None else literal(0.0), kw).where(*conds)
    if sem is not None:
        q = q.where(or_(Item.embedding.is_not(None), kw > 0.3)).order_by(
            Item.embedding.cosine_distance(req.embedding)
        )
    else:
        q = q.where(kw > 0.3).order_by(kw.desc())
    rows = db.execute(q.limit(limit)).all()
    items = [r[0] for r in rows]
    dorms, places = locations(db, {i.owner_id for i in items}, {i.pickup_place_id for i in items})
    out = []
    for item, s, k in rows:
        loc = loc_for(viewer_for_distance, item.owner_id, item.pickup_place_id, dorms, places)
        score = pair_score(float(s or 0), float(k or 0), proximity(viewer_for_distance, loc))
        if score is not None:
            out.append(Scored(item, score, reason(viewer_for_distance, loc, item.status)))
    out.sort(key=lambda s: (-s.score, s.item.id))
    return out


def _already_notified(db: Session, request_id: int, types: tuple[str, ...]) -> set[int]:
    return set(
        db.scalars(
            select(Notification.user_id).where(
                Notification.type.in_(types),
                Notification.data["request_id"].astext == str(request_id),
            )
        )
    )


def _recent_count(db: Session, user_id: int, ntype: str) -> int:
    since = datetime.now(UTC) - timedelta(hours=24)
    return (
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.type == ntype,
                Notification.created_at >= since,
            )
        )
        or 0
    )


def _a(thing: str) -> str:
    return ("an " if thing[:1].lower() in "aeiou" else "a ") + thing


def match_request(request_id: int, *, notify_new_only: bool) -> None:
    with SessionLocal() as db:
        req = db.get(ItemRequest, request_id)
        if req is None:
            return
        try:
            _match(db, req)
        finally:
            req.matching_status = "done"
            db.commit()


def _match(db: Session, req: ItemRequest) -> None:
    try:
        req.embedding = embed_passages([request_text(req)])[0]
    except EmbeddingUnavailable as exc:
        log.warning("matching request %s without embeddings: %s", req.id, exc)
    db.flush()
    if req.status != "open" or request_is_expired(req):
        return

    requester = db.get(User, req.requester_id)
    rv = build_viewer(db, requester)
    aud_ids = list(
        db.scalars(select(RequestAudience.community_id).where(RequestAudience.request_id == req.id))
    )
    base = [
        Item.archived.is_(False),
        Item.status.in_(MATCH_STATUSES),
        Item.owner_id != req.requester_id,
        _owner_can_view(aud_ids),
    ]
    public = score_items(
        db, rv, req, [*base, Item.visibility != "private", item_visible_clause(rv)]
    )[: cfg.MATCH_TOP_N]
    private = score_items(
        db, rv, req, [*base, Item.visibility == "private", Item.pings_enabled.is_(True)]
    )[: cfg.MATCH_TOP_N]

    # Replace this request's match rows (notification history lives in `notifications`).
    db.execute(delete(RequestMatch).where(RequestMatch.request_id == req.id))
    rows: dict[int, RequestMatch] = {}
    for s, anonymous in [(s, False) for s in public] + [(s, True) for s in private]:
        rows[s.item.id] = RequestMatch(
            request_id=req.id,
            item_id=s.item.id,
            score=s.score,
            reason=s.reason,
            anonymous=anonymous,
        )
    db.add_all(rows.values())
    db.flush()

    if req.seed_key is not None:
        return  # seeded history gets matches but no notifications (keeps demo inboxes clean)
    dorm_name = rv.dorm_name or "your area"
    thing = (req.item_name or req.title).strip().rstrip("?.!").lower()[:60] or "something"
    notified = _already_notified(db, req.id, ("match", "private_match"))

    # --- public: top 5 distinct owners
    sent: set[int] = set()
    for s in public:
        owner = s.item.owner_id
        if owner in sent or owner in notified:
            if owner in notified:
                rows[s.item.id].notified = True
            continue
        if len(sent) >= cfg.MATCH_NOTIFY_OWNERS:
            break
        if _recent_count(db, owner, "match") >= MATCH_NOTIFY_PER_OWNER_PER_DAY:
            continue
        first = requester.name.split()[0] if requester.name else "Someone"
        notify(
            db,
            owner,
            "match",
            title=f"{first} needs {_a(thing)}",
            body=f"{first} in {dorm_name} needs {_a(thing)} — you have one: {s.item.name}",
            link=f"/requests/{req.id}",
            actor_id=requester.id,
            data={"request_id": req.id, "item_id": s.item.id},
        )
        rows[s.item.id].notified = True
        sent.add(owner)

    # --- private (anonymous): top 5 distinct owners, ≤ 3 per person per day
    pinged: set[int] = set()
    for s in private:
        owner = s.item.owner_id
        if owner in pinged or owner in sent or owner in notified:
            if owner in notified:
                rows[s.item.id].notified = True
            continue
        if len(pinged) >= cfg.MATCH_NOTIFY_OWNERS:
            break
        if _recent_count(db, owner, "private_match") >= cfg.PRIVATE_PINGS_PER_DAY:
            continue
        notify(
            db,
            owner,
            "private_match",
            title=f"Someone nearby needs {_a(thing)}",
            body=(
                f"Someone in {dorm_name} needs {_a(thing)}. You said you have one — want to "
                "help? They won't know it's you unless you offer."
            ),
            link=f"/requests/{req.id}?offer_item={s.item.id}",
            actor_id=None,
            data={"request_id": req.id, "item_id": s.item.id},
        )
        rows[s.item.id].notified = True
        pinged.add(owner)
    db.flush()


# ---------------------------------------------------------------- read side
def visible_matches(
    db: Session, req: ItemRequest, viewer: ViewerContext
) -> list[tuple[Item, float]]:
    rows = db.execute(
        select(Item, RequestMatch.score)
        .join(RequestMatch, RequestMatch.item_id == Item.id)
        .where(
            RequestMatch.request_id == req.id,
            RequestMatch.anonymous.is_(False),
            Item.visibility != "private",
            Item.status.in_(("available", "reserved", "borrowed")),
            item_visible_clause(viewer),
        )
        .order_by(RequestMatch.score.desc(), Item.id)
    ).all()
    return [(i, s) for i, s in rows]


def private_pinged_count(db: Session, request_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(RequestMatch)
            .where(
                RequestMatch.request_id == request_id,
                RequestMatch.anonymous.is_(True),
                RequestMatch.notified.is_(True),
            )
        )
        or 0
    )


def fulfillable(db: Session, viewer: ViewerContext, limit: int = cfg.FULFILLABLE_MAX):
    """Open requests by others (last 21 days) that my available items (public or private) match."""
    from app.services.visibility import request_not_expired_clause, request_visible_clause

    since = datetime.now(UTC) - timedelta(days=cfg.FULFILLABLE_DAYS)
    my_items = db.scalars(
        select(Item).where(
            Item.owner_id == viewer.user_id, Item.archived.is_(False), Item.status == "available"
        )
    ).all()
    if not my_items:
        return []
    reqs = db.scalars(
        select(ItemRequest)
        .where(
            request_visible_clause(viewer),
            ItemRequest.requester_id != viewer.user_id,
            ItemRequest.status == "open",
            request_not_expired_clause(),
            ItemRequest.created_at >= since,
        )
        .order_by(ItemRequest.created_at.desc())
        .limit(300)
    ).all()
    if not reqs:
        return []
    req_ids = [r.id for r in reqs]
    pairs = db.execute(
        select(
            ItemRequest.id,
            Item.id,
            func.coalesce(1 - Item.embedding.cosine_distance(ItemRequest.embedding), 0.0),
            _keyword_expr(func.coalesce(ItemRequest.item_name, ItemRequest.title)),
        )
        .select_from(ItemRequest)
        .join(
            Item,
            and_(
                Item.owner_id == viewer.user_id,
                Item.archived.is_(False),
                Item.status == "available",
            ),
        )
        .where(ItemRequest.id.in_(req_ids))
    ).all()
    by_id = {r.id: r for r in reqs}
    items_by_id = {i.id: i for i in my_items}
    dorms, places = locations(db, {r.requester_id for r in reqs}, {r.pickup_place_id for r in reqs})
    per_req: dict[int, list[tuple[Item, float]]] = {}
    best: dict[int, float] = {}
    for rid, iid, sem, kw in pairs:
        r = by_id[rid]
        loc = loc_for(viewer, r.requester_id, r.pickup_place_id, dorms, places)
        score = pair_score(float(sem or 0), float(kw or 0), proximity(viewer, loc))
        if score is None:
            continue
        per_req.setdefault(rid, []).append((items_by_id[iid], score))
        best[rid] = max(best.get(rid, 0), score)
    ranked = sorted(best, key=lambda rid: (-best[rid], -rid))[:limit]
    return [(by_id[rid], sorted(per_req[rid], key=lambda t: -t[1])) for rid in ranked]
