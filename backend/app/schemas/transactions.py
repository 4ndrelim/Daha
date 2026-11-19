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


ConditionSlot = Literal["front", "back", "marks"]
ConditionStage = Literal["handoff", "return"]


class ConditionPhotos(Schema):
    """Photo URLs per guided shot; null until taken (and again once the exchange ends)."""

    front: str | None
    back: str | None
    marks: str | None


class ConditionCheck(Schema):
    """Condition check on a loan (CONDITION_CHECK_ENABLED). Never affects points or karma."""

    handoff_photos: ConditionPhotos
    handoff_confirmed_at: ISODateTime | None  # the borrower tapped "This looks right"
    return_photos: ConditionPhotos
    status: Literal["waiting", "checking", "done", "failed"]
    result: Literal["no_changes", "possible_changes"] | None
    note: str | None  # short and neutral; never "damaged" or "your fault"
    sample: bool  # true = a labeled sample result (AI_PROVIDER=mock or the agent isn't set up)
    checked_at: ISODateTime | None
    photos_deleted: bool  # photos are removed when the exchange ends; only the result is kept
    can_add_handoff_photos: bool  # me = owner, before the borrower confirmed
    can_confirm: bool  # me = borrower, all 3 handoff photos are in, not yet confirmed
    can_add_return_photos: bool  # me = borrower, item handed off, no result yet


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
    condition: ConditionCheck | None = None  # null unless the feature is on and kind = lend


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
