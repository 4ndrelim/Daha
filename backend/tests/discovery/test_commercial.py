"""Buy or rent nearby (C6): what we send to Exa, how results are read and ranked, and the API.

The first half needs no database; the API half uses the test database like every other test.
"""

import json

import httpx
import pytest
import respx
from sqlalchemy import select

from app import schemas
from app.core.config import settings
from app.discovery import commercial as c
from app.discovery import countries
from app.models import AICache, Event
from app.services.viewer import ViewerContext
from tests.core.factories import community_id, seed_base, signup

EXA = "https://exa.test"
WILBUR = ViewerContext(1, 2, "Wilbur Hall", 37.42402, -122.16308, frozenset({1, 2}), 10)
NO_DORM = ViewerContext(1, None, None, None, None, frozenset({1}), 10)


def body(**kw) -> schemas.CommercialSearchBody:
    return schemas.CommercialSearchBody(q=kw.pop("q", "graphing calculator"), **kw)


def result(url="https://store.test/p/1", **summary) -> dict:
    data = {"is_offer": True, "product": "TI-84 Plus CE", "offer_type": "buy", "seller": "Store"}
    data.update(summary)
    return {"url": url, "title": "Page title", "summary": json.dumps(data)}


# ---------------------------------------------------------------- what leaves our server
def test_search_words_drop_filler_and_personal_details():
    words, category = c.search_words(
        "anyone have a graphing calculator near me? text 650-555-1234 or me@stanford.edu"
    )
    assert "graphing calculator" in words and category == "academic"
    assert "650" not in words and "@" not in words and "stanford" not in words
    assert c.search_words("check https://example.com/x hdmi cable")[0] == "check hdmi cable"
    assert c.search_words("MacBook Air A1466 2017 charger")[0] == "MacBook Air A1466 2017 charger"


def test_near_prefers_typed_place_then_device_then_campus():
    place = c.resolve_near(WILBUR, body(place=" Mountain View, CA <script> ", lat=1.0, lng=2.0))
    assert (place.source, place.label, place.lat) == ("place", "Mountain View, CA script", None)
    device = c.resolve_near(WILBUR, body(lat=37.386052, lng=-122.083851))
    assert (device.source, device.lat, device.lng) == ("device", 37.39, -122.08)  # ~1 km only
    campus = c.resolve_near(NO_DORM, body())
    assert (campus.source, campus.label) == ("campus", "Stanford campus")
    assert (campus.lat, campus.lng) == (37.43, -122.17)


def test_near_ignores_the_dorm_when_no_coordinates_are_sent():
    near = c.resolve_near(WILBUR, body())  # has a dorm with coordinates, sends none
    assert (near.source, near.label) == ("campus", "Stanford campus")
    assert (near.lat, near.lng) == (37.43, -122.17)  # campus, not Wilbur's 37.42, -122.16
    assert near == c.resolve_near(NO_DORM, body())
    half = c.resolve_near(WILBUR, body(lat=37.386052))  # one coordinate alone is not a location
    assert half.source == "campus"


def test_exa_request_with_coordinates_asks_for_near_me():
    sent = c.exa_request("graphing calculator", "academic", c.resolve_near(WILBUR, body()))
    assert "near me" in sent["query"] and "graphing calculator" in sent["query"]
    # no coordinates sent → campus, not the dorm (plans/LOCATION.md)
    assert sent["userLocation"] == {"country": "US", "latitude": 37.43, "longitude": -122.17}
    device = c.resolve_near(WILBUR, body(lat=37.386052, lng=-122.083851))
    assert c.exa_request("graphing calculator", "academic", device)["userLocation"] == {
        "country": "US",
        "latitude": 37.39,
        "longitude": -122.08,
    }
    assert sent["numResults"] == 10 and sent["moderation"] is True
    assert "reddit.com" in sent["excludeDomains"]
    assert sent["contents"]["summary"]["schema"]["required"][0] == "is_offer"
    assert "Wilbur" not in json.dumps(sent)  # the dorm name never leaves


def test_exa_request_with_a_typed_place_and_a_service():
    near = c.resolve_near(WILBUR, body(place="94040"))
    sent = c.exa_request("repair bike", "services", near)
    assert sent["userLocation"] == "US"
    assert "near 94040" in sent["query"] and "service" in sent["query"]


