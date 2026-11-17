from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.common import ID, ISODateTime, Schema, TransactionType, TxAction, TxStatus
from app.schemas.communities import Place
from app.schemas.items import ItemCard
from app.schemas.users import UserRef


class TxTimelineEntry(Schema):
    status: TxStatus
    at: ISODateTime
    by: UserRef | None
    note: str | None


class Transaction(Schema):
    id: ID
    kind: TransactionType
    status: TxStatus
    item: ItemCard
    request_id: ID | None
    owner: UserRef
    borrower: UserRef
    initiated_by: Literal["owner", "borrower"]
    my_role: Literal["owner", "borrower"]
    message: str | None
    start_date: date | None
    due_date: date | None
    is_overdue: bool
    pickup_place: Place | None
    pickup_note: str | None
    conversation_id: ID
    allowed_actions: list[TxAction]
    can_review: bool
    timeline: list[TxTimelineEntry]
    created_at: ISODateTime
    updated_at: ISODateTime


class TxActionBody(Schema):
    action: TxAction
    note: str | None = None
    due_date: date | None = None
    pickup_place_id: ID | None = None


class ReviewCreate(Schema):
    rating: int = Field(ge=1, le=5)
    body: str | None = None


class Review(Schema):
    id: ID
    transaction_id: ID
    reviewer: UserRef
    reviewee_id: ID
    rating: int
    body: str | None
    created_at: ISODateTime
