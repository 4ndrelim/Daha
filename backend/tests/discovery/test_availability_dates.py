"""Availability dates on items (docs/plans/availability-dates.md).

`available_from` / `available_until` are campus calendar days, both optional, both inclusive.
An item that isn't out yet is shown with its date; one past its "until" date is gone.
"""

from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.core.geo import campus_today
from app.models import Item
from app.services import availability
from tests.discovery.helpers import item, names, request, search, world
from tests.discovery.test_mutual import opt_in, pairs


def day(offset: int) -> str:
    return (campus_today() + timedelta(days=offset)).isoformat()


def end(db, item_id: int, days_ago: int = 1) -> None:
    """Make an item's last day pass (the API refuses a past "until" date, as it should)."""
    it = db.get(Item, item_id)
    it.available_from, it.available_until = None, campus_today() - timedelta(days=days_ago)
    db.commit()


# ---------------------------------------------------------------- the rules themselves
def test_window_and_messages():
    today = date(2026, 11, 19)
    it = Item(name="Tent", available_from=date(2026, 11, 21), available_until=date(2026, 11, 23))
    assert availability.window(it, today) == "upcoming"
    assert availability.window(it, date(2026, 11, 21)) == "now"  # both ends are inclusive
    assert availability.window(it, date(2026, 11, 23)) == "now"
    assert availability.window(it, date(2026, 11, 24)) == "ended"
    assert availability.window(Item(name="Anytime"), today) == "now"
    assert availability.nice(date(2026, 11, 21)) == "Sat 21 Nov"

    problem = availability.borrow_problem
    assert "available from Sat 21 Nov" in problem(it, None, None, today)
    assert problem(it, date(2026, 11, 21), date(2026, 11, 23), today) is None
    assert "back by Mon 23 Nov" in problem(it, date(2026, 11, 22), date(2026, 11, 25), today)
    assert "only available until Mon 23 Nov" in problem(it, date(2026, 11, 24), None, today)
    assert "was only available until" in problem(it, None, None, date(2026, 11, 30))
    assert problem(Item(name="Anytime"), None, date(2027, 1, 1), today) is None


def test_today_is_the_campus_day_not_the_servers(monkeypatch):
    assert settings.campus_tz == "America/Los_Angeles"
    from datetime import datetime
    from zoneinfo import ZoneInfo

    assert campus_today() == datetime.now(ZoneInfo("America/Los_Angeles")).date()


# ---------------------------------------------------------------- listing and editing
def test_dates_are_saved_shown_on_cards_and_validated(client, db):
    w = world(client, db)
    made = item(client, w.wilbur, "Ski jacket", available_from=day(2), available_until=day(9))
    assert (made["available_from"], made["available_until"]) == (day(2), day(9))
    assert made["available_now"] is False
    assert search(client, w.flomo, "ski jacket")["items"] == []  # "available only" is the default
    card = search(client, w.flomo, "ski jacket", available_only="false")["items"][0]
    assert card["available_from"] == day(2) and card["available_now"] is False
    assert f"From {availability.nice(campus_today() + timedelta(days=2))}" in card["match_reason"]

    anytime = item(client, w.wilbur, "Kettle")
    assert anytime["available_now"] is True and anytime["available_from"] is None

    def post(**kw):
        body = {"name": "X", "category": "other", "transaction_type": "lend"}
        body["visibility"] = "campus"
        return client.post("/api/items", headers=w.wilbur, json={**body, **kw})

    assert post(available_from=day(5), available_until=day(1)).status_code == 400
    past = post(available_until=day(-1))
    assert past.status_code == 400 and "already passed" in past.json()["detail"]
    assert post(available_from=day(0), available_until=day(0)).status_code == 201  # today only

    url = f"/api/items/{made['id']}"
    edited = client.patch(url, headers=w.wilbur, json={"available_from": None})
    assert edited.status_code == 200 and edited.json()["available_now"] is True
    assert client.patch(url, headers=w.wilbur, json={"available_until": day(-2)}).status_code == 400
    # An old item whose dates have passed can still be edited in other ways, and re-opened.
    end(db, made["id"])
    assert client.patch(url, headers=w.wilbur, json={"name": "Ski jacket (M)"}).status_code == 200
    reopened = client.patch(url, headers=w.wilbur, json={"available_until": None})
    assert reopened.status_code == 200 and reopened.json()["available_now"] is True


# ---------------------------------------------------------------- search and feeds
def test_search_hides_ended_and_upcoming_items_unless_asked(client, db):
    w = world(client, db)
    item(client, w.wilbur, "Camping stove", available_from=day(8))
    today = campus_today()
    saturday = today if today.weekday() == 6 else today + timedelta(days=5 - today.weekday())
    boxes = item(client, w.wilbur, "Rooftop cargo box", available_from=saturday.isoformat())
    item(client, w.wilbur2, "Camping stove two burner")
    gone = item(client, w.wilbur, "Camping stove old")
    end(db, gone["id"])

    assert names(search(client, w.flomo, "camping stove")) == ["Camping stove two burner"]
    everything = search(client, w.flomo, "camping stove", available_only="false")
    assert names(everything) == ["Camping stove two burner", "Camping stove"]  # never the old one
    assert names(search(client, w.flomo, "")) == ["Camping stove two burner"]  # browsing

    # Asking for dates still works: an item that starts on that day is a real answer.
    dated = search(client, w.flomo, "rooftop cargo box this weekend")
    assert boxes["id"] in [i["id"] for i in dated["items"]]

    home = client.get("/api/feed/home", headers=w.flomo).json()
    assert "Camping stove old" not in str(home)


