"""Buy or rent nearby (C6): store and rental alternatives from the web, cheapest first.

The web asks for these when a campus search comes back thin (≤ 2 items), and whenever someone
taps "Compare store prices nearby". Borrowing stays the first answer; this is the fallback.

What leaves our server (one Exa web search):
- the search words only. Filler ("anyone have", "near me", dates), emails, phone numbers and
  links are stripped first;
- a coarse location: the device's location when the person allowed it (rounded to ~1 km in the
  browser and again here), else Stanford campus, or a town/ZIP they typed (plans/LOCATION.md),
  plus that location's country, worked out offline here (app/discovery/countries.py);
- never the person's name, id, email, or anything else stored about them. Coordinates are not
  stored or logged here; the cache key is a hash.

Cost: one Exa search with up to 10 results and a per-page summary (~$0.017). Results are cached
per (words, area) for COMMERCIAL_CACHE_HOURS. Each person gets COMMERCIAL_DAILY_LOOKUPS_PER_USER
uncached lookups per 24 h, and all lookups stop at COMMERCIAL_BUDGET_USD per calendar month.
"""

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import settings
from app.discovery.countries import country_for, local_currency, place_country
from app.discovery.query_parser import parse_query
from app.models import AICache, Event
from app.services.viewer import ViewerContext

log = logging.getLogger(__name__)

CACHE_VERSION = "commercial-v1"
EVENT_TYPE = "commercial_lookup"
MAX_OFFERS = 8
UNITS = ("each", "hour", "day", "week", "month")
OFFER_TYPES = ("buy", "rent", "service")
CURRENCY_SYMBOL = {
    "USD": "$", "CAD": "CA$", "MXN": "MX$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "CN¥",
    "HKD": "HK$", "TWD": "NT$", "KRW": "₩", "SGD": "S$", "MYR": "RM", "THB": "฿", "VND": "₫",
    "PHP": "₱", "IDR": "Rp", "INR": "₹", "AUD": "A$", "NZD": "NZ$", "ILS": "₪", "BRL": "R$",
}  # fmt: skip

_EMAIL = re.compile(r"\S+@\S+")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
_PHONE = re.compile(r"(?:\+?1[\s.-]?)?\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
_UNSAFE = re.compile(r"[^\w\s'&+./-]")
_PLACE_UNSAFE = re.compile(r"[^\w\s,.'-]")
_PRICE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?")

# Pages that discuss things rather than sell them.
EXCLUDE_DOMAINS = [
    "reddit.com",
    "quora.com",
    "youtube.com",
    "tiktok.com",
    "instagram.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "pinterest.com",
    "wikipedia.org",
    "medium.com",
    "linkedin.com",
]

# Exa writes one of these per result page (contents.summary.schema).
OFFER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_offer": {
            "type": "boolean",
            "description": "true only if this page itself sells, rents, or offers as a paid "
            "service the thing the shopper wants (not an article, review, list, or forum)",
        },
        "product": {
            "type": "string",
            "description": "short name of the exact product or service offered on this page",
        },
        "price": {
            "type": "number",
            "description": "the main current price as a number, no currency symbol; "
            "omit it if the page shows no price",
        },
        "currency": {"type": "string", "description": "ISO 4217 code of the price, e.g. USD"},
        "price_unit": {
            "type": "string",
            "enum": list(UNITS),
            "description": "what the price covers; each = buying one",
        },
        "offer_type": {"type": "string", "enum": list(OFFER_TYPES)},
        "seller": {"type": "string", "description": "store, brand, or business name"},
        "store_location": {
            "type": "string",
            "description": "town of the physical store or business, if the page names one",
        },
    },
    "required": ["is_offer", "product", "offer_type", "seller"],
}


# ---------------------------------------------------------------- what we send out
def search_words(q: str) -> tuple[str, str | None]:
    """The words to search for (personal details and filler removed) and the parsed category."""
    scrubbed = _PHONE.sub(" ", _URL.sub(" ", _EMAIL.sub(" ", q)))
    parsed = parse_query(scrubbed)
    words = " ".join(_UNSAFE.sub(" ", parsed.text).split())[:100].strip()
    return words, parsed.category


@dataclass(frozen=True)
class Near:
    label: str  # shown to the person
    source: str  # place | device | campus ("dorm" is no longer returned)
    lat: float | None
    lng: float | None
    place: str | None  # typed town/ZIP, used in the query text when there are no coordinates
    cache_part: str
    country: str | None = None  # ISO code, worked out offline; None when we can't tell


