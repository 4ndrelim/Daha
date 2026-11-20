from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from sqlalchemy import select

from app import schemas
from app.api.deps import DB, CurrentUser, Viewer
from app.models import Item, ItemRequest
from app.services import availability, serializers, transactions, value_exchange
from app.services import items as items_service
from app.services.notifications import notify
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


@router.get("/items/value-estimate", response_model=schemas.ValueEstimate)
def value_estimate(name: str, viewer: Viewer, db: DB):
    """Value exchange: a starting value for the List an item form. Never makes a paid call."""
    return value_exchange.suggest(db, name[:120])


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
def delete_item(item_id: int, user: CurrentUser, viewer: Viewer, db: DB):
    item = items_service.get_own_item(db, item_id, viewer)
    items_service.archive_item(db, item)
    transactions.decline_pending_for_item(db, item, user, f"“{item.name}” was removed.")
    db.commit()
    return Response(status_code=204)


@router.post("/items/{item_id}/borrow", response_model=schemas.Transaction, status_code=201)
def borrow_item(item_id: int, body: schemas.BorrowBody, user: CurrentUser, viewer: Viewer, db: DB):
    """Ask to borrow (or take / swap) an item straight from its page."""
    item = items_service.get_visible_item(db, item_id, viewer)
    if item.owner_id == user.id:
        raise HTTPException(400, "This is your own item")
    if item.status != "available" or item.visibility == "private":
        raise HTTPException(409, "This item isn't available right now")
    problem = availability.borrow_problem(item, body.start_date, body.due_date)
    if problem:
        raise HTTPException(409, problem)
    if transactions.has_open_transaction(db, item.id, user.id):
        raise HTTPException(409, "You already asked for this item")
    request = None
    if body.request_id is not None:
        request = db.get(ItemRequest, body.request_id)
        if request is None or request.requester_id != user.id or request.status != "open":
            raise HTTPException(400, "That isn't one of your open requests")
    tx = transactions.create_transaction(
        db,
        item=item,
        borrower=user,
        initiated_by="borrower",
        message=body.message,
        start_date=body.start_date,
        due_date=body.due_date,
        request=request,
    )
    verb = {"lend": "borrow", "give": "have", "exchange": "swap for"}[item.transaction_type]
    notify(
        db,
        item.owner_id,
        "borrow_request",
        f"{user.name.split()[0]} wants to {verb} your item",
        item.name,
        f"/messages/{tx.conversation_id}",
        actor_id=user.id,
        data={"transaction_id": tx.id, "item_id": item.id},
    )
    db.commit()
    return transactions.transaction_out(db, tx, viewer)