# ---------------------------------------------------------------- country and currency
@pytest.mark.parametrize(
    ("lat", "lng", "country"),
    [
        (37.43, -122.17, "US"),  # Stanford
        (37.87, -122.26, "US"),  # Berkeley
        (42.36, -71.09, "US"),  # MIT
        (21.30, -157.82, "US"),  # Honolulu
        (43.66, -79.40, "CA"),  # Toronto
        (51.51, -0.13, "GB"),  # London
        (1.30, 103.85, "SG"),  # Singapore
        (35.68, 139.76, "JP"),  # Tokyo
        (0.0, -160.0, None),  # the middle of the Pacific
    ],
)
def test_country_comes_from_the_coordinates_offline(lat, lng, country):
    assert countries.country_for(lat, lng) == country


@pytest.mark.parametrize(
    ("place", "country"),
    [
        ("94040", "US"),
        ("Berkeley, CA", "US"),
        ("Austin TX", "US"),
        ("Mountain View, California", "US"),
        ("Cambridge, UK", "GB"),
        ("Kyoto, Japan", "JP"),
        ("Singapore", "SG"),
        ("Tokyo", None),  # can't tell: the words in the query do the work
        ("Palo Alto", None),
    ],
)
def test_country_of_a_typed_place(place, country):
    assert countries.place_country(place) == country


def test_exa_request_sends_the_real_country():
    campus = c.exa_request("tent", None, c.resolve_near(NO_DORM, body()))
    assert campus["userLocation"]["country"] == "US"
    singapore = c.resolve_near(NO_DORM, body(lat=1.3005, lng=103.8501))
    sent = c.exa_request("tent", None, singapore)
    assert sent["userLocation"] == {"country": "SG", "latitude": 1.3, "longitude": 103.85}
    assert (
        c.exa_request("tent", None, c.resolve_near(NO_DORM, body(place="Kyoto, Japan")))[
            "userLocation"
        ]
        == "JP"
    )
    unknown = c.exa_request("tent", None, c.resolve_near(NO_DORM, body(place="Tokyo")))
    assert "userLocation" not in unknown and "near Tokyo" in unknown["query"]


def test_prices_rank_and_show_in_the_local_currency():
    results = [
        result("https://a.test/1", product="Tent A", price=30, currency="USD", seller="A"),
        result("https://b.test/1", product="Tent B", price=120, currency="SGD", seller="B"),
        result("https://c.test/1", product="Tent C", price=45, seller="C"),  # no currency given
    ]
    offers = c.rank([o for r in results if (o := c.offer_from_result(r, "SGD"))], "SGD")
    assert [o.title for o in offers] == ["Tent C", "Tent B", "Tent A"]  # SGD first, USD last
    assert (offers[0].currency, offers[0].price_text) == ("SGD", "S$45")
    assert c.price_text(1200.0, "JPY", "each") == "¥1,200"
    assert countries.local_currency("JP") == "JPY" and countries.local_currency(None) == "USD"


@respx.mock
def test_exa_provider_ranks_in_the_local_currency(exa_settings):
    respx.post(f"{EXA}/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    result("https://a.test/1", product="Desk lamp A", price=25, currency="USD"),
                    result("https://b.test/1", product="Desk lamp B", price=39),
                ]
            },
        )
    )
    tokyo = c.resolve_near(NO_DORM, body(lat=35.68, lng=139.76))
    found = c.ExaProvider().search("desk lamp", "dorm", tokyo)
    assert [(o.title, o.currency) for o in found.offers] == [
        ("Desk lamp B", "JPY"),
        ("Desk lamp A", "USD"),
    ]


# ---------------------------------------------------------------- reading what comes back
@pytest.mark.parametrize(
    ("raw", "price"),
    [
        (12.99, 12.99),
        ("$1,299.00", 1299.0),
        ("25", 25.0),
        ("from $7.5 a day", 7.5),
        (0, None),
        (-3, None),
        (True, None),
        ("free", None),
        (10**6, None),
        (None, None),
    ],
)
def test_parse_price(raw, price):
    assert c.parse_price(raw) == price


def test_price_text():
    assert c.price_text(12.0, "USD", "each") == "$12"
    assert c.price_text(1299.5, "USD", "each") == "$1,299.50"
    assert c.price_text(15.0, "USD", "day") == "$15/day"
    assert c.price_text(9.0, "SEK", "each") == "9 SEK"  # no symbol: amount + code
    assert c.price_text(None, None, None) is None


