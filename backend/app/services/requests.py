"""Requests ("anyone have a …?") and offers on them."""

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import settings
from app.discovery import hooks
from app.models import Item, ItemRequest, Place, RequestAudience, Transaction, User
from app.services import items as items_service
from app.services import serializers, transactions
from app.services.notifications import notify
from app.services.viewer import ViewerContext
from app.services.visibility import (
    request_is_expired,
    request_visible_clause,
    resolve_audiences,
)

EDITABLE_FIELDS = (
    "raw_text",
    "title",
    "item_name",
    "category",
    "attributes",
    "quantity",
    "needed_from",
    "needed_until",
    "duration_days",
    "transaction_type",
    "pickup_place_id",
)
NOT_NULLABLE = {"raw_text", "title", "attributes", "quantity"}


def _validate(db: Session, visibility: str, needed_from, needed_until, place_id) -> None:
    if visibility == "private":
        raise HTTPException(400, "A request has to be visible to someone")
    if needed_from and needed_until and needed_from > needed_until:
        raise HTTPException(400, "The end date is before the start date")
    if place_id is not None and db.get(Place, place_id) is None:
        raise HTTPException(400, "That pickup spot doesn't exist")


def _write_audiences(db: Session, req: ItemRequest, community_ids: list[int]) -> None:
    db.execute(delete(RequestAudience).where(RequestAudience.request_id == req.id))
    db.add_all(RequestAudience(request_id=req.id, community_id=cid) for cid in community_ids)


def create_request(
    db: Session, user: User, data: schemas.RequestCreate, background: BackgroundTasks | None
) -> ItemRequest:
    _validate(db, data.visibility, data.needed_from, data.needed_until, data.pickup_place_id)
    audience = resolve_audiences(db, user, data.visibility, data.group_ids)
    req = ItemRequest(
        requester_id=user.id,
        raw_text=data.raw_text.strip(),
        title=data.title.strip(),
        item_name=data.item_name,
        category=data.category,
        attributes=data.attributes,
        quantity=data.quantity,
        needed_from=data.needed_from,
        needed_until=data.needed_until,
        duration_days=data.duration_days,
        transaction_type=data.transaction_type,
        visibility=data.visibility,
        pickup_place_id=data.pickup_place_id,
        status="open",
        matching_status="pending",
    )
    db.add(req)
    db.flush()
    _write_audiences(db, req, audience)
    db.flush()
    if background is not None:
        background.add_task(hooks.on_request_created, req.id)
    return req


def get_visible_request(db: Session, request_id: int, viewer: ViewerContext) -> ItemRequest:
    req = db.execute(
        select(ItemRequest).where(ItemRequest.id == request_id, request_visible_clause(viewer))
    ).scalar_one_or_none()
    if req is None:
        raise HTTPException(404, "Request not found")
    return req


def update_request(
    db: Session,
    req: ItemRequest,
    user: User,
    data: schemas.RequestUpdate,
    background: BackgroundTasks | None,
) -> ItemRequest:
    if req.requester_id != user.id:
        raise HTTPException(403, "Only the person who asked can change this request")
    if req.status in ("fulfilled", "cancelled"):
        raise HTTPException(409, "This request is already closed")
    sent = data.model_fields_set

    edited = False
    for field in EDITABLE_FIELDS:
        if field not in sent:
            continue
        value = getattr(data, field)
        if value is None and field in NOT_NULLABLE:
            continue
        setattr(req, field, value.strip() if field in ("raw_text", "title") else value)
        edited = True

    visibility_sent = "visibility" in sent and data.visibility is not None
    if visibility_sent or ("group_ids" in sent and data.group_ids is not None):
        if visibility_sent:
            req.visibility = data.visibility
        group_ids = data.group_ids
        if group_ids is None and req.visibility == "groups":
            group_ids = list(
                db.scalars(
                    select(RequestAudience.community_id).where(RequestAudience.request_id == req.id)
                )
            )
        _validate(db, req.visibility, None, None, None)
        _write_audiences(db, req, resolve_audiences(db, user, req.visibility, group_ids))
        edited = True
    _validate(db, req.visibility, req.needed_from, req.needed_until, req.pickup_place_id)

    if "status" in sent and data.status is not None:
        req.status = data.status
        if data.status == "fulfilled":
            req.fulfilled_at = func.now()
            reason = "This request was marked as fulfilled."
        else:
            reason = "This request was cancelled."
        transactions.decline_open_offers(db, req, user, reason)

    db.add(req)
    db.flush()
    db.refresh(req)
    if edited and background is not None:
        background.add_task(hooks.on_request_updated, req.id)
    return req


