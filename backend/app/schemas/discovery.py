from datetime import date
from typing import Annotated, Literal

from pydantic import Field

from app.schemas.common import Category, ISODateTime, Schema, TransactionType
from app.schemas.communities import Community, CommunityRef
from app.schemas.items import ItemCard
from app.schemas.requests import RequestCard
from app.schemas.users import UserRef


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
    dorm_value_shared_month_usd: int | None = None  # value exchange: completed this month


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


# ---------- buy or rent nearby (C6) ----------
class CommercialSearchBody(Schema):
    q: str = Field(min_length=1, max_length=200)  # the campus search text
    place: str | None = Field(default=None, max_length=80)  # typed town or ZIP, e.g. "94040"
    lat: float | None = Field(default=None, ge=-90, le=90)  # opt-in browser location;
    lng: float | None = Field(default=None, ge=-180, le=180)  # rounded to ~1 km, never stored
    pinned: bool = False  # True: lat/lng is a spot the person put on the map, not the device


class CommercialOffer(Schema):
    title: str
    price: float | None  # in `currency`; null when the page shows no clear price
    currency: str | None  # ISO 4217, e.g. "USD"
    price_text: str | None  # e.g. "$12.99", "$25/day"
    price_unit: Literal["each", "hour", "day", "week", "month"] | None
    offer_type: Literal["buy", "rent", "service"]
    seller: str  # store, brand, or business name
    location: str | None  # town of the store when the page names one
    url: str
    image_url: str | None


class CommercialSearchResponse(Schema):
    query: str  # the words that were searched (filler and personal details removed)
    near: str  # e.g. "Wilbur Hall", "your location", "Mountain View, CA"
    # "dorm" is kept in the type so nothing breaks, but it is no longer returned (plans/LOCATION.md)
    near_source: Literal["place", "device", "pin", "dorm", "campus"]  # "dorm" is no longer used
    offers: list[CommercialOffer]  # cheapest first; no price → last
    provider: str  # "exa" | "mock" (sample data)
    cached: bool
    fetched_at: ISODateTime


# ---------- mutual matching (docs/plans/mutual-matching.md) ----------
class MutualNeed(Schema):
    kind: Literal["request", "search", "predicted"]  # "search"/"predicted" are guesses
    name: str  # e.g. "tripod"
    request: RequestCard | None  # set when kind = "request"


class MutualLink(Schema):
    item: ItemCard  # this item answers that need
    need: MutualNeed
    score: float


class MutualMatch(Schema):
    user: UserRef  # the other person
    you_give: list[MutualLink]  # my items they need (1..3)
    you_get: list[MutualLink]  # their items I need (1..3)
    score: float  # 0..1
    reason: str  # e.g. "Same dorm · you both asked"
    uses_prediction: bool  # true if any link is a guess


class MutualMatchesResponse(Schema):
    enabled: bool  # my opt-in (Me.match_suggestions)
    matches: list[MutualMatch]  # ≤ 10
    # What the profile agent noticed about me (MUTUAL_MATCHING=ai only; shown only to me).
    summary: str | None = None  # one sentence, e.g. "You lend outdoor gear and borrow tools."
    likely_needs: list[str] = []  # ≤ 5 guesses, e.g. ["duffel bag"]; word them as "might need"
