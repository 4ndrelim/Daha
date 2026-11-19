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


class HandoffSuggestion(Schema):
    """A proposed handoff time and exchange spot (HANDOFF_COORDINATOR_ENABLED)."""

    # thinking = the agent is working · draft = only its author sees it · sent = waiting for the
    # other person · accepted = it is now the transaction's pickup place and time · failed
    status: Literal["thinking", "draft", "sent", "accepted", "failed"]
    mine: bool  # I asked for it, or I sent it
    start_time: ISODateTime | None
    place: Place | None
    reason: str | None  # one short line from the agent; null for a hand-picked time
    confidence: float | None  # 0..1
    sample: bool  # true = a labeled stand-in, no AI ran (AI_PROVIDER=mock)
    message: str | None  # set when failed, e.g. "Couldn't find a good time — suggest one yourself"
    can_send: bool  # my draft: "Send"
    can_accept: bool  # their suggestion: one tap to confirm


class HandoffState(Schema):
    can_suggest: bool  # "Suggest a time & place" may run now
    runs_left_today: int  # of 3 per transaction per 24 h
    suggestion: HandoffSuggestion | None


class HandoffSendBody(Schema):
    """Empty = send my draft as it is. With both fields = send my own time and place ("Change")."""

    start_time: ISODateTime | None = None
    place_id: ID | None = None


class TxValue(Schema):
    """Value exchange on one transaction (estimates in whole US dollars; no money moves)."""

    value_usd: int | None  # the item's value (frozen when the exchange completes)
    swap_value_usd: int | None  # swaps: what the borrower gave in return
    difference_usd: int | None  # swaps: |value_usd - swap_value_usd| when both are known
    high_value: bool  # value_usd >= 100
    needs_condition_check: bool  # a High value lend waits for the confirmed 3 handoff photos
    bonus_points: int | None  # completed: the value bonus the viewer got from this exchange
    # completed with no bonus: self | no_value | under_review | repeat
    no_bonus_reason: str | None
    can_set_swap_value: bool  # the viewer is the swap's borrower and it isn't finished


class SwapValueBody(Schema):
    value_usd: int | None = Field(default=None, ge=0, le=10000)


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
    pickup_at: ISODateTime | None = None  # the agreed handoff time, once someone accepted one
    pickup_note: str | None
    conversation_id: ID
    allowed_actions: list[TxAction]
    can_review: bool
    timeline: list[TxTimelineEntry]
    created_at: ISODateTime
    updated_at: ISODateTime
    condition: ConditionCheck | None = None  # null unless the feature is on and kind = lend
    handoff: HandoffState | None = None  # null unless the feature is on, before the handoff
    value: TxValue | None = None  # null unless VALUE_EXCHANGE_ENABLED; estimates only


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