def clean_place(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = " ".join(_PLACE_UNSAFE.sub(" ", text).split())[:60].strip(" ,.-")
    return cleaned or None


def _geo(label: str, source: str, lat: float, lng: float) -> Near:
    lat, lng = round(lat, 2), round(lng, 2)  # ~1 km: enough for "nearby", and no closer
    return Near(label, source, lat, lng, None, f"geo:{lat:.2f},{lng:.2f}", country_for(lat, lng))


def resolve_near(viewer: ViewerContext, body: schemas.CommercialSearchBody) -> Near:
    """A typed place wins, then the device's location (when the person allowed it), then campus.

    The dorm is deliberately not used (plans/LOCATION.md): the rule is "you, or campus". The viewer
    stays in the signature so callers don't change.
    """
    place = clean_place(body.place)
    if place:
        return Near(
            place, "place", None, None, place, f"place:{place.lower()}", place_country(place)
        )
    if body.lat is not None and body.lng is not None:
        return _geo("your location", "device", body.lat, body.lng)
    return _geo(
        settings.commercial_default_label,
        "campus",
        settings.commercial_default_lat,
        settings.commercial_default_lng,
    )


def exa_request(words: str, category: str | None, near: Near) -> dict[str, Any]:
    where = "me" if near.lat is not None else near.place
    if category == "services":
        query = f"{words} near {where}: local shop or service with prices"
    else:
        query = f"{words} for sale or rent near {where}: store or rental listing with price"
    request: dict[str, Any] = {
        "query": query,
        "type": settings.exa_search_type,
        "numResults": 10,
        "excludeDomains": EXCLUDE_DOMAINS,
        "moderation": True,
        "contents": {
            "summary": {
                "query": f"The shopper wants: {words}. Does this page itself sell, rent, or "
                "offer (as a paid service) that? Describe the offer.",
                "schema": OFFER_SCHEMA,
            }
        },
    }
    # Exa wants the country with any coordinates. When we can't tell the country (a typed place
    # like "Tokyo", or a spot at sea), leave it out rather than guess: the words do the work.
    if near.country and near.lat is not None and near.lng is not None:
        request["userLocation"] = {
            "country": near.country,
            "latitude": near.lat,
            "longitude": near.lng,
        }
    elif near.country:
        request["userLocation"] = near.country
    return request


# ---------------------------------------------------------------- reading results
def parse_price(value: Any) -> float | None:
    """12.99, "$1,299.00", "25" → a positive number below 100k; anything else → None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        number = float(value)
    elif isinstance(value, str) and (m := _PRICE.search(value)):
        cents = f".{m.group(2)}" if m.group(2) else ""
        number = float(m.group(1).replace(",", "") + cents)
    else:
        return None
    return round(number, 2) if 0 < number < 100_000 else None


def price_text(price: float | None, currency: str | None, unit: str | None) -> str | None:
    if price is None:
        return None
    amount = f"{price:,.2f}".removesuffix(".00")
    symbol = CURRENCY_SYMBOL.get(currency or "USD")
    text = f"{symbol}{amount}" if symbol else f"{amount} {currency}"
    return text if unit in (None, "each") else f"{text}/{unit}"


def _text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    return " ".join(value.split())[:limit].strip() or None


def _web_url(value: Any, *, https_only: bool = False) -> str | None:
    if not isinstance(value, str):
        return None
    url = value.strip()
    parts = urlsplit(url)
    allowed = ("https",) if https_only else ("http", "https")
    if parts.scheme not in allowed or not parts.netloc or len(url) > 2000:
        return None
    return url


def _summary_dict(summary: Any) -> dict[str, Any] | None:
    if isinstance(summary, dict):
        return summary
    if not isinstance(summary, str):
        return None
    for candidate in (summary, summary[summary.find("{") : summary.rfind("}") + 1]):
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    return None


def offer_from_result(
    result: dict[str, Any], default_currency: str = "USD"
) -> schemas.CommercialOffer | None:
    """One Exa result → an offer, or None if the page doesn't actually offer the thing.

    A price with no clear currency is taken to be in the local one (`default_currency`).
    """
    data = _summary_dict(result.get("summary"))
    url = _web_url(result.get("url"))
    if not data or data.get("is_offer") is not True or not url:
        return None
    title = _text(data.get("product"), 140) or _text(result.get("title"), 140)
    if not title:
        return None
    price = parse_price(data.get("price"))
    currency = unit = None
    if price is not None:
        code = _text(data.get("currency"), 3)
        currency = code.upper() if code and len(code) == 3 and code.isalpha() else default_currency
        unit = data.get("price_unit") if data.get("price_unit") in UNITS else "each"
    offer_type = data.get("offer_type") if data.get("offer_type") in OFFER_TYPES else "buy"
    return schemas.CommercialOffer(
        title=title,
        price=price,
        currency=currency,
        price_text=price_text(price, currency, unit),
        price_unit=unit,
        offer_type=offer_type,
        seller=_text(data.get("seller"), 60) or urlsplit(url).netloc.lower().removeprefix("www."),
        location=_text(data.get("store_location"), 60),
        url=url,
        image_url=_web_url(result.get("image"), https_only=True),
    )


def rank(
    offers: list[schemas.CommercialOffer], currency: str = "USD"
) -> list[schemas.CommercialOffer]:
    """Drop duplicates, then cheapest first in the local `currency`.

    No price, or a price in another currency (we don't convert), goes last.
    """
    seen: set[str] = set()
    unique: list[schemas.CommercialOffer] = []
    for offer in offers:
        page = urlsplit(offer.url)._replace(query="", fragment="").geturl().rstrip("/").lower()
        name = f"{offer.seller.lower()}|{offer.title.lower()}"
        if page in seen or name in seen:
            continue
        seen.update((page, name))
        unique.append(offer)
    order = sorted(
        enumerate(unique),
        key=lambda pair: (
            pair[1].price is None,
            pair[1].currency not in (None, currency),
            pair[1].price or 0.0,
            pair[0],  # ties keep the search engine's order
        ),
    )
    return [offer for _, offer in order]


# ---------------------------------------------------------------- providers
class CommercialError(Exception):
    """str(exc) is for logs; user_message is safe to show."""

    def __init__(self, detail: str, status: int, user_message: str):
        super().__init__(detail)
        self.status = status
        self.user_message = user_message


@dataclass
class Found:
    offers: list[schemas.CommercialOffer]
    cost_usd: float


class CommercialProvider(Protocol):
    name: str

    def search(self, words: str, category: str | None, near: Near) -> Found: ...


class ExaProvider:
    name = "exa"

    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._transport = transport

    def search(self, words: str, category: str | None, near: Near) -> Found:
        if not settings.exa_api_key:
            raise CommercialError("EXA_API_KEY is not set", 503, "Store search isn't set up yet")
        with httpx.Client(
            base_url=settings.exa_base_url.rstrip("/"),
            headers={"x-api-key": settings.exa_api_key},
            timeout=httpx.Timeout(10.0, read=float(settings.exa_timeout_s)),
            transport=self._transport,
        ) as client:
            data = self._post(client, exa_request(words, category, near))
        currency = local_currency(near.country)
        results = data.get("results") or []
        offers = [o for r in results if (o := offer_from_result(r, currency))]
        total = (data.get("costDollars") or {}).get("total")
        cost = float(total) if isinstance(total, int | float) and total >= 0 else None
        estimate = settings.commercial_est_cost_usd
        return Found(rank(offers, currency)[:MAX_OFFERS], cost if cost is not None else estimate)

    def _post(self, client: httpx.Client, body: dict[str, Any], retry: bool = True) -> dict:
        try:
            resp = client.post("/search", json=body)
        except httpx.TransportError as exc:
            if retry:
                time.sleep(1.0)
                return self._post(client, body, retry=False)
            raise CommercialError(
                f"exa: {type(exc).__name__}", 502, "Couldn't reach store search — try again"
            ) from exc
        code = resp.status_code
        if code in (429, 502, 503, 504) and retry:
            time.sleep(1.0)
            return self._post(client, body, retry=False)
        if code in (401, 403):
            raise CommercialError(f"exa HTTP {code}", 503, "Store search isn't set up correctly")
        if code == 402:
            raise CommercialError("exa HTTP 402 (no credit)", 503, "Store search is paused")
        if code == 429:
            raise CommercialError("exa HTTP 429", 429, "Store search is busy — try in a minute")
        if code >= 400:
            raise CommercialError(
                f"exa HTTP {code}: {resp.text[:200]}", 502, "Store search didn't work — try again"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise CommercialError("exa: invalid JSON", 502, "Store search didn't work") from exc
        return data if isinstance(data, dict) else {}


class MockProvider:
    """Free, deterministic sample offers on example.com for dev, tests and demos without a key."""

    name = "mock"

    def search(self, words: str, category: str | None, near: Near) -> Found:
        base = 8 + int(hashlib.sha256(words.lower().encode()).hexdigest()[:6], 16) % 60
        thing = words[:1].upper() + words[1:]
        town = near.place or "Palo Alto"
        link = f"https://example.com/search?q={quote(words)}"

        def offer(title, price, seller, *, kind="buy", unit="each", location=town, path="buy"):
            return schemas.CommercialOffer(
                title=title,
                price=price,
                currency="USD",
                price_text=price_text(price, "USD", unit),
                price_unit=unit,
                offer_type=kind,
                seller=seller,
                location=location,
                url=f"{link}&offer={path}",
                image_url=None,
            )

        if category == "services":
            offers = [
                offer(f"{thing} (walk-in)", base + 15.0, "Sample Repair Shop", kind="service"),
                offer(f"{thing}, by the hour", 25.0, "Sample Pro", kind="service", unit="hour"),
            ]
        else:
            offers = [
                offer(f"{thing} (new)", base + 0.99, "Sample Store"),
                offer(
                    f"{thing} (used, good)",
                    round(base * 0.55, 2),
                    "Sample Marketplace",
                    path="used",
                ),
                offer(
                    f"{thing} rental",
                    max(3.0, round(base * 0.15, 2)),
                    "Sample Rentals",
                    kind="rent",
                    unit="day",
                    path="rent",
                ),
                offer(
                    f"{thing} (ships in 2 days)",
                    base + 6.49,
                    "Sample Online Shop",
                    location=None,
                    path="online",
                ),
            ]
        return Found(rank(offers), 0.0)


def get_provider(name: str) -> CommercialProvider:
    if name == "exa":
        return ExaProvider()
    return MockProvider()


# ---------------------------------------------------------------- cache, limits, log
def cache_key(provider: str, words: str, near: Near) -> str:
    digest = hashlib.sha256(f"{words.lower()}|{near.cache_part}".encode()).hexdigest()
    return f"{CACHE_VERSION}:{provider}:{digest}"


def cache_get(db: Session, key: str) -> tuple[list[schemas.CommercialOffer], datetime] | None:
    row = db.get(AICache, key)
    if row is None or not isinstance(row.value, dict):
        return None
    try:
        fetched_at = datetime.fromisoformat(row.value["fetched_at"])
        offers = [schemas.CommercialOffer.model_validate(o) for o in row.value["offers"]]
    except (KeyError, TypeError, ValueError):
        return None
    if datetime.now(UTC) - fetched_at > timedelta(hours=settings.commercial_cache_hours):
        return None
    return offers, fetched_at


def cache_put(
    db: Session, key: str, offers: list[schemas.CommercialOffer], fetched_at: datetime
) -> None:
    value = {"offers": [o.model_dump() for o in offers], "fetched_at": fetched_at.isoformat()}
    stmt = insert(AICache).values(key=key, value=value)
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=[AICache.key],
            set_={"value": stmt.excluded.value, "created_at": func.now()},
        )
    )


def check_limits(db: Session, user_id: int) -> None:
    """429 at the per-person daily cap or the monthly budget (only uncached lookups count)."""
    since = datetime.now(UTC) - timedelta(hours=24)
    used = db.scalar(
        select(func.count())
        .select_from(Event)
        .where(
            Event.type == EVENT_TYPE,
            Event.user_id == user_id,
            Event.created_at >= since,
            Event.payload["cached"].as_boolean().is_(False),
        )
    )
    if (used or 0) >= settings.commercial_daily_lookups_per_user:
        raise HTTPException(429, "You've hit today's store-search limit — try again tomorrow")
    month = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    spent = db.scalar(
        select(func.coalesce(func.sum(Event.payload["cost_usd"].as_float()), 0.0)).where(
            Event.type == EVENT_TYPE, Event.created_at >= month
        )
    )
    if float(spent or 0.0) + settings.commercial_est_cost_usd > settings.commercial_budget_usd:
        raise HTTPException(429, "Store search is paused for this month")


def commercial_search(
    db: Session, viewer: ViewerContext, body: schemas.CommercialSearchBody
) -> schemas.CommercialSearchResponse:
    provider = settings.commercial_provider.strip().lower()
    if provider not in ("mock", "exa"):
        raise HTTPException(503, "Store search is turned off")
    words, category = search_words(body.q)
    if len(words) < 2:
        raise HTTPException(400, "Search for a specific thing to compare stores")
    near = resolve_near(viewer, body)
    key = cache_key(provider, words, near)
    start = time.monotonic()
    hit = cache_get(db, key)
    if hit:
        offers, fetched_at = hit
        cost, cached = 0.0, True
    else:
        if provider != "mock":
            check_limits(db, viewer.user_id)
        db.commit()  # don't hold a transaction open during the web call
        try:
            found = get_provider(provider).search(words, category, near)
        except CommercialError as exc:
            log.warning("commercial search failed: %s", exc)
            raise HTTPException(exc.status, exc.user_message) from exc
        offers, cost, cached = found.offers, found.cost_usd, False
        fetched_at = datetime.now(UTC)
        cache_put(db, key, offers, fetched_at)
    db.add(
        Event(
            user_id=viewer.user_id,
            type=EVENT_TYPE,
            payload={
                "provider": provider,
                "cached": cached,
                "results": len(offers),
                "cost_usd": round(cost, 4),
                "near": near.source,  # the kind of location only, never where
                "latency_ms": int((time.monotonic() - start) * 1000),
            },
        )
    )
    db.commit()
    return schemas.CommercialSearchResponse(
        query=words,
        near=near.label,
        near_source=near.source,
        offers=offers,
        provider=provider,
        cached=cached,
        fetched_at=fetched_at,
    )
