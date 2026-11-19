"""Home feed and community channel feed (PLAN.md C3)."""

from fastapi import HTTPException
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app import schemas
from app.discovery import matching
from app.discovery.scoring import loc_for, locations
from app.models import Community, Item, ItemAudience, ItemRequest, Membership, RequestAudience
from app.services import serializers, value_exchange
from app.services.communities import get_community
from app.services.viewer import ViewerContext
from app.services.visibility import (
    DISCOVERY_ITEM_STATUSES,
    item_visible_clause,
    request_not_expired_clause,
    request_visible_clause,
)

NEW_NEARBY_MAX = 12
NEW_NEARBY_MIN = 6
REQUESTS_NEARBY_MAX = 10
YOU_CAN_HELP_MAX = 5
MAX_LIMIT = 50


def _open_requests_conds(viewer: ViewerContext) -> list:
    return [
        request_visible_clause(viewer),
        ItemRequest.status == "open",
        request_not_expired_clause(),
    ]


def _discoverable_items(viewer: ViewerContext) -> list:
    return [
        item_visible_clause(viewer),
        Item.visibility != "private",
        Item.status.in_(DISCOVERY_ITEM_STATUSES),
    ]


def fulfillable_out(
    db: Session, viewer: ViewerContext, limit: int
) -> list[schemas.FulfillableRequest]:
    pairs = matching.fulfillable(db, viewer, limit)
    if not pairs:
        return []
    cards = {c.id: c for c in serializers.request_cards(db, [r for r, _ in pairs], viewer)}
    out = []
    for req, items in pairs:
        scores = {}
        for item, score in items:
            label = "Only you · they won't see it" if item.visibility == "private" else "Yours"
            scores[item.id] = (score, label)
        out.append(
            schemas.FulfillableRequest(
                request=cards[req.id],
                my_matching_items=serializers.item_cards(db, [i for i, _ in items], viewer, scores),
            )
        )
    return out


def home_feed(db: Session, viewer: ViewerContext) -> schemas.HomeFeed:
    dorm = db.get(Community, viewer.dorm_id) if viewer.dorm_id else None
    my_item_count = (
        db.scalar(
            select(func.count())
            .select_from(Item)
            .where(
                Item.owner_id == viewer.user_id,
                Item.archived.is_(False),
                Item.visibility != "private",
            )
        )
        or 0
    )

    # Requests near you: same dorm first, then distance, then newest.
    reqs = db.scalars(
        select(ItemRequest)
        .where(*_open_requests_conds(viewer), ItemRequest.requester_id != viewer.user_id)
        .order_by(ItemRequest.created_at.desc())
        .limit(200)
    ).all()
    dorms, places = locations(db, {r.requester_id for r in reqs}, {r.pickup_place_id for r in reqs})

    def req_key(r):
        loc = loc_for(viewer, r.requester_id, r.pickup_place_id, dorms, places)
        same = viewer.dorm_id is not None and loc.dorm_id == viewer.dorm_id
        return (
            0 if same else 1,
            loc.distance if loc.distance is not None else 999,
            -r.created_at.timestamp(),
        )

    requests_nearby = sorted(reqs, key=req_key)[:REQUESTS_NEARBY_MAX]

    # New near you: available, not mine; same dorm first, within radius, newest; else campus.
    items = db.scalars(
        select(Item)
        .where(
            *_discoverable_items(viewer),
            Item.owner_id != viewer.user_id,
            Item.status == "available",
        )
        .order_by(Item.created_at.desc())
        .limit(300)
    ).all()
    idorms, iplaces = locations(db, {i.owner_id for i in items}, {i.pickup_place_id for i in items})
    near, far = [], []
    for it in items:
        loc = loc_for(viewer, it.owner_id, it.pickup_place_id, idorms, iplaces)
        same = viewer.dorm_id is not None and loc.dorm_id == viewer.dorm_id
        within = loc.distance is not None and loc.distance <= viewer.walking_radius_min
        (near if same or within else far).append((0 if same else 1, it))
    near.sort(key=lambda t: (t[0], -t[1].created_at.timestamp()))
    chosen = [it for _, it in near][:NEW_NEARBY_MAX]
    if len(chosen) < NEW_NEARBY_MIN:
        chosen += [it for _, it in far][: NEW_NEARBY_MAX - len(chosen)]

    stats = schemas.HomeFeedStats(
        dorm_items=_dorm_items(db, viewer),
        campus_items=db.scalar(
            select(func.count()).select_from(Item).where(*_discoverable_items(viewer))
        )
        or 0,
        open_requests=db.scalar(
            select(func.count()).select_from(ItemRequest).where(*_open_requests_conds(viewer))
        )
        or 0,
        dorm_value_shared_month_usd=value_exchange.dorm_shared_this_month(db, viewer.dorm_id),
    )
    return schemas.HomeFeed(
        dorm=serializers.community_ref(dorm) if dorm else None,
        my_item_count=my_item_count,
        show_scan_cta=my_item_count < 3,
        you_can_help=fulfillable_out(db, viewer, YOU_CAN_HELP_MAX),
        requests_nearby=serializers.request_cards(db, requests_nearby, viewer),
        new_nearby=serializers.item_cards(db, chosen, viewer),
        stats=stats,
    )


