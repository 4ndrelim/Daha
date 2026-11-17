"""Points, levels, badges (PLAN.md §7.8)."""

from collections.abc import Iterable
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import settings
from app.core.geo import campus_today
from app.models import Item, PointsLedger, Review, Transaction, UserBadge
from app.services.notifications import notify

LEVELS: list[tuple[str, int]] = [
    ("New Neighbor", 0),
    ("Good Neighbor", 20),
    ("Helper", 60),
    ("Community Pillar", 150),
    ("Campus Legend", 400),
]

# code → (name, emoji, description)
BADGES: dict[str, tuple[str, str, str]] = {
    "first_share": ("First Share", "🌱", "Shared your first item"),
    "first_lend": ("First Lend", "🤝", "Lent something to a neighbor"),
    "generous": ("Generous", "🎁", "Gave away 3 things"),
    "request_hero": ("Request Hero", "🦸", "Answered 5 requests"),
    "trusted": ("Trusted", "⭐", "5+ reviews averaging 4.5 or higher"),
}

POINTS_ITEM_PUBLISHED = 2
ITEM_POINTS_DAILY_CAP = 10  # first 10 items per day earn points
POINTS_LEND_COMPLETED = 10
POINTS_GIVE_COMPLETED = 15
POINTS_EXCHANGE_COMPLETED = 10
POINTS_REQUEST_BONUS = 5
POINTS_BORROW_COMPLETED = 2
POINTS_GOOD_REVIEW = 2


def level_for(points: int) -> schemas.Level:
    idx = max(i for i, (_, minimum) in enumerate(LEVELS) if points >= minimum)
    name, minimum = LEVELS[idx]
    nxt = LEVELS[idx + 1] if idx + 1 < len(LEVELS) else None
    return schemas.Level(
        name=name,
        min_points=minimum,
        next_level_name=nxt[0] if nxt else None,
        next_level_points=nxt[1] if nxt else None,
    )


def points_by_user(db: Session, user_ids: Iterable[int]) -> dict[int, int]:
    ids = list(set(user_ids))
    if not ids:
        return {}
    rows = db.execute(
        select(PointsLedger.user_id, func.coalesce(func.sum(PointsLedger.delta), 0))
        .where(PointsLedger.user_id.in_(ids))
        .group_by(PointsLedger.user_id)
    ).all()
    out = dict.fromkeys(ids, 0)
    out.update({uid: int(total) for uid, total in rows})
    return out


def user_points(db: Session, user_id: int) -> int:
    return points_by_user(db, [user_id])[user_id]


def award(
    db: Session,
    user_id: int,
    delta: int,
    reason: str,
    ref_type: str | None = None,
    ref_id: int | None = None,
) -> None:
    db.add(
        PointsLedger(user_id=user_id, delta=delta, reason=reason, ref_type=ref_type, ref_id=ref_id)
    )
    db.flush()


def award_item_published(db: Session, user_id: int, item_id: int) -> int:
    """+2 for a published, non-private item; only the first 10 per campus day. Returns points."""
    tz = ZoneInfo(settings.campus_tz)
    day_start = datetime.combine(campus_today(), time.min, tzinfo=tz)
    already = db.scalar(
        select(func.count())
        .select_from(PointsLedger)
        .where(
            PointsLedger.user_id == user_id,
            PointsLedger.reason == "item_published",
            PointsLedger.created_at >= day_start,
        )
    )
    if (already or 0) >= ITEM_POINTS_DAILY_CAP:
        return 0
    award(db, user_id, POINTS_ITEM_PUBLISHED, "item_published", "item", item_id)
    return POINTS_ITEM_PUBLISHED


def _earned_codes(db: Session, user_id: int) -> set[str]:
    """Which badges the user qualifies for right now."""
    earned: set[str] = set()
    shared = db.scalar(
        select(func.count())
        .select_from(Item)
        .where(Item.owner_id == user_id, Item.visibility != "private")
    )
    if shared:
        earned.add("first_share")

    done = dict(
        db.execute(
            select(Transaction.kind, func.count())
            .where(Transaction.owner_id == user_id, Transaction.status == "completed")
            .group_by(Transaction.kind)
        ).all()
    )
    if done.get("lend", 0) >= 1:
        earned.add("first_lend")
    if done.get("give", 0) >= 3:
        earned.add("generous")

    fulfilled = db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.owner_id == user_id,
            Transaction.status == "completed",
            Transaction.request_id.is_not(None),
        )
    )
    if (fulfilled or 0) >= 5:
        earned.add("request_hero")

    count, avg = db.execute(
        select(func.count(), func.avg(Review.rating)).where(Review.reviewee_id == user_id)
    ).one()
    if count >= 5 and avg is not None and float(avg) >= 4.5:
        earned.add("trusted")
    return earned


def check_badges(db: Session, user_id: int, *, send_notifications: bool = True) -> list[str]:
    """Award any newly earned badges. Returns the new badge codes. The caller commits."""
    have = set(db.scalars(select(UserBadge.code).where(UserBadge.user_id == user_id)))
    new = sorted(_earned_codes(db, user_id) - have)
    for code in new:
        db.add(UserBadge(user_id=user_id, code=code))
        if send_notifications:
            name, emoji, description = BADGES[code]
            notify(db, user_id, "badge", f"New badge: {emoji} {name}", description, "/profile")
    db.flush()
    return new


def badges_for(db: Session, user_id: int) -> list[schemas.Badge]:
    rows = db.execute(
        select(UserBadge).where(UserBadge.user_id == user_id).order_by(UserBadge.earned_at)
    ).scalars()
    out = []
    for b in rows:
        if b.code not in BADGES:
            continue
        name, emoji, description = BADGES[b.code]
        out.append(
            schemas.Badge(
                code=b.code, name=name, emoji=emoji, description=description, earned_at=b.earned_at
            )
        )
    return out
