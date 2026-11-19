"""Model → schema converters, batched so list endpoints never do N+1 queries (PLAN.md §7.10)."""

from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import settings
from app.core.geo import distance_min
from app.models import (
    Community,
    ConversationParticipant,
    Item,
    ItemAudience,
    ItemImage,
    ItemRequest,
    Membership,
    Message,
    Notification,
    Place,
    RequestAudience,
    RequestMatch,
    Review,
    Transaction,
    Upload,
    User,
)
from app.services import points
from app.services.viewer import ViewerContext
from app.services.visibility import (
    DISCOVERY_ITEM_STATUSES,
    item_visible_clause,
    request_not_expired_clause,
    request_status,
    request_visible_clause,
)

ACTIVE_TX_STATUSES = ("requested", "offered", "accepted", "handed_off")


# ---------------------------------------------------------------- users
def dorms_by_user(db: Session, user_ids: Iterable[int]) -> dict[int, Community]:
    ids = list(set(user_ids))
    if not ids:
        return {}
    rows = db.execute(
        select(Membership.user_id, Community)
        .join(Community, Community.id == Membership.community_id)
        .where(Membership.user_id.in_(ids), Community.kind == "dorm")
    ).all()
    return {uid: dorm for uid, dorm in rows}


def ratings_by_user(db: Session, user_ids: Iterable[int]) -> dict[int, tuple[float | None, int]]:
    ids = list(set(user_ids))
    out: dict[int, tuple[float | None, int]] = dict.fromkeys(ids, (None, 0))
    if ids:
        rows = db.execute(
            select(Review.reviewee_id, func.avg(Review.rating), func.count())
            .where(Review.reviewee_id.in_(ids))
            .group_by(Review.reviewee_id)
        ).all()
        out.update({uid: (round(float(avg), 2), int(n)) for uid, avg, n in rows})
    return out


def user_refs(
    db: Session, user_ids: Iterable[int], dorms: dict[int, Community] | None = None
) -> dict[int, schemas.UserRef]:
    """UserRef for many users in four queries."""
    ids = list(set(user_ids))
    if not ids:
        return {}
    users = db.execute(select(User).where(User.id.in_(ids))).scalars().all()
    dorms = dorms if dorms is not None else dorms_by_user(db, ids)
    pts = points.points_by_user(db, ids)
    ratings = ratings_by_user(db, ids)
    return {
        u.id: schemas.UserRef(
            id=u.id,
            name=u.name,
            avatar_url=u.avatar_url,
            dorm_name=dorms[u.id].name if u.id in dorms else None,
            level_name=points.level_for(pts[u.id]).name,
            rating_avg=ratings[u.id][0],
        )
        for u in users
    }


def user_ref(db: Session, user: User) -> schemas.UserRef:
    return user_refs(db, [user.id])[user.id]


def user_public(db: Session, user: User) -> schemas.UserPublic:
    ref = user_ref(db, user)
    pts = points.user_points(db, user.id)
    completed = db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.status == "completed",
            or_(Transaction.owner_id == user.id, Transaction.borrower_id == user.id),
        )
    )
    shared = db.scalar(
        select(func.count())
        .select_from(Item)
        .where(Item.owner_id == user.id, Item.archived.is_(False), Item.visibility != "private")
    )
    return schemas.UserPublic(
        **ref.model_dump(),
        value_shared_usd=value_shared_usd(db, user.id),
        bio=user.bio,
        points=pts,
        level=points.level_for(pts),
        badges=points.badges_for(db, user.id),
        rating_count=ratings_by_user(db, [user.id])[user.id][1],
        completed_count=completed or 0,
        items_shared_count=shared or 0,
        joined_at=user.created_at,
    )


def value_shared_usd(db: Session, user_id: int) -> int | None:
    """What this user's shared items were worth, counting only completed exchanges they gave.

    Each completed transaction where the user is the owner adds that item's value once (a lamp
    lent 3 times counts 3 times). Items without a value add nothing. Null when the flag is off.
    Display only: never feeds points, karma or payments.
    """
    if not settings.item_value_enabled:
        return None
    total = db.scalar(
        select(func.coalesce(func.sum(Item.value_usd), 0))
        .select_from(Transaction)
        .join(Item, Item.id == Transaction.item_id)
        .where(Transaction.owner_id == user_id, Transaction.status == "completed")
    )
    return int(total or 0)


