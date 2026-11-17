"""The one visibility rule (PLAN.md §7.4), used by details, search, feeds, and matching."""

from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.geo import campus_today
from app.models import Community, Item, ItemAudience, ItemRequest, Membership, RequestAudience, User
from app.services.viewer import ViewerContext

# Discovery (search, feeds, matches) only shows these; unavailable and archived are excluded.
DISCOVERY_ITEM_STATUSES = ("available", "reserved", "borrowed")
REQUEST_EXPIRY_DAYS = 14


def item_visible_clause(viewer: ViewerContext):
    """SQLAlchemy boolean clause for .where(): owner OR audience match; excludes archived."""
    # Aliased so the clause also works inside queries that already join item_audiences.
    aud = aliased(ItemAudience)
    in_audience = exists().where(aud.item_id == Item.id, aud.community_id.in_(viewer.community_ids))
    return and_(Item.archived.is_(False), or_(Item.owner_id == viewer.user_id, in_audience))


def request_visible_clause(viewer: ViewerContext):
    aud = aliased(RequestAudience)
    in_audience = exists().where(
        aud.request_id == ItemRequest.id, aud.community_id.in_(viewer.community_ids)
    )
    return or_(ItemRequest.requester_id == viewer.user_id, in_audience)


def user_can_view_request(db: Session, user_id: int, request_id: int) -> bool:
    req = db.get(ItemRequest, request_id)
    if req is None:
        return False
    if req.requester_id == user_id:
        return True
    return bool(
        db.scalar(
            select(func.count())
            .select_from(RequestAudience)
            .join(
                Membership,
                and_(
                    Membership.community_id == RequestAudience.community_id,
                    Membership.user_id == user_id,
                ),
            )
            .where(RequestAudience.request_id == request_id)
        )
    )


# ---------------------------------------------------------------- expiry (computed, not stored)
def request_is_expired(req: ItemRequest, today: date | None = None) -> bool:
    """`needed_until < today`, or no dates and older than 14 days. Only open requests expire."""
    if req.status != "open":
        return False
    today = today or campus_today()
    last_day = req.needed_until or req.needed_from
    if last_day is not None:
        return last_day < today
    return req.created_at < datetime.now(req.created_at.tzinfo) - timedelta(
        days=REQUEST_EXPIRY_DAYS
    )


def request_not_expired_clause(today: date | None = None):
    """SQL twin of request_is_expired(), for discovery queries on open requests."""
    today = today or campus_today()
    last_day = func.coalesce(ItemRequest.needed_until, ItemRequest.needed_from)
    return or_(
        last_day >= today,
        and_(
            last_day.is_(None),
            ItemRequest.created_at >= func.now() - timedelta(days=REQUEST_EXPIRY_DAYS),
        ),
    )


def request_status(req: ItemRequest, today: date | None = None) -> str:
    return "expired" if request_is_expired(req, today) else req.status


# ---------------------------------------------------------------- audiences on create/update
def user_dorm_id(db: Session, user_id: int) -> int | None:
    return db.scalar(
        select(Community.id)
        .join(Membership, Membership.community_id == Community.id)
        .where(Membership.user_id == user_id, Community.kind == "dorm")
    )


def campus_id(db: Session) -> int:
    cid = db.scalar(select(Community.id).where(Community.kind == "campus"))
    if cid is None:
        raise HTTPException(500, "Campus community is missing — run `make seed`")
    return cid


def resolve_audiences(
    db: Session, owner: User, visibility: str, group_ids: list[int] | None
) -> list[int]:
    """Community ids that may see an item or request (PLAN.md §7.4). Raises 400 on bad input."""
    if visibility == "campus":
        return [campus_id(db)]
    if visibility == "dorm":
        dorm_id = user_dorm_id(db, owner.id)
        if dorm_id is None:
            raise HTTPException(400, "Pick your dorm first to share with your dorm")
        return [dorm_id]
    if visibility == "groups":
        ids = list(dict.fromkeys(group_ids or []))
        if not ids:
            raise HTTPException(400, "Choose at least one group")
        mine = set(
            db.scalars(
                select(Community.id)
                .join(Membership, Membership.community_id == Community.id)
                .where(
                    Membership.user_id == owner.id,
                    Community.kind == "group",
                    Community.id.in_(ids),
                )
            )
        )
        if mine != set(ids):
            raise HTTPException(400, "You can only share with groups you belong to")
        return ids
    if visibility == "private":
        return []
    raise HTTPException(400, "Unknown visibility")
