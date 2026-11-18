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
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, delete, exists, func, literal, literal_column, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.discovery import config as cfg
from app.discovery.embeddings import EmbeddingUnavailable, embed_passages, provider_name
from app.discovery.scoring import loc_for, locations, proximity, reason
from app.discovery.texts import request_text
from app.models import (
    Item,
    ItemAudience,
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


def _diverse(scored: list[Scored]) -> list[Scored]:
    """At most MATCH_PER_OWNER rows per owner, MATCH_STORE_N in total (already score-sorted)."""
    per_owner: dict[int, int] = {}
    out = []
    for s in scored:
        n = per_owner.get(s.item.owner_id, 0)
        if n < cfg.MATCH_PER_OWNER:
            per_owner[s.item.owner_id] = n + 1
            out.append(s)
        if len(out) >= cfg.MATCH_STORE_N:
            break
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


def short_dorm(name: str | None) -> str:
    """'Florence Moore Hall (FloMo)' → 'FloMo'; None → 'your area'."""
    if not name:
        return "your area"
    m = re.search(r"\(([^)]+)\)", name)
    return m.group(1) if m else name


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
    public = _diverse(
        score_items(db, rv, req, [*base, Item.visibility != "private", item_visible_clause(rv)])
    )
    private = _diverse(
        score_items(
            db, rv, req, [*base, Item.visibility == "private", Item.pings_enabled.is_(True)]
        )
    )

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
    dorm_name = short_dorm(rv.dorm_name)
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
        .limit(cfg.MATCH_TOP_N)
    ).all()
    return [(i, s) for i, s in rows]


def private_pinged_count(db: Session, request_id: int) -> int:
    """How many people were quietly pinged for this request (from the notifications sent)."""
    return (
        db.scalar(
            select(func.count(func.distinct(Notification.user_id))).where(
                Notification.type == "private_match",
                Notification.data["request_id"].astext == str(request_id),
            )
        )
        or 0
    )


def reverse_match_item(item_id: int) -> None:
    """Score one saved item against open requests and upsert request_matches (no notifications).

    Keeps "You could help" fresh for items added after a request was posted, without scoring
    every item × request pair on each home-feed load.
    """
    from sqlalchemy.dialects.postgresql import insert

    from app.services.visibility import request_not_expired_clause

    with SessionLocal() as db:
        item = db.get(Item, item_id)
        if item is None:
            return
        # Keep rows that already produced a notification (history); refresh the rest.
        db.execute(
            delete(RequestMatch).where(
                RequestMatch.item_id == item.id, RequestMatch.notified.is_(False)
            )
        )
        live = (
            not item.archived
            and item.status in MATCH_STATUSES
            and (item.visibility != "private" or item.pings_enabled)
        )
        if not live:
            db.commit()
            return
        owner_can_view = exists().where(
            RequestAudience.request_id == ItemRequest.id,
            RequestAudience.community_id.in_(
                select(Membership.community_id).where(Membership.user_id == item.owner_id)
            ),
        )
        conds = [
            ItemRequest.status == "open",
            request_not_expired_clause(),
            ItemRequest.requester_id != item.owner_id,
            owner_can_view,
        ]
        if item.visibility != "private":
            item_aud = select(ItemAudience.community_id).where(ItemAudience.item_id == item.id)
            conds.append(
                exists().where(
                    Membership.user_id == ItemRequest.requester_id,
                    Membership.community_id.in_(item_aud),
                )
            )
        req_name = func.coalesce(ItemRequest.item_name, ItemRequest.title)
        tsq = func.plainto_tsquery("english", req_name)
        ws = func.word_similarity(req_name, item.name)
        item_tsv = func.setweight(
            func.to_tsvector("english", literal(item.name)), literal_column("'A'")
        ).op("||")(
            func.setweight(
                func.to_tsvector("english", literal(item.description or "")), literal_column("'B'")
            )
        )
        kw = func.greatest(
            case((ws >= 0.6, ws), else_=0.0),
            func.least(func.ts_rank_cd(item_tsv, tsq) * 5.0, 1.0),
        )
        if item.embedding is not None:
            sem = 1 - ItemRequest.embedding.cosine_distance(item.embedding)
            q = (
                select(ItemRequest, sem, kw)
                .where(*conds, ItemRequest.embedding.is_not(None))
                .order_by(ItemRequest.embedding.cosine_distance(item.embedding))
            )
        else:
            q = select(ItemRequest, literal(0.0), kw).where(*conds)
        rows = db.execute(q.limit(100)).all()
        dorms, places = locations(db, {item.owner_id}, {item.pickup_place_id})
        viewers: dict[int, ViewerContext] = {}
        values = []
        for req, s, k in rows:
            if req.requester_id not in viewers:
                viewers[req.requester_id] = build_viewer(db, db.get(User, req.requester_id))
            rviewer = viewers[req.requester_id]
            loc = loc_for(rviewer, item.owner_id, item.pickup_place_id, dorms, places)
            score = pair_score(float(s or 0), float(k or 0), proximity(rviewer, loc))
            if score is not None:
                values.append(
                    {
                        "request_id": req.id,
                        "item_id": item.id,
                        "score": score,
                        "reason": reason(rviewer, loc, item.status),
                        "anonymous": item.visibility == "private",
                    }
                )
        if values:
            stmt = insert(RequestMatch).values(values)
            db.execute(
                stmt.on_conflict_do_update(
                    index_elements=["request_id", "item_id"],
                    set_={
                        "score": stmt.excluded.score,
                        "reason": stmt.excluded.reason,
                        "anonymous": stmt.excluded.anonymous,
                    },
                )
            )
        db.commit()


def fulfillable(db: Session, viewer: ViewerContext, limit: int = cfg.FULFILLABLE_MAX):
    """Open requests by others (last 21 days) that my available items (public or private) match.

    Reads request_matches, which is written both when a request is posted (match_request) and
    when an item is saved (reverse_match_item) — so this is an indexed lookup, not a big join.
    """
    from app.services.visibility import request_not_expired_clause, request_visible_clause

    since = datetime.now(UTC) - timedelta(days=cfg.FULFILLABLE_DAYS)
    rows = db.execute(
        select(ItemRequest, Item, RequestMatch.score)
        .join(RequestMatch, RequestMatch.request_id == ItemRequest.id)
        .join(Item, Item.id == RequestMatch.item_id)
        .where(
            Item.owner_id == viewer.user_id,
            Item.archived.is_(False),
            Item.status == "available",
            request_visible_clause(viewer),
            ItemRequest.requester_id != viewer.user_id,
            ItemRequest.status == "open",
            request_not_expired_clause(),
            ItemRequest.created_at >= since,
        )
        .order_by(RequestMatch.score.desc())
        .limit(500)
    ).all()
    per_req: dict[int, list[tuple[Item, float]]] = {}
    by_id: dict[int, ItemRequest] = {}
    for req, item, score in rows:
        by_id[req.id] = req
        per_req.setdefault(req.id, []).append((item, score))
    ranked = sorted(per_req, key=lambda rid: (-per_req[rid][0][1], -rid))[:limit]
    return [(by_id[rid], per_req[rid][:5]) for rid in ranked]