def unread_counts(db: Session, user_id: int) -> schemas.UnreadCounts:
    notifications = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    messages = db.scalar(
        select(func.count(Message.id))
        .join(
            ConversationParticipant,
            ConversationParticipant.conversation_id == Message.conversation_id,
        )
        .where(
            ConversationParticipant.user_id == user_id,
            Message.id > func.coalesce(ConversationParticipant.last_read_message_id, 0),
            Message.sender_id.is_distinct_from(user_id),
        )
    )
    return schemas.UnreadCounts(notifications=notifications or 0, messages=messages or 0)


def me_out(db: Session, user: User) -> schemas.Me:
    public = user_public(db, user)
    communities = (
        db.execute(
            select(Community)
            .join(Membership, Membership.community_id == Community.id)
            .where(Membership.user_id == user.id)
            .order_by(Community.name)
        )
        .scalars()
        .all()
    )
    dorm = next((c for c in communities if c.kind == "dorm"), None)
    unread = unread_counts(db, user.id)
    return schemas.Me(
        **public.model_dump(),
        email=user.email,
        dorm=community_ref(dorm) if dorm else None,
        groups=[community_ref(c) for c in communities if c.kind == "group"],
        walking_radius_min=user.walking_radius_min,
        onboarded=user.onboarded,
        match_suggestions=user.match_suggestions,
        unread_notifications=unread.notifications,
        unread_messages=unread.messages,
        item_value_enabled=settings.item_value_enabled,
    )


# ---------------------------------------------------------------- communities & places
def community_ref(c: Community) -> schemas.CommunityRef:
    return schemas.CommunityRef(id=c.id, slug=c.slug, name=c.name, kind=c.kind, emoji=c.emoji)


def communities_out(
    db: Session, communities: list[Community], viewer: ViewerContext
) -> list[schemas.Community]:
    """Communities with visibility-aware counts, in four queries."""
    if not communities:
        return []
    ids = [c.id for c in communities]
    member_counts = dict(
        db.execute(
            select(Membership.community_id, func.count())
            .where(Membership.community_id.in_(ids))
            .group_by(Membership.community_id)
        ).all()
    )
    item_counts = dict(
        db.execute(
            select(ItemAudience.community_id, func.count(Item.id.distinct()))
            .join(Item, Item.id == ItemAudience.item_id)
            .where(
                ItemAudience.community_id.in_(ids),
                item_visible_clause(viewer),
                Item.status.in_(DISCOVERY_ITEM_STATUSES),
            )
            .group_by(ItemAudience.community_id)
        ).all()
    )
    request_counts = dict(
        db.execute(
            select(RequestAudience.community_id, func.count(ItemRequest.id.distinct()))
            .join(ItemRequest, ItemRequest.id == RequestAudience.request_id)
            .where(
                RequestAudience.community_id.in_(ids),
                request_visible_clause(viewer),
                ItemRequest.status == "open",
                request_not_expired_clause(),
            )
            .group_by(RequestAudience.community_id)
        ).all()
    )
    my_roles = dict(
        db.execute(
            select(Membership.community_id, Membership.role).where(
                Membership.user_id == viewer.user_id, Membership.community_id.in_(ids)
            )
        ).all()
    )
    return [
        schemas.Community(
            **community_ref(c).model_dump(),
            description=c.description,
            group_type=c.group_type,
            is_private=c.is_private,
            member_count=member_counts.get(c.id, 0),
            item_count=item_counts.get(c.id, 0),
            open_request_count=request_counts.get(c.id, 0),
            is_member=c.id in my_roles,
            my_role=my_roles.get(c.id),
            join_code=c.join_code if my_roles.get(c.id) == "admin" else None,
            lat=c.lat,
            lng=c.lng,
            distance_min=distance_min(viewer.lat, viewer.lng, c.lat, c.lng),
        )
        for c in communities
    ]


