from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.common import (
    ID,
    Category,
    ISODateTime,
    RequestStatus,
    Schema,
    TransactionType,
    Visibility,
)
from app.schemas.communities import Place
from app.schemas.items import ItemCard, ItemCreate
from app.schemas.transactions import Transaction
from app.schemas.users import UserRef


class ParsedRequest(Schema):
    kind: Literal["request", "offer", "other"]
    title: str
    item_name: str | None
    category: Category | None
    attributes: dict[str, str]
    quantity: int
    needed_from: date | None
    needed_until: date | None
    duration_days: int | None
    transaction_type: TransactionType | None
    confidence: float


class ParseRequestBody(Schema):
    text: str


class RequestCard(Schema):
    id: ID
    title: str
    raw_text: str
    category: Category | None
    status: RequestStatus
    requester: UserRef
    needed_from: date | None
    needed_until: date | None
    visibility: Visibility
    community_label: str
    distance_min: int | None
    same_dorm: bool
    offer_count: int
    match_count: int
    created_at: ISODateTime


class RequestDetail(RequestCard):
    item_name: str | None
    attributes: dict[str, str]
    quantity: int
    duration_days: int | None
    transaction_type: TransactionType | None
    pickup_place: Place | None
    group_ids: list[ID]
    is_mine: bool
    matching_status: Literal["pending", "done"]
    offers: list[Transaction]  # requester sees all; others see only their own
    share_url: str  # `${PUBLIC_BASE_URL}/r/${id}`


class RequestCreate(Schema):
    raw_text: str = Field(min_length=1, max_length=1000)
    title: str = Field(min_length=1, max_length=200)
    item_name: str | None = None
    category: Category | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    quantity: int = Field(default=1, ge=1, le=999)
    needed_from: date | None = None
    needed_until: date | None = None
    duration_days: int | None = Field(default=None, ge=1, le=365)
    transaction_type: TransactionType | None = None
    visibility: Visibility
    group_ids: list[ID] = Field(default_factory=list)
    pickup_place_id: ID | None = None


class RequestUpdate(Schema):
    """Partial<RequestCreate> & {status?}. Only fields present in the body are applied."""

    raw_text: str | None = Field(default=None, min_length=1, max_length=1000)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    item_name: str | None = None
    category: Category | None = None
    attributes: dict[str, str] | None = None
    quantity: int | None = Field(default=None, ge=1, le=999)
    needed_from: date | None = None
    needed_until: date | None = None
    duration_days: int | None = Field(default=None, ge=1, le=365)
    transaction_type: TransactionType | None = None
    visibility: Visibility | None = None
    group_ids: list[ID] | None = None
    pickup_place_id: ID | None = None
    status: Literal["cancelled", "fulfilled"] | None = None


class OfferCreate(Schema):
    """Exactly one of item_id / new_item."""

    item_id: ID | None = None
    new_item: ItemCreate | None = None
    message: str | None = None


class MatchesResponse(Schema):
    matching_status: Literal["pending", "done"]
    items: list[ItemCard]
    private_pinged_count: int  # anonymous pings sent (a number only, never who)
