"""Who is looking: the viewer's dorm, location, and communities (PLAN.md §7.10)."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Community, Membership, User


@dataclass(frozen=True)
class ViewerContext:
    user_id: int
    dorm_id: int | None
    dorm_name: str | None
    lat: float | None
    lng: float | None
    community_ids: frozenset[int]  # campus + dorm + groups
    walking_radius_min: int


def build_viewer(db: Session, user: User) -> ViewerContext:
    rows = (
        db.execute(
            select(Community)
            .join(Membership, Membership.community_id == Community.id)
            .where(Membership.user_id == user.id)
        )
        .scalars()
        .all()
    )
    dorm = next((c for c in rows if c.kind == "dorm"), None)
    return ViewerContext(
        user_id=user.id,
        dorm_id=dorm.id if dorm else None,
        dorm_name=dorm.name if dorm else None,
        lat=dorm.lat if dorm else None,
        lng=dorm.lng if dorm else None,
        community_ids=frozenset(c.id for c in rows),
        walking_radius_min=user.walking_radius_min,
    )