def community_out(db: Session, c: Community, viewer: ViewerContext) -> schemas.Community:
    return communities_out(db, [c], viewer)[0]


def place_out(place: Place, viewer: ViewerContext) -> schemas.Place:
    return schemas.Place(
        id=place.id,
        name=place.name,
        lat=place.lat,
        lng=place.lng,
        description=place.description,
        distance_min=distance_min(viewer.lat, viewer.lng, place.lat, place.lng),
    )


def _places_by_id(db: Session, place_ids: Iterable[int | None]) -> dict[int, Place]:
    ids = {pid for pid in place_ids if pid is not None}
    if not ids:
        return {}
    return {p.id: p for p in db.execute(select(Place).where(Place.id.in_(ids))).scalars()}


def _community_label(visibility: str, audience: list[Community]) -> str:
    """ "Campus" | dorm name | first group name (+N) | "Only you"."""
    if visibility == "private":
        return "Only you"
    if visibility == "campus":
        return "Campus"
    if not audience:
        return "Dorm" if visibility == "dorm" else "Group"
    if visibility == "groups" and len(audience) > 1:
        return f"{audience[0].name} +{len(audience) - 1}"
    return audience[0].name


def _distance(place: Place | None, dorm: Community | None, viewer: ViewerContext) -> int | None:
    """Location = the pickup place if set, else the owner's (requester's) dorm (PLAN.md §7.9)."""
    spot = place or dorm
    if spot is None:
        return None
    return distance_min(viewer.lat, viewer.lng, spot.lat, spot.lng)


# ---------------------------------------------------------------- items
def item_cards(
    db: Session,
    items: list[Item],
    viewer: ViewerContext,
    scores: dict[int, tuple[float, str]] | None = None,
) -> list[schemas.ItemCard]:
    if not items:
        return []
    ids = [i.id for i in items]
    owner_ids = {i.owner_id for i in items}
    dorms = dorms_by_user(db, owner_ids)
    owners = user_refs(db, owner_ids, dorms)
    places = _places_by_id(db, (i.pickup_place_id for i in items))

    audiences: dict[int, list[Community]] = defaultdict(list)
    for item_id, community in db.execute(
        select(ItemAudience.item_id, Community)
        .join(Community, Community.id == ItemAudience.community_id)
        .where(ItemAudience.item_id.in_(ids))
        .order_by(Community.name)
    ).all():
        audiences[item_id].append(community)

    thumbs: dict[int, str] = {}
    for item_id, url in db.execute(
        select(ItemImage.item_id, Upload.url)
        .join(Upload, Upload.id == ItemImage.upload_id)
        .where(ItemImage.item_id.in_(ids))
        .order_by(ItemImage.position, ItemImage.id)
    ).all():
        thumbs.setdefault(item_id, url)

    scores = scores or {}
    out = []
    for i in items:
        dorm = dorms.get(i.owner_id)
        score, reason = scores.get(i.id, (None, None))
        out.append(
            schemas.ItemCard(
                id=i.id,
                name=i.name,
                category=i.category,
                transaction_type=i.transaction_type,
                status=i.status,
                condition=i.condition,
                quantity=i.quantity,
                thumbnail_url=thumbs.get(i.id),
                owner=owners[i.owner_id],
                visibility=i.visibility,
                community_label=_community_label(i.visibility, audiences.get(i.id, [])),
                distance_min=_distance(places.get(i.pickup_place_id), dorm, viewer),
                same_dorm=dorm is not None and dorm.id == viewer.dorm_id,
                created_at=i.created_at,
                match_score=score,
                match_reason=reason,
                value_usd=i.value_usd if settings.item_value_enabled else None,
            )
        )
    return out


