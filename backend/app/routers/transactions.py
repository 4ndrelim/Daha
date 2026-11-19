from typing import Literal

from fastapi import APIRouter
from sqlalchemy import or_, select

from app import schemas
from app.api.deps import DB, CurrentUser, Viewer
from app.models import Transaction
from app.services import condition, transactions

router = APIRouter(tags=["transactions"])


@router.get("/transactions", response_model=list[schemas.Transaction])
def list_transactions(
    viewer: Viewer,
    db: DB,
    role: Literal["owner", "borrower", "all"] = "all",
    state: Literal["active", "past", "all"] = "all",
):
    me = viewer.user_id
    query = select(Transaction)
    if role == "owner":
        query = query.where(Transaction.owner_id == me)
    elif role == "borrower":
        query = query.where(Transaction.borrower_id == me)
    else:
        query = query.where(or_(Transaction.owner_id == me, Transaction.borrower_id == me))
    if state == "active":
        query = query.where(Transaction.status.in_(transactions.ACTIVE_STATUSES))
    elif state == "past":
        query = query.where(Transaction.status.in_(transactions.PAST_STATUSES))
    rows = db.execute(
        query.order_by(Transaction.updated_at.desc(), Transaction.id.desc()).limit(200)
    ).scalars()
    return transactions.transactions_out(db, list(rows), viewer)


@router.get("/transactions/{transaction_id}", response_model=schemas.Transaction)
def get_transaction(transaction_id: int, viewer: Viewer, db: DB):
    tx = transactions.get_for_party(db, transaction_id, viewer.user_id)
    return transactions.transaction_out(db, tx, viewer)


@router.post("/transactions/{transaction_id}/actions", response_model=schemas.Transaction)
def transaction_action(
    transaction_id: int, body: schemas.TxActionBody, user: CurrentUser, viewer: Viewer, db: DB
):
    tx = transactions.get_for_party(db, transaction_id, user.id, lock=True)
    transactions.apply_action(db, tx, user, body)
    condition.on_status_change(db, tx)  # an ended loan keeps only the condition result text
    db.commit()
    db.refresh(tx)
    return transactions.transaction_out(db, tx, viewer)


@router.post(
    "/transactions/{transaction_id}/review", response_model=schemas.Review, status_code=201
)
def review_transaction(transaction_id: int, body: schemas.ReviewCreate, user: CurrentUser, db: DB):
    tx = transactions.get_for_party(db, transaction_id, user.id)
    review = transactions.create_review(db, tx, user, body)
    db.commit()
    return transactions.review_out(db, review)
