from datetime import date
from typing import Annotated, Literal

from pydantic import Field

from app.schemas.common import Category, ISODateTime, Schema, TransactionType
from app.schemas.communities import Community, CommunityRef
from app.schemas.items import ItemCard
from app.schemas.requests import RequestCard


class ParsedQuery(Schema):
    text: str
    category: Category | None
    scope: Literal["campus", "dorm"] | None
    near_me: bool
    available_from: date | None
    available_until: date | None
    transaction_type: TransactionType | None
    chips: list[str]  # human-readable, e.g. ["Tech", "Near you", "This weekend"]


class SearchResponse(Schema):
    parsed: ParsedQuery
    items: list[ItemCard]
    requests: list[RequestCard]
    communities: list[Community]
    next_offset: int | None


class FulfillableRequest(Schema):
    request: RequestCard
    my_matching_items: list[ItemCard]


class HomeFeedStats(Schema):
    dorm_items: int
    campus_items: int
    open_requests: int


class HomeFeed(Schema):
    dorm: CommunityRef | None
    my_item_count: int
    show_scan_cta: bool  # my_item_count < 3
    you_can_help: list[FulfillableRequest]  # ≤ 5
    requests_nearby: list[RequestCard]  # ≤ 10
    new_nearby: list[ItemCard]  # ≤ 12
    stats: HomeFeedStats


class FeedEntryRequest(Schema):
    kind: Literal["request"] = "request"
    created_at: ISODateTime
    request: RequestCard


class FeedEntryItem(Schema):
    kind: Literal["item"] = "item"
    created_at: ISODateTime
    item: ItemCard


FeedEntry = Annotated[FeedEntryRequest | FeedEntryItem, Field(discriminator="kind")]