def create_offer(
    db: Session,
    req: ItemRequest,
    user: User,
    data: schemas.OfferCreate,
    background: BackgroundTasks | None,
) -> Transaction:
    """Offer one of your items (or a brand-new one) on someone's request."""
    if req.requester_id == user.id:
        raise HTTPException(400, "You can't offer on your own request")
    if req.status != "open" or request_is_expired(req):
        raise HTTPException(409, "This request is no longer open")
    if (data.item_id is None) == (data.new_item is None):
        raise HTTPException(400, "Offer either one of your items or a new item, not both")

    if data.item_id is not None:
        item = db.get(Item, data.item_id)
        if item is None or item.owner_id != user.id or item.archived:
            raise HTTPException(400, "You can only offer your own items")
        if item.status != "available":
            raise HTTPException(409, "That item isn't available right now")
        duplicate = db.scalar(
            select(Transaction.id).where(
                Transaction.request_id == req.id,
                Transaction.item_id == item.id,
                Transaction.status.in_(transactions.ACTIVE_STATUSES),
            )
        )
        if duplicate is not None:
            raise HTTPException(409, "You already offered this item")
    else:
        item = items_service.create_item(
            db, user, data.new_item, source="offer", background=background
        )

    requester = db.get(User, req.requester_id)
    tx = transactions.create_transaction(
        db,
        item=item,
        borrower=requester,
        initiated_by="owner",
        message=data.message,
        start_date=req.needed_from,
        due_date=req.needed_until if item.transaction_type == "lend" else None,
        request=req,
    )
    notify(
        db,
        requester.id,
        "offer",
        f"{user.name.split()[0]} can help with “{req.title}”",
        item.name,
        f"/requests/{req.id}",
        actor_id=user.id,
        data={"transaction_id": tx.id, "request_id": req.id, "item_id": item.id},
    )
    return tx


def request_detail(db: Session, req: ItemRequest, viewer: ViewerContext) -> schemas.RequestDetail:
    card = serializers.request_cards(db, [req], viewer)[0]
    is_mine = req.requester_id == viewer.user_id
    query = select(Transaction).where(Transaction.request_id == req.id)
    if not is_mine:  # the requester sees every offer; anyone else sees only their own
        query = query.where(
            or_(Transaction.owner_id == viewer.user_id, Transaction.borrower_id == viewer.user_id)
        )
    offers = db.execute(query.order_by(Transaction.id)).scalars().all()
    place = db.get(Place, req.pickup_place_id) if req.pickup_place_id else None
    group_ids: list[int] = []
    if is_mine and req.visibility == "groups":
        group_ids = list(
            db.scalars(
                select(RequestAudience.community_id)
                .where(RequestAudience.request_id == req.id)
                .order_by(RequestAudience.community_id)
            )
        )
    return schemas.RequestDetail(
        **card.model_dump(),
        item_name=req.item_name,
        attributes={str(k): str(v) for k, v in (req.attributes or {}).items()},
        quantity=req.quantity,
        duration_days=req.duration_days,
        transaction_type=req.transaction_type,
        pickup_place=serializers.place_out(place, viewer) if place else None,
        group_ids=group_ids,
        is_mine=is_mine,
        matching_status=req.matching_status,
        offers=transactions.transactions_out(db, list(offers), viewer),
        share_url=f"{settings.public_base_url.rstrip('/')}/r/{req.id}",
    )
