from fastapi import APIRouter

from app import schemas
from app.routers._stub import not_implemented

router = APIRouter(tags=["items"])


@router.post("/items", response_model=schemas.ItemDetail, status_code=201)
def create_item(body: schemas.ItemCreate):
    not_implemented()


@router.post("/items/batch", response_model=schemas.ItemsBatchResponse, status_code=201)
def create_items_batch(body: schemas.ItemsBatchBody):
    not_implemented()


@router.get("/items/{item_id}", response_model=schemas.ItemDetail)
def get_item(item_id: int):
    not_implemented()


@router.patch("/items/{item_id}", response_model=schemas.ItemDetail)
def update_item(item_id: int, body: schemas.ItemUpdate):
    not_implemented()


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    not_implemented()


@router.get("/me/items", response_model=list[schemas.ItemCard])
def my_items(status: schemas.ItemStatus | None = None):
    not_implemented()


@router.post("/items/{item_id}/borrow", response_model=schemas.Transaction, status_code=201)
def borrow_item(item_id: int, body: schemas.BorrowBody):
    not_implemented()