# ---------------------------------------------------------------- matching
def matches(client, headers, rid) -> list[str]:
    r = client.get(f"/api/requests/{rid}/matches", headers=headers)
    assert r.status_code == 200, r.text
    return [i["name"] for i in r.json()["items"]]


def test_matching_only_offers_items_available_on_the_days_asked_for(client, db):
    w = world(client, db)
    item(client, w.wilbur, "Black binder", category="academic")
    item(client, w.wilbur2, "Black binder with tabs", category="academic", available_from=day(5))
    gone = item(client, w.wilbur2, "Black binder old", category="academic")
    end(db, gone["id"])

    now = request(client, w.flomo, "need a black binder", title="Binder", item_name="black binder")
    assert matches(client, w.flomo, now["id"]) == ["Black binder"]  # no dates = needed now

    next_week = request(
        client, w.flomo, "need a black binder next week", title="Binder later",
        item_name="black binder", needed_from=day(5), needed_until=day(7),
    )  # fmt: skip
    assert set(matches(client, w.flomo, next_week["id"])) == {
        "Black binder",
        "Black binder with tabs",
    }

    # "You could help" for the lender follows the same rule.
    could = client.get("/api/feed/home", headers=w.wilbur2).json()
    helped = {f["request"]["id"] for f in could.get("fulfillable", [])}
    assert now["id"] not in helped


def test_an_item_listed_after_the_request_is_matched_by_the_same_rule(client, db):
    w = world(client, db)
    now = request(client, w.flomo, "need a black binder", title="Binder", item_name="black binder")
    item(client, w.wilbur, "Black binder later", category="academic", available_from=day(6))
    item(client, w.wilbur2, "Black binder", category="academic")
    assert matches(client, w.flomo, now["id"]) == ["Black binder"]


def test_mutual_matching_ignores_items_outside_their_dates(client, db, monkeypatch):
    monkeypatch.setattr(settings, "mutual_matching", "rules")
    w = world(client, db)
    tent = item(client, w.wilbur, "Camping tent", category="sports")
    item(client, w.flomo, "Large suitcase", category="moving")
    request(client, w.flomo, "anyone have a camping tent?", title="Tent", item_name="camping tent")
    request(client, w.wilbur, "need a large suitcase", title="Suitcase", item_name="large suitcase")
    opt_in(client, w.wilbur, w.flomo)
    assert len(pairs(client, w.wilbur)) == 1

    url = f"/api/items/{tent['id']}"
    assert client.patch(url, headers=w.wilbur, json={"available_from": day(3)}).status_code == 200
    assert pairs(client, w.wilbur) == [] and pairs(client, w.flomo) == []
    assert client.patch(url, headers=w.wilbur, json={"available_from": None}).status_code == 200
    assert len(pairs(client, w.wilbur)) == 1


# ---------------------------------------------------------------- borrowing
@pytest.mark.parametrize(
    ("body", "status", "says"),
    [
        ({}, 409, "is available from"),  # asking for it now, before it is out
        ({"start_date": 1}, 409, "is available from"),
        ({"start_date": 3, "due_date": 5}, 201, None),  # inside the dates
        ({"start_date": 3, "due_date": 12}, 409, "needs to be back by"),
        ({"start_date": 11}, 409, "is only available until"),
    ],
)
def test_borrow_requests_outside_the_dates_are_refused_with_a_reason(
    client, db, body, status, says
):
    w = world(client, db)
    made = item(client, w.wilbur, "Ski jacket", available_from=day(3), available_until=day(9))
    detail = client.get(f"/api/items/{made['id']}", headers=w.flomo).json()
    assert detail["can_borrow"] is True and detail["available_now"] is False  # can ask ahead
    sent = {k: day(v) for k, v in body.items()}
    r = client.post(f"/api/items/{made['id']}/borrow", headers=w.flomo, json=sent)
    assert r.status_code == status, r.text
    if says:
        assert says in r.json()["detail"] and "Ski jacket" in r.json()["detail"]


def test_an_ended_item_cannot_be_borrowed(client, db):
    w = world(client, db)
    made = item(client, w.wilbur, "Hand truck")
    end(db, made["id"])
    detail = client.get(f"/api/items/{made['id']}", headers=w.flomo).json()
    assert detail["can_borrow"] is False and detail["available_now"] is False
    r = client.post(f"/api/items/{made['id']}/borrow", headers=w.flomo, json={})
    assert r.status_code == 409 and "was only available until" in r.json()["detail"]


def test_scan_review_can_set_the_dates_for_everything_it_publishes(client, db):
    from tests.ai.test_scans import _scan, user_in_wilbur

    headers, _ = user_in_wilbur(client, db)
    scan = _scan(client, headers, [1])
    det = scan["detections"][0]
    one = {
        "detection_id": det["id"],
        "name": det["name"],
        "category": det["category"],
        "transaction_type": "give",
        "visibility": "campus",
        "available_from": day(3),
        "available_until": day(10),
    }
    url = f"/api/scans/{scan['id']}/publish"
    past = {**one, "available_from": None, "available_until": day(-1)}
    late = client.post(url, headers=headers, json={"items": [past]})
    assert late.status_code == 400 and "already passed" in late.json()["detail"]
    made = client.post(url, headers=headers, json={"items": [one]}).json()["items"][0]
    assert (made["available_from"], made["available_until"]) == (day(3), day(10))
    assert made["available_now"] is False
