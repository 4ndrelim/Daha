"""Community membership rules: everyone is in campus, at most one dorm, any number of groups."""

import re
import secrets

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import schemas
from app.models import Community, Membership, User
from app.services.visibility import campus_id

JOIN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


def get_community(db: Session, id_or_slug: str | int) -> Community:
    ref = str(id_or_slug)
    if ref.isdigit():
        c = db.get(Community, int(ref))
    else:
        c = db.execute(select(Community).where(Community.slug == ref)).scalar_one_or_none()
    if c is None:
        raise HTTPException(404, "Community not found")
    return c


def membership(db: Session, user_id: int, community_id: int) -> Membership | None:
    return db.get(Membership, (user_id, community_id))


def ensure_campus_membership(db: Session, user_id: int) -> None:
    cid = campus_id(db)
    if membership(db, user_id, cid) is None:
        db.add(Membership(user_id=user_id, community_id=cid))
        db.flush()


def set_dorm(db: Session, user_id: int, dorm_id: int) -> None:
    """Switch the user's dorm: ≤ 1 dorm membership at any time."""
    dorm = db.get(Community, dorm_id)
    if dorm is None or dorm.kind != "dorm":
        raise HTTPException(400, "That dorm doesn't exist")
    old_dorm_ids = select(Community.id).where(Community.kind == "dorm", Community.id != dorm_id)
    db.execute(
        delete(Membership).where(
            Membership.user_id == user_id, Membership.community_id.in_(old_dorm_ids)
        )
    )
    if membership(db, user_id, dorm_id) is None:
        db.add(Membership(user_id=user_id, community_id=dorm_id))
    db.flush()


def _unique_slug(db: Session, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "group"
    slug, n = base, 1
    while db.scalar(select(Community.id).where(Community.slug == slug)) is not None:
        n += 1
        slug = f"{base}-{n}"
    return slug


def new_join_code() -> str:
    return "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(6))


def create_group(db: Session, creator: User, data: schemas.CommunityCreate) -> Community:
    group = Community(
        kind="group",
        slug=_unique_slug(db, data.name),
        name=data.name.strip(),
        description=data.description,
        emoji=data.emoji,
        group_type=data.group_type,
        is_private=data.is_private,
        join_code=new_join_code() if data.is_private else None,
        created_by=creator.id,
    )
    db.add(group)
    db.flush()
    db.add(Membership(user_id=creator.id, community_id=group.id, role="admin"))
    db.flush()
    return group


def join(db: Session, user: User, community: Community, join_code: str | None) -> None:
    if community.kind == "dorm":
        set_dorm(db, user.id, community.id)
        return
    if membership(db, user.id, community.id) is not None:
        return
    if community.kind == "group" and community.is_private:
        given = (join_code or "").strip().upper()
        if not given or not secrets.compare_digest(given, community.join_code or ""):
            raise HTTPException(403, "This group is private — ask a member for the join code")
    db.add(Membership(user_id=user.id, community_id=community.id))
    db.flush()


def leave(db: Session, user: User, community: Community) -> None:
    if community.kind == "campus":
        raise HTTPException(400, "Everyone belongs to the campus community")
    db.execute(
        delete(Membership).where(
            Membership.user_id == user.id, Membership.community_id == community.id
        )
    )
    db.flush()
