from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app import schemas
from app.api.deps import DB, CurrentUser, Viewer
from app.models import Item, Review, User
from app.services import serializers, users
from app.services.pagination import Limit, Offset, page_of
from app.services.visibility import item_visible_clause

router = APIRouter(tags=["users"])


def _get_user(db: DB, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


@router.get("/me", response_model=schemas.Me)
def get_me(user: CurrentUser, db: DB):
    return serializers.me_out(db, user)


@router.patch("/me", response_model=schemas.Me)
def update_me(body: schemas.MeUpdate, user: CurrentUser, db: DB):
    users.update_me(db, user, body)
    db.commit()
    return serializers.me_out(db, user)


@router.get("/users/{user_id}", response_model=schemas.UserPublic)
def get_user(user_id: int, viewer: Viewer, db: DB):
    return serializers.user_public(db, _get_user(db, user_id))


@router.get("/users/{user_id}/items", response_model=schemas.Page[schemas.ItemCard])
def get_user_items(user_id: int, viewer: Viewer, db: DB, offset: Offset = 0, limit: Limit = 20):
    """Only items the viewer may see. Private items never appear on a profile."""
    _get_user(db, user_id)
    rows = (
        db.execute(
            select(Item)
            .where(
                Item.owner_id == user_id,
                Item.visibility != "private",
                item_visible_clause(viewer),
            )
            .order_by(Item.created_at.desc(), Item.id.desc())
            .offset(offset)
            .limit(limit + 1)
        )
        .scalars()
        .all()
    )
    items, next_offset = page_of(list(rows), offset, limit)
    return schemas.Page[schemas.ItemCard](
        items=serializers.item_cards(db, items, viewer), next_offset=next_offset
    )


@router.get("/users/{user_id}/reviews", response_model=list[schemas.Review])
def get_user_reviews(user_id: int, viewer: Viewer, db: DB):
    _get_user(db, user_id)
    reviews = (
        db.execute(
            select(Review)
            .where(Review.reviewee_id == user_id)
            .order_by(Review.created_at.desc(), Review.id.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )
    refs = serializers.user_refs(db, {r.reviewer_id for r in reviews})
    return [
        schemas.Review(
            id=r.id,
            transaction_id=r.transaction_id,
            reviewer=refs[r.reviewer_id],
            reviewee_id=r.reviewee_id,
            rating=r.rating,
            body=r.body,
            created_at=r.created_at,
        )
        for r in reviews
    ]
