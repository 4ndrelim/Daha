"""C5: private "I have this" items and anonymous pings."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import Notification, RequestMatch
from tests.discovery.helpers import item, request, search, world
from tests.discovery.test_matching import matches, notes

PUMP_Q = "anyone have a bike pump?"


def test_private_item_gets_anonymous_ping_and_stays_hidden(client, db):
    w = world(client, db)
    pump = item(client, w.wilbur2, "Bike pump", "private", category="sports")
    req = request(client, w.flomo, PUMP_Q, title="Bike pump", item_name="bike pump")
    (ping,) = notes(db, w.wilbur2_me["id"], "private_match")
    assert ping.link == f"/requests/{req['id']}?offer_item={pump['id']}"
    assert ping.actor_id is None and "won't know it's you" in ping.body
    assert notes(db, w.wilbur2_me["id"], "match") == []

    mine = matches(client, w.flomo, req["id"])
    assert mine["items"] == [] and mine["private_pinged_count"] == 1
    assert matches(client, w.wilbur, req["id"])["private_pinged_count"] == 0  # not the requester
    assert client.get(f"/api/requests/{req['id']}", headers=w.flomo).json()["match_count"] == 0
    # Never in search, feeds, profiles, or by URL.
    for viewer in (w.flomo, w.wilbur):
        assert search(client, viewer, "bike pump")["items"] == []
        assert client.get(f"/api/items/{pump['id']}", headers=viewer).status_code == 404
    feed = client.get("/api/feed/home", headers=w.flomo).json()
    assert all(i["id"] != pump["id"] for i in feed["new_nearby"])
    prof = client.get(f"/api/users/{w.wilbur2_me['id']}/items", headers=w.flomo).json()
    assert prof["items"] == []


def test_owner_sees_own_private_item_in_fulfillable(client, db):
    w = world(client, db)
    item(client, w.wilbur2, "Bike pump", "private", category="sports")
    req = request(client, w.flomo, PUMP_Q, title="Bike pump", item_name="bike pump")
    body = client.get("/api/me/fulfillable", headers=w.wilbur2).json()
    assert [f["request"]["id"] for f in body] == [req["id"]]
    assert body[0]["my_matching_items"][0]["visibility"] == "private"
    home = client.get("/api/feed/home", headers=w.wilbur2).json()
    assert [f["request"]["id"] for f in home["you_can_help"]] == [req["id"]]


def test_one_ping_per_request_and_three_per_day(client, db):
    w = world(client, db)
    item(client, w.wilbur2, "Bike pump", "private", category="sports")
    reqs = [
        request(client, w.flomo, PUMP_Q, title="Bike pump", item_name="bike pump") for _ in range(4)
    ]
    assert len(notes(db, w.wilbur2_me["id"], "private_match")) == 3
    client.patch(f"/api/requests/{reqs[0]['id']}", headers=w.flomo, json={"title": "Bike pump pls"})
    assert len(notes(db, w.wilbur2_me["id"], "private_match")) == 3
    # The 4th request stored the match but didn't ping (cap), so its count is 0.
    assert matches(client, w.flomo, reqs[3]["id"])["private_pinged_count"] == 0
    # A day later the cap resets.
    db.execute(
        Notification.__table__.update().values(created_at=datetime.now(UTC) - timedelta(hours=25))
    )
    db.commit()
    client.patch(f"/api/requests/{reqs[3]['id']}", headers=w.flomo, json={"title": "Bike pump?"})
    assert len(notes(db, w.wilbur2_me["id"], "private_match")) == 4
    assert matches(client, w.flomo, reqs[3]["id"])["private_pinged_count"] == 1


def test_pings_disabled_are_skipped(client, db):
    w = world(client, db)
    item(client, w.wilbur2, "Bike pump", "private", category="sports", pings_enabled=False)
    req = request(client, w.flomo, PUMP_Q, title="Bike pump", item_name="bike pump")
    assert notes(db, w.wilbur2_me["id"], "private_match") == []
    assert db.scalars(select(RequestMatch).where(RequestMatch.request_id == req["id"])).all() == []


def test_offer_with_private_item_reveals_owner_only_through_offer(client, db):
    w = world(client, db)
    pump = item(client, w.wilbur2, "Bike pump", "private", category="sports")
    req = request(client, w.flomo, PUMP_Q, title="Bike pump", item_name="bike pump")
    r = client.post(
        f"/api/requests/{req['id']}/offers",
        headers=w.wilbur2,
        json={"item_id": pump["id"], "message": "I have one!"},
    )
    assert r.status_code == 201, r.text
    detail = client.get(f"/api/requests/{req['id']}", headers=w.flomo).json()
    assert [o["owner"]["id"] for o in detail["offers"]] == [w.wilbur2_me["id"]]
    assert matches(client, w.flomo, req["id"])["items"] == []  # still not in the match list
