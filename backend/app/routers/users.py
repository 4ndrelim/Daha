from fastapi import APIRouter

from app import schemas
from app.routers._stub import not_implemented

router = APIRouter(tags=["users"])


@router.get("/me", response_model=schemas.Me)
def get_me():
    not_implemented()


@router.patch("/me", response_model=schemas.Me)
def update_me(body: schemas.MeUpdate):
    not_implemented()


@router.get("/users/{user_id}", response_model=schemas.UserPublic)
def get_user(user_id: int):
    not_implemented()


@router.get("/users/{user_id}/items", response_model=schemas.Page[schemas.ItemCard])
def get_user_items(user_id: int, offset: int = 0, limit: int = 20):
    not_implemented()


@router.get("/users/{user_id}/reviews", response_model=list[schemas.Review])
def get_user_reviews(user_id: int):
    not_implemented()