def item_detail(db: Session, item: Item, viewer: ViewerContext) -> schemas.ItemDetail:
    card = item_cards(db, [item], viewer)[0]
    is_mine = item.owner_id == viewer.user_id

    images = [
        schemas.ItemImage(id=u.id, url=u.url, width=u.width, height=u.height)
        for u in db.execute(
            select(Upload)
            .join(ItemImage, ItemImage.upload_id == Upload.id)
            .where(ItemImage.item_id == item.id)
            .order_by(ItemImage.position, ItemImage.id)
        ).scalars()
    ]
    place = db.get(Place, item.pickup_place_id) if item.pickup_place_id else None

    # The viewer's own live transactions on this item (newest first).
    my_txs = (
        db.execute(
            select(Transaction)
            .where(
                Transaction.item_id == item.id,
                Transaction.status.in_(ACTIVE_TX_STATUSES),
                or_(
                    Transaction.owner_id == viewer.user_id,
                    Transaction.borrower_id == viewer.user_id,
                ),
            )
            .order_by(Transaction.id.desc())
        )
        .scalars()
        .all()
    )
    agreed = [t for t in my_txs if t.status in ("accepted", "handed_off")]
    active = (agreed or my_txs or [None])[0]
    can_see_note = is_mine or bool(agreed)

    group_ids: list[int] = []
    if is_mine and item.visibility == "groups":
        group_ids = list(
            db.scalars(
                select(ItemAudience.community_id)
                .where(ItemAudience.item_id == item.id)
                .order_by(ItemAudience.community_id)
            )
        )

    return schemas.ItemDetail(
        **card.model_dump(),
        description=item.description,
        images=images,
        max_lend_days=item.max_lend_days,
        available_from=item.available_from,
        available_until=item.available_until,
        pickup_place=place_out(place, viewer) if place else None,
        pickup_note=item.pickup_note if can_see_note else None,
        group_ids=group_ids,
        pings_enabled=item.pings_enabled,
        is_mine=is_mine,
        can_borrow=(
            not is_mine
            and not item.archived
            and item.status == "available"
            and item.visibility != "private"
            and not my_txs
        ),
        active_transaction_id=active.id if active else None,
        source=item.source,
        updated_at=item.updated_at,
    )


# ---------------------------------------------------------------- requests
def request_cards(
    db: Session, reqs: list[ItemRequest], viewer: ViewerContext
) -> list[schemas.RequestCard]:
    if not reqs:
        return []
    ids = [r.id for r in reqs]
    requester_ids = {r.requester_id for r in reqs}
    dorms = dorms_by_user(db, requester_ids)
    requesters = user_refs(db, requester_ids, dorms)
    places = _places_by_id(db, (r.pickup_place_id for r in reqs))

    audiences: dict[int, list[Community]] = defaultdict(list)
    for request_id, community in db.execute(
        select(RequestAudience.request_id, Community)
        .join(Community, Community.id == RequestAudience.community_id)
        .where(RequestAudience.request_id.in_(ids))
        .order_by(Community.name)
    ).all():
        audiences[request_id].append(community)

    offer_counts = dict(
        db.execute(
            select(Transaction.request_id, func.count())
            .where(
                Transaction.request_id.in_(ids),
                Transaction.initiated_by == "owner",
                Transaction.status.not_in(("declined", "cancelled")),
            )
            .group_by(Transaction.request_id)
        ).all()
    )
    match_counts = dict(
        db.execute(
            select(RequestMatch.request_id, func.count())
            .where(RequestMatch.request_id.in_(ids), RequestMatch.anonymous.is_(False))
            .group_by(RequestMatch.request_id)
        ).all()
    )

    out = []
    for r in reqs:
        dorm = dorms.get(r.requester_id)
        out.append(
            schemas.RequestCard(
                id=r.id,
                title=r.title,
                raw_text=r.raw_text,
                category=r.category,
                status=request_status(r),
                requester=requesters[r.requester_id],
                needed_from=r.needed_from,
                needed_until=r.needed_until,
                visibility=r.visibility,
                community_label=_community_label(r.visibility, audiences.get(r.id, [])),
                distance_min=_distance(places.get(r.pickup_place_id), dorm, viewer),
                same_dorm=dorm is not None and dorm.id == viewer.dorm_id,
                offer_count=offer_counts.get(r.id, 0),
                match_count=match_counts.get(r.id, 0),
                created_at=r.created_at,
            )
        )
    return out
