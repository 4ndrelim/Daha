from typing import Literal

from fastapi import APIRouter

from app import schemas
from app.routers._stub import not_implemented

router = APIRouter(tags=["transactions"])


@router.get("/transactions", response_model=list[schemas.Transaction])
def list_transactions(
    role: Literal["owner", "borrower", "all"] = "all",
    state: Literal["active", "past", "all"] = "all",
):
    not_implemented()


@router.get("/transactions/{transaction_id}", response_model=schemas.Transaction)
def get_transaction(transaction_id: int):
    not_implemented()


@router.post("/transactions/{transaction_id}/actions", response_model=schemas.Transaction)
def transaction_action(transaction_id: int, body: schemas.TxActionBody):
    not_implemented()


@router.post(
    "/transactions/{transaction_id}/review", response_model=schemas.Review, status_code=201
)
def review_transaction(transaction_id: int, body: schemas.ReviewCreate):
    not_implemented()