def _dorm_items(db: Session, viewer: ViewerContext) -> int:
    if viewer.dorm_id is None:
        return 0
    return (
        db.scalar(
            select(func.count())
            .select_from(Item)
            .where(
                *_discoverable_items(viewer),
                exists().where(
                    Membership.user_id == Item.owner_id, Membership.community_id == viewer.dorm_id
                ),
            )
        )
        or 0
    )


def community_feed(
    db: Session, viewer: ViewerContext, community_id: int, kind: str, offset: int, limit: int
) -> schemas.Page[schemas.FeedEntry]:
    """Entries shared with the community, + campus-visible entries by its members, newest first."""
    community = get_community(db, community_id)
    if (
        community.kind == "group"
        and community.is_private
        and community.id not in viewer.community_ids
    ):
        raise HTTPException(404, "Community not found")
    offset, limit = max(offset, 0), min(max(limit, 1), MAX_LIMIT)
    window = offset + limit + 1
    by_campus = community.kind == "campus"

    def member(user_col):
        return exists().where(
            Membership.community_id == community.id, Membership.user_id == user_col
        )

    items: list[Item] = []
    reqs: list[ItemRequest] = []
    if kind in ("all", "items"):
        shared = exists().where(
            ItemAudience.item_id == Item.id, ItemAudience.community_id == community.id
        )
        where = (
            shared
            if by_campus
            else or_(shared, (Item.visibility == "campus") & member(Item.owner_id))
        )
        items = db.scalars(
            select(Item)
            .where(*_discoverable_items(viewer), where)
            .order_by(Item.created_at.desc(), Item.id.desc())
            .limit(window)
        ).all()
    if kind in ("all", "requests"):
        shared = exists().where(
            RequestAudience.request_id == ItemRequest.id,
            RequestAudience.community_id == community.id,
        )
        where = (
            shared
            if by_campus
            else or_(
                shared, (ItemRequest.visibility == "campus") & member(ItemRequest.requester_id)
            )
        )
        reqs = db.scalars(
            select(ItemRequest)
            .where(
                request_visible_clause(viewer),
                ItemRequest.status.in_(("open", "in_progress", "fulfilled")),
                or_(ItemRequest.status != "open", request_not_expired_clause()),
                where,
            )
            .order_by(ItemRequest.created_at.desc(), ItemRequest.id.desc())
            .limit(window)
        ).all()
    merged = sorted(
        [(i.created_at, "item", i) for i in items] + [(r.created_at, "request", r) for r in reqs],
        key=lambda t: (t[0], t[2].id),
        reverse=True,
    )
    page = merged[offset : offset + limit]
    icards = {
        c.id: c for c in serializers.item_cards(db, [x for _, k, x in page if k == "item"], viewer)
    }
    rcards = {
        c.id: c
        for c in serializers.request_cards(db, [x for _, k, x in page if k == "request"], viewer)
    }
    out: list = []
    for created, k, x in page:
        if k == "item":
            out.append(schemas.FeedEntryItem(created_at=created, item=icards[x.id]))
        else:
            out.append(schemas.FeedEntryRequest(created_at=created, request=rcards[x.id]))
    return schemas.Page[schemas.FeedEntry](
        items=out, next_offset=offset + limit if len(merged) > offset + limit else None
    )
