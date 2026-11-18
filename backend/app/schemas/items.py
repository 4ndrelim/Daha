from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.common import (
    ID,
    Category,
    Condition,
    ISODateTime,
    ItemSource,
    ItemStatus,
    Schema,
    TransactionType,
    Visibility,
)
from app.schemas.communities import Place
from app.schemas.users import UserRef


class ItemImage(Schema):
    id: ID
    url: str
    width: int
    height: int


class ItemCard(Schema):
    id: ID
    name: str
    category: Category
    transaction_type: TransactionType
    status: ItemStatus
    condition: Condition | None
    quantity: int
    thumbnail_url: str | None
    owner: UserRef
    visibility: Visibility
    community_label: str  # "Campus" | dorm name | first group name (+N) | "Only you"
    distance_min: int | None
    same_dorm: bool
    created_at: ISODateTime
    match_score: float | None  # only in search/match/fulfillable responses, else null
    match_reason: str | None


class ItemDetail(ItemCard):
    description: str | None
    images: list[ItemImage]
    max_lend_days: int | None
    available_from: date | None
    available_until: date | None
    pickup_place: Place | None
    pickup_note: str | None  # owner, or counterparty of an accepted/handed_off transaction
    group_ids: list[ID]  # owner only, else []
    pings_enabled: bool
    is_mine: bool
    can_borrow: bool
    active_transaction_id: ID | None
    source: ItemSource
    updated_at: ISODateTime


class ItemCreate(Schema):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    category: Category
    quantity: int = Field(default=1, ge=1, le=999)
    condition: Condition | None = None
    transaction_type: TransactionType
    max_lend_days: int | None = Field(default=None, ge=1, le=365)
    available_from: date | None = None
    available_until: date | None = None
    visibility: Visibility
    group_ids: list[ID] = Field(default_factory=list)
    pickup_place_id: ID | None = None
    pickup_note: str | None = None
    image_upload_ids: list[ID] = Field(default_factory=list)  # ≤ 6, first = thumbnail
    pings_enabled: bool = True


class ItemUpdate(Schema):
    """Partial<ItemCreate> & {status?}. Only fields present in the body are applied."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    category: Category | None = None
    quantity: int | None = Field(default=None, ge=1, le=999)
    condition: Condition | None = None
    transaction_type: TransactionType | None = None
    max_lend_days: int | None = Field(default=None, ge=1, le=365)
    available_from: date | None = None
    available_until: date | None = None
    visibility: Visibility | None = None
    group_ids: list[ID] | None = None
    pickup_place_id: ID | None = None
    pickup_note: str | None = None
    image_upload_ids: list[ID] | None = None
    pings_enabled: bool | None = None
    status: Literal["available", "unavailable"] | None = None


class BorrowBody(Schema):
    message: str | None = None
    start_date: date | None = None
    due_date: date | None = None
    request_id: ID | None = None


class ItemsBatchBody(Schema):
    items: list[ItemCreate]  # ≤ 30


class ItemsBatchResponse(Schema):
    items: list[ItemDetail]