def test_results_become_offers_cheapest_first():
    results = [
        result("https://a.test/1", product="Calculator A", price=99.99, seller="A"),
        result("https://b.test/1", product="Calculator B", price="$14.50", seller="B"),
        result("https://c.test/1", product="Calculator C", seller="C"),  # no price → last
        result("https://d.test/1", product="Calculator D", price=10, currency="EUR", seller="D"),
        result("https://e.test/1", product="Rental", price=5, price_unit="day", offer_type="rent"),
        result("https://f.test/1", is_offer=False, price=1),  # an article, not an offer
        {"url": "https://g.test/1", "summary": "not json at all"},
        result("javascript:alert(1)", price=2),  # unsafe link
        result("https://b.test/1?utm=x", product="Calculator B", price=14.5, seller="B"),  # dup
    ]
    offers = c.rank([o for r in results if (o := c.offer_from_result(r))])
    assert [o.title for o in offers] == [
        "Rental",
        "Calculator B",
        "Calculator A",
        "Calculator D",
        "Calculator C",
    ]
    rental = offers[0]
    assert (rental.offer_type, rental.price_unit, rental.price_text) == ("rent", "day", "$5/day")
    assert offers[1].currency == "USD" and offers[-1].price is None


def test_summary_wrapped_in_prose_and_missing_seller():
    raw = {
        "url": "https://www.bestbuy.test/site/x",
        "image": "http://insecure.test/img.jpg",
        "summary": 'Here you go: {"is_offer": true, "product": "USB-C charger", "price": 19}',
    }
    offer = c.offer_from_result(raw)
    assert offer is not None
    assert (offer.seller, offer.price_text, offer.offer_type) == ("bestbuy.test", "$19", "buy")
    assert offer.image_url is None  # only https images


# ---------------------------------------------------------------- the Exa client
@pytest.fixture
def exa_settings(monkeypatch):
    monkeypatch.setattr(settings, "exa_base_url", EXA)
    monkeypatch.setattr(settings, "exa_api_key", "exa-secret-key")
    monkeypatch.setattr(c.time, "sleep", lambda s: None)


@respx.mock
def test_exa_provider_sends_the_key_only_in_the_header(exa_settings):
    route = respx.post(f"{EXA}/search").mock(
        return_value=httpx.Response(
            200,
            json={"results": [result(price=21.0)], "costDollars": {"total": 0.016}},
        )
    )
    found = c.ExaProvider().search(
        "graphing calculator", "academic", c.resolve_near(WILBUR, body())
    )
    assert [o.price for o in found.offers] == [21.0] and found.cost_usd == 0.016
    request = route.calls[0].request
    assert request.headers["x-api-key"] == "exa-secret-key"
    assert "exa-secret-key" not in request.content.decode()


@respx.mock
def test_exa_provider_retries_once_then_maps_errors(exa_settings):
    near = c.resolve_near(WILBUR, body())
    respx.post(f"{EXA}/search").mock(
        side_effect=[httpx.Response(502), httpx.Response(200, json={"results": []})]
    )
    found = c.ExaProvider().search("tent", None, near)
    assert found.offers == [] and found.cost_usd == settings.commercial_est_cost_usd

    respx.post(f"{EXA}/search").mock(return_value=httpx.Response(429))
    with pytest.raises(c.CommercialError) as busy:
        c.ExaProvider().search("tent", None, near)
    assert busy.value.status == 429

    respx.post(f"{EXA}/search").mock(return_value=httpx.Response(401, text="bad key"))
    with pytest.raises(c.CommercialError) as refused:
        c.ExaProvider().search("tent", None, near)
    assert refused.value.status == 503 and "set up" in refused.value.user_message


def test_exa_provider_without_a_key(monkeypatch):
    monkeypatch.setattr(settings, "exa_api_key", "")
    with pytest.raises(c.CommercialError) as exc:
        c.ExaProvider().search("tent", None, c.resolve_near(WILBUR, body()))
    assert exc.value.status == 503


def test_mock_provider_is_free_labeled_and_sorted():
    near = c.resolve_near(WILBUR, body())
    first = c.MockProvider().search("desk lamp", "dorm", near)
    again = c.MockProvider().search("desk lamp", "dorm", near)
    assert first == again and first.cost_usd == 0.0
    assert all(o.url.startswith("https://example.com/") for o in first.offers)
    prices = [o.price for o in first.offers]
    assert prices == sorted(prices)


# ---------------------------------------------------------------- the API (test database)
class FakePaid:
    """Stands in for Exa: counts calls, costs money."""

    name = "exa"

    def __init__(self):
        self.calls = 0

    def search(self, words, category, near):
        self.calls += 1
        offer = c.MockProvider().search(words, category, near).offers[0]
        return c.Found([offer], 0.02)


