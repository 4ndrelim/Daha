from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from sqlalchemy import select

from app import schemas
from app.api.deps import DB, CurrentUser, Viewer
from app.models import Item
from app.routers._stub import not_implemented
from app.services import items as items_service
from app.services import serializers
from app.services.viewer import build_viewer

router = APIRouter(tags=["items"])


@router.post("/items", response_model=schemas.ItemDetail, status_code=201)
def create_item(body: schemas.ItemCreate, user: CurrentUser, db: DB, background: BackgroundTasks):
    item = items_service.create_item(db, user, body, background=background)
    db.commit()
    return serializers.item_detail(db, item, build_viewer(db, user))


@router.post("/items/batch", response_model=schemas.ItemsBatchResponse, status_code=201)
def create_items_batch(
    body: schemas.ItemsBatchBody, user: CurrentUser, db: DB, background: BackgroundTasks
):
    """≤ 30 items in one DB transaction: either all are created or none."""
    if not body.items:
        raise HTTPException(400, "Add at least one item")
    if len(body.items) > items_service.MAX_BATCH:
        raise HTTPException(400, f"At most {items_service.MAX_BATCH} items at once")
    created = [
        items_service.create_item(db, user, data, background=background) for data in body.items
    ]
    db.commit()
    viewer = build_viewer(db, user)
    return schemas.ItemsBatchResponse(
        items=[serializers.item_detail(db, item, viewer) for item in created]
    )


@router.get("/me/items", response_model=list[schemas.ItemCard])
def my_items(viewer: Viewer, db: DB, status: schemas.ItemStatus | None = None):
    query = select(Item).where(Item.owner_id == viewer.user_id, Item.archived.is_(False))
    if status:
        query = query.where(Item.status == status)
    rows = db.execute(query.order_by(Item.created_at.desc(), Item.id.desc())).scalars().all()
    return serializers.item_cards(db, list(rows), viewer)


@router.get("/items/{item_id}", response_model=schemas.ItemDetail)
def get_item(item_id: int, viewer: Viewer, db: DB):
    return serializers.item_detail(db, items_service.get_visible_item(db, item_id, viewer), viewer)


@router.patch("/items/{item_id}", response_model=schemas.ItemDetail)
def update_item(
    item_id: int,
    body: schemas.ItemUpdate,
    user: CurrentUser,
    viewer: Viewer,
    db: DB,
    background: BackgroundTasks,
):
    item = items_service.get_own_item(db, item_id, viewer)
    items_service.update_item(db, item, user, body, background=background)
    db.commit()
    return serializers.item_detail(db, item, build_viewer(db, user))


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int, viewer: Viewer, db: DB):
    items_service.archive_item(db, items_service.get_own_item(db, item_id, viewer))
    db.commit()
    return Response(status_code=204)


@router.post("/items/{item_id}/borrow", response_model=schemas.Transaction, status_code=201)
def borrow_item(item_id: int, body: schemas.BorrowBody):
    not_implemented()
