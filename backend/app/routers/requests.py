from fastapi import APIRouter, BackgroundTasks
from sqlalchemy import select

from app import schemas
from app.api.deps import DB, CurrentUser, Viewer
from app.models import ItemRequest
from app.services import requests as requests_service
from app.services import serializers, transactions
from app.services.viewer import build_viewer

router = APIRouter(tags=["requests"])


@router.post("/requests", response_model=schemas.RequestDetail, status_code=201)
def create_request(
    body: schemas.RequestCreate, user: CurrentUser, db: DB, background: BackgroundTasks
):
    req = requests_service.create_request(db, user, body, background)
    db.commit()
    return requests_service.request_detail(db, req, build_viewer(db, user))


@router.get("/me/requests", response_model=list[schemas.RequestCard])
def my_requests(viewer: Viewer, db: DB):
    rows = (
        db.execute(
            select(ItemRequest)
            .where(ItemRequest.requester_id == viewer.user_id)
            .order_by(ItemRequest.created_at.desc(), ItemRequest.id.desc())
        )
        .scalars()
        .all()
    )
    return serializers.request_cards(db, list(rows), viewer)


@router.get("/requests/{request_id}", response_model=schemas.RequestDetail)
def get_request(request_id: int, viewer: Viewer, db: DB):
    req = requests_service.get_visible_request(db, request_id, viewer)
    return requests_service.request_detail(db, req, viewer)


@router.patch("/requests/{request_id}", response_model=schemas.RequestDetail)
def update_request(
    request_id: int,
    body: schemas.RequestUpdate,
    user: CurrentUser,
    viewer: Viewer,
    db: DB,
    background: BackgroundTasks,
):
    req = requests_service.get_visible_request(db, request_id, viewer)
    requests_service.update_request(db, req, user, body, background)
    db.commit()
    return requests_service.request_detail(db, req, build_viewer(db, user))


@router.post("/requests/{request_id}/offers", response_model=schemas.Transaction, status_code=201)
def create_offer(
    request_id: int,
    body: schemas.OfferCreate,
    user: CurrentUser,
    viewer: Viewer,
    db: DB,
    background: BackgroundTasks,
):
    req = requests_service.get_visible_request(db, request_id, viewer)
    tx = requests_service.create_offer(db, req, user, body, background)
    db.commit()
    return transactions.transaction_out(db, tx, viewer)