@pytest.fixture
def paid(monkeypatch):
    fake = FakePaid()
    monkeypatch.setattr(settings, "commercial_provider", "exa")
    monkeypatch.setattr(c, "get_provider", lambda name: fake)
    return fake


def wilbur_user(client, db):
    seed_base(db)
    headers, _ = signup(client, "Sam", dorm_id=community_id(db, "wilbur"))
    return headers


def lookup_events(db) -> list[Event]:
    return list(db.scalars(select(Event).where(Event.type == c.EVENT_TYPE).order_by(Event.id)))


def test_api_mock_offers_near_campus_for_a_user_with_a_dorm(client, db, monkeypatch):
    monkeypatch.setattr(settings, "commercial_provider", "mock")
    headers = wilbur_user(client, db)
    r = client.post("/api/search/commercial", headers=headers, json={"q": "desk lamp near me"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert (data["query"], data["near"], data["near_source"]) == (
        "desk lamp",
        "Stanford campus",
        "campus",
    )
    assert data["provider"] == "mock" and data["cached"] is False
    prices = [o["price"] for o in data["offers"]]
    assert prices == sorted(prices) and data["fetched_at"].endswith("Z")


def test_api_caches_per_words_and_area(client, db, paid):
    headers = wilbur_user(client, db)
    first = client.post("/api/search/commercial", headers=headers, json={"q": "camping tent"})
    again = client.post("/api/search/commercial", headers=headers, json={"q": "camping tent?"})
    elsewhere = client.post(
        "/api/search/commercial", headers=headers, json={"q": "camping tent", "place": "Oakland"}
    )
    assert [r.json()["cached"] for r in (first, again, elsewhere)] == [False, True, False]
    assert paid.calls == 2
    assert [e.payload["cost_usd"] for e in lookup_events(db)] == [0.02, 0.0, 0.02]


def test_api_daily_cap_and_monthly_budget(client, db, paid, monkeypatch):
    headers = wilbur_user(client, db)
    monkeypatch.setattr(settings, "commercial_daily_lookups_per_user", 1)
    assert (
        client.post("/api/search/commercial", headers=headers, json={"q": "tent"}).status_code
        == 200
    )
    capped = client.post("/api/search/commercial", headers=headers, json={"q": "kayak"})
    assert capped.status_code == 429 and "today" in capped.json()["detail"]
    cached = client.post("/api/search/commercial", headers=headers, json={"q": "tent"})
    assert cached.status_code == 200  # cache hits are free and never capped

    monkeypatch.setattr(settings, "commercial_daily_lookups_per_user", 50)
    monkeypatch.setattr(settings, "commercial_budget_usd", 0.03)
    broke = client.post("/api/search/commercial", headers=headers, json={"q": "kayak"})
    assert broke.status_code == 429 and "month" in broke.json()["detail"]
    assert paid.calls == 1


def test_api_never_stores_coordinates(client, db, paid):
    headers = wilbur_user(client, db)
    r = client.post(
        "/api/search/commercial",
        headers=headers,
        json={"q": "bike lock", "lat": 37.386052, "lng": -122.083851},
    )
    assert r.json()["near_source"] == "device" and r.json()["near"] == "your location"
    stored = json.dumps([e.payload for e in lookup_events(db)]) + json.dumps(
        [(row.key, row.value) for row in db.scalars(select(AICache))]
    )
    assert "37.38" not in stored and "37.39" not in stored and "122.08" not in stored


def test_api_off_vague_and_logged_out(client, db, monkeypatch):
    headers = wilbur_user(client, db)
    vague = client.post("/api/search/commercial", headers=headers, json={"q": "anyone have?"})
    assert vague.status_code == 400
    assert client.post("/api/search/commercial", json={"q": "tent"}).status_code == 401
    monkeypatch.setattr(settings, "commercial_provider", "off")
    off = client.post("/api/search/commercial", headers=headers, json={"q": "tent"})
    assert off.status_code == 503


def test_api_provider_failure_is_friendly_and_free(client, db, monkeypatch):
    headers = wilbur_user(client, db)

    class Broken:
        name = "exa"

        def search(self, *args):
            raise c.CommercialError("exa HTTP 401", 503, "Store search isn't set up correctly")

    monkeypatch.setattr(settings, "commercial_provider", "exa")
    monkeypatch.setattr(c, "get_provider", lambda name: Broken())
    r = client.post("/api/search/commercial", headers=headers, json={"q": "tent"})
    assert r.status_code == 503 and r.json()["detail"] == "Store search isn't set up correctly"
    assert lookup_events(db) == []  # nothing spent, nothing logged
