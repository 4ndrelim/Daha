"""PLAN.md §7.7: lifecycles, illegal actions, auto-declines, privacy, points, badges."""

import pytest
from sqlalchemy import select

from app.models import Item, ItemRequest
from tests.core.factories import community_id, seed_base, signup


@pytest.fixture
def w(client, db):
    seed_base(db)
    wilbur, flomo = community_id(db, "wilbur"), community_id(db, "flomo")
    owner_h, owner = signup(client, "Maya Owner", dorm_id=wilbur)
    bor_h, borrower = signup(client, "Jordan Borrower", dorm_id=flomo)
    third_h, third = signup(client, "Third Wheel", dorm_id=flomo)
    return {
        "owner": owner,
        "borrower": borrower,
        "third": third,
        "oh": owner_h,
        "bh": bor_h,
        "th": third_h,
    }


def make_item(client, headers, **kw):
    body = {
        "name": "Camping tent",
        "category": "sports",
        "transaction_type": "lend",
        "visibility": "campus",
        "pickup_note": "Side door of Wilbur, code 4411",
    }
    body.update(kw)
    r = client.post("/api/items", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def make_request(client, headers, **kw):
    body = {
        "raw_text": "anyone have a tent I can borrow?",
        "title": "Tent",
        "item_name": "tent",
        "category": "sports",
        "visibility": "campus",
    }
    body.update(kw)
    r = client.post("/api/requests", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def act(client, tx_id, headers, action, **kw):
    return client.post(
        f"/api/transactions/{tx_id}/actions", json={"action": action, **kw}, headers=headers
    )


def borrow(client, item_id, headers, **kw):
    return client.post(f"/api/items/{item_id}/borrow", json=kw, headers=headers)


def me(client, headers):
    return client.get("/api/me", headers=headers).json()


def item_status(client, item_id, headers):
    return client.get(f"/api/items/{item_id}", headers=headers).json()["status"]


def test_full_lend_lifecycle(client, db, w):
    item = make_item(client, w["oh"])
    r = borrow(
        client,
        item["id"],
        w["bh"],
        message="Could I borrow this for the weekend?",
        due_date="2027-01-10",
    )
    assert r.status_code == 201, r.text
    tx = r.json()
    assert tx["status"] == "requested" and tx["kind"] == "lend"
    assert tx["initiated_by"] == "borrower" and tx["my_role"] == "borrower"
    assert tx["allowed_actions"] == ["cancel"] and tx["can_review"] is False
    assert tx["pickup_note"] is None  # hidden until accepted
    assert tx["item"]["id"] == item["id"] and tx["owner"]["name"] == "Maya Owner"
    assert [e["status"] for e in tx["timeline"]] == ["requested"]

    # the owner gets a notification and an unread first message
    owner_me = me(client, w["oh"])
    assert owner_me["unread_messages"] == 1
    notes = client.get("/api/notifications", headers=w["oh"]).json()
    assert notes[0]["type"] == "borrow_request"
    assert notes[0]["link"] == f"/messages/{tx['conversation_id']}"
    assert notes[0]["actor"]["name"] == "Jordan Borrower" and notes[0]["read"] is False

    owner_view = client.get(f"/api/transactions/{tx['id']}", headers=w["oh"]).json()
    assert owner_view["my_role"] == "owner"
    assert owner_view["allowed_actions"] == ["accept", "decline"]
    assert owner_view["pickup_note"] == "Side door of Wilbur, code 4411"

    # item page: the borrower can't ask twice, and still can't see the note
    page = client.get(f"/api/items/{item['id']}", headers=w["bh"]).json()
    assert page["can_borrow"] is False and page["active_transaction_id"] == tx["id"]
    assert page["pickup_note"] is None
    assert borrow(client, item["id"], w["bh"]).status_code == 409

    # accept → reserved, note revealed
    r = act(client, tx["id"], w["oh"], "accept", pickup_place_id=1)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "accepted"
    assert r.json()["allowed_actions"] == ["hand_off", "cancel"]
    assert r.json()["pickup_place"]["id"] == 1
    assert item_status(client, item["id"], w["bh"]) == "reserved"
    b_view = client.get(f"/api/transactions/{tx['id']}", headers=w["bh"]).json()
    assert b_view["pickup_note"] == "Side door of Wilbur, code 4411"
    assert b_view["allowed_actions"] == ["hand_off", "cancel"]
    page = client.get(f"/api/items/{item['id']}", headers=w["bh"]).json()
    assert page["pickup_note"] == "Side door of Wilbur, code 4411"
    # ... but a third person still can't
    page3 = client.get(f"/api/items/{item['id']}", headers=w["th"]).json()
    assert page3["pickup_note"] is None and page3["can_borrow"] is False

    # hand off → borrowed
    r = act(client, tx["id"], w["bh"], "hand_off")
    assert r.status_code == 200 and r.json()["status"] == "handed_off"
    assert r.json()["allowed_actions"] == []  # the borrower waits for the owner
    assert r.json()["is_overdue"] is False
    assert item_status(client, item["id"], w["oh"]) == "borrowed"

    # only the owner can mark it returned
    assert act(client, tx["id"], w["bh"], "mark_returned").status_code == 409
    r = act(client, tx["id"], w["oh"], "mark_returned")
    assert r.status_code == 200
    done = r.json()
    assert done["status"] == "completed" and done["allowed_actions"] == []
    assert done["can_review"] is True
    assert [e["status"] for e in done["timeline"]] == [
        "requested",
        "accepted",
        "handed_off",
        "completed",
    ]
    assert item_status(client, item["id"], w["oh"]) == "available"

    # points: owner 2 (item) + 10 (lend); borrower 2
    assert me(client, w["oh"])["points"] == 12
    assert me(client, w["bh"])["points"] == 2
    assert {b["code"] for b in me(client, w["oh"])["badges"]} == {"first_share", "first_lend"}
    types = [n["type"] for n in client.get("/api/notifications", headers=w["bh"]).json()]
    assert types.count("tx_update") == 2  # "accepted", then "all done — leave a review"

    # reviews: one each, only parties
    r = client.post(
        f"/api/transactions/{tx['id']}/review",
        json={"rating": 5, "body": "Great tent"},
        headers=w["bh"],
    )
    assert r.status_code == 201, r.text
    assert r.json()["reviewee_id"] == w["owner"]["id"] and r.json()["rating"] == 5
    assert (
        client.post(
            f"/api/transactions/{tx['id']}/review", json={"rating": 4}, headers=w["bh"]
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/transactions/{tx['id']}/review", json={"rating": 3}, headers=w["oh"]
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/transactions/{tx['id']}/review", json={"rating": 5}, headers=w["th"]
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/transactions/{tx['id']}/review", json={"rating": 6}, headers=w["oh"]
        ).status_code
        == 422
    )
    assert me(client, w["oh"])["points"] == 14  # +2 for a ≥4★ review
    assert me(client, w["bh"])["points"] == 2  # 3★ earns nothing
    assert me(client, w["oh"])["rating_avg"] == 5.0
    reviews = client.get(f"/api/users/{w['owner']['id']}/reviews", headers=w["th"]).json()
    assert [r["body"] for r in reviews] == ["Great tent"]
    after = client.get(f"/api/transactions/{tx['id']}", headers=w["bh"]).json()
    assert after["can_review"] is False

    # history filters
    past = client.get("/api/transactions", params={"state": "past"}, headers=w["oh"]).json()
    assert [t["id"] for t in past] == [tx["id"]]
    assert client.get("/api/transactions", params={"state": "active"}, headers=w["oh"]).json() == []
    as_borrower = client.get("/api/transactions", params={"role": "borrower"}, headers=w["oh"])
    assert as_borrower.json() == []


def test_full_give_lifecycle_via_request_and_offer(client, db, w):
    request = make_request(
        client, w["bh"], raw_text="anyone have spare ramen?", title="Ramen", category="consumables"
    )
    assert request["matching_status"] in ("pending", "done") and request["is_mine"] is True
    assert request["share_url"].endswith(f"/r/{request['id']}")
    # the no-op discovery hook ran after the response
    assert (
        client.get(f"/api/requests/{request['id']}", headers=w["bh"]).json()["matching_status"]
        == "done"
    )

    item = make_item(
        client, w["oh"], name="Instant ramen", category="consumables", transaction_type="give"
    )
    r = client.post(
        f"/api/requests/{request['id']}/offers",
        json={"item_id": item["id"], "message": "I have a box!"},
        headers=w["oh"],
    )
    assert r.status_code == 201, r.text
    tx = r.json()
    assert tx["status"] == "offered" and tx["kind"] == "give"
    assert tx["initiated_by"] == "owner" and tx["my_role"] == "owner"
    assert tx["allowed_actions"] == ["cancel"] and tx["request_id"] == request["id"]

    notes = client.get("/api/notifications", headers=w["bh"]).json()
    assert notes[0]["type"] == "offer" and notes[0]["link"] == f"/requests/{request['id']}"

    detail = client.get(f"/api/requests/{request['id']}", headers=w["bh"]).json()
    assert detail["offer_count"] == 1 and [o["id"] for o in detail["offers"]] == [tx["id"]]
    assert detail["offers"][0]["allowed_actions"] == ["accept", "decline"]
    # a bystander sees the request but not other people's offers
    bystander = client.get(f"/api/requests/{request['id']}", headers=w["th"]).json()
    assert bystander["offers"] == [] and bystander["offer_count"] == 1

    assert act(client, tx["id"], w["bh"], "accept").status_code == 200
    assert (
        client.get(f"/api/requests/{request['id']}", headers=w["bh"]).json()["status"]
        == "in_progress"
    )

    r = act(client, tx["id"], w["oh"], "hand_off")
    assert r.status_code == 200 and r.json()["status"] == "completed"  # give: no return step
    assert r.json()["allowed_actions"] == []
    assert db.get(Item, item["id"]).status == "unavailable"
    assert db.get(ItemRequest, request["id"]).status == "fulfilled"
    assert db.get(ItemRequest, request["id"]).fulfilled_at is not None
    # owner: 2 (item) + 15 (give) + 5 (fulfilled a request); borrower: nothing
    assert me(client, w["oh"])["points"] == 22
    assert me(client, w["bh"])["points"] == 0
    assert act(client, tx["id"], w["oh"], "mark_returned").status_code == 409


def test_exchange_gives_both_sides_points_and_services_stay_available(client, db, w):
    item = make_item(
        client, w["oh"], name="Headshot photos", category="services", transaction_type="exchange"
    )
    tx = borrow(client, item["id"], w["bh"], message="Swap for cookies?").json()
    assert act(client, tx["id"], w["oh"], "accept").status_code == 200
    r = act(client, tx["id"], w["oh"], "hand_off")
    assert r.json()["status"] == "completed"
    assert me(client, w["oh"])["points"] == 12 and me(client, w["bh"])["points"] == 10
    assert db.get(Item, item["id"]).status == "available"


def test_every_illegal_action_is_409(client, db, w):
    item = make_item(client, w["oh"])
    tx = borrow(client, item["id"], w["bh"]).json()
    everything = ["accept", "decline", "cancel", "hand_off", "mark_returned"]

    def check(headers, allowed):
        got = client.get(f"/api/transactions/{tx['id']}", headers=headers).json()
        assert got["allowed_actions"] == allowed
        for action in everything:
            if action not in allowed:
                assert act(client, tx["id"], headers, action).status_code == 409, action

    # requested
    check(w["oh"], ["accept", "decline"])
    check(w["bh"], ["cancel"])
    act(client, tx["id"], w["oh"], "accept")
    # accepted
    check(w["oh"], ["hand_off", "cancel"])
    check(w["bh"], ["hand_off", "cancel"])
    act(client, tx["id"], w["oh"], "hand_off")
    # handed_off (lend)
    check(w["bh"], [])
    check(w["oh"], ["mark_returned"])
    act(client, tx["id"], w["oh"], "mark_returned")
    # completed
    check(w["oh"], [])
    check(w["bh"], [])
    assert act(client, tx["id"], w["oh"], "explode").status_code == 422

    # offered: owner may only cancel; requester may accept/decline
    request = make_request(client, w["bh"])
    offer = client.post(
        f"/api/requests/{request['id']}/offers", json={"item_id": item["id"]}, headers=w["oh"]
    ).json()
    tx = offer
    check(w["oh"], ["cancel"])
    check(w["bh"], ["accept", "decline"])
    assert act(client, tx["id"], w["bh"], "decline").status_code == 200
    check(w["oh"], [])
    check(w["bh"], [])


def test_non_party_gets_404(client, db, w):
    item = make_item(client, w["oh"])
    tx = borrow(client, item["id"], w["bh"], message="hi").json()
    assert client.get(f"/api/transactions/{tx['id']}", headers=w["th"]).status_code == 404
    assert act(client, tx["id"], w["th"], "accept").status_code == 404
    conv = tx["conversation_id"]
    assert client.get(f"/api/conversations/{conv}", headers=w["th"]).status_code == 404
    assert client.get(f"/api/conversations/{conv}/messages", headers=w["th"]).status_code == 404
    assert (
        client.post(
            f"/api/conversations/{conv}/messages", json={"body": "hi"}, headers=w["th"]
        ).status_code
        == 404
    )
    assert client.get("/api/transactions", headers=w["th"]).json() == []
    assert client.get("/api/transactions/1").status_code == 401


def test_accept_auto_declines_other_requests_on_the_same_item(client, db, w):
    item = make_item(client, w["oh"])
    first = borrow(client, item["id"], w["bh"]).json()
    second = borrow(client, item["id"], w["th"]).json()
    assert act(client, first["id"], w["oh"], "accept").status_code == 200

    loser = client.get(f"/api/transactions/{second['id']}", headers=w["th"]).json()
    assert loser["status"] == "declined" and loser["allowed_actions"] == []
    assert loser["timeline"][-1]["by"] is None and "someone else" in loser["timeline"][-1]["note"]
    msgs = client.get(
        f"/api/conversations/{second['conversation_id']}/messages", headers=w["th"]
    ).json()
    assert msgs[-1]["kind"] == "system" and msgs[-1]["sender"] is None
    notes = client.get("/api/notifications", headers=w["th"]).json()
    assert notes[0]["type"] == "tx_update"
    # the item is reserved, so nobody else can ask or be accepted
    assert borrow(client, item["id"], w["th"]).status_code == 409


def test_cancel_and_decline_release_the_item_and_request(client, db, w):
    request = make_request(client, w["bh"])
    item = make_item(client, w["oh"])
    tx = client.post(
        f"/api/requests/{request['id']}/offers", json={"item_id": item["id"]}, headers=w["oh"]
    ).json()
    act(client, tx["id"], w["bh"], "accept")
    assert db.get(Item, item["id"]).status == "reserved"
    db.rollback()
    assert act(client, tx["id"], w["bh"], "cancel").status_code == 200
    db.expire_all()
    assert db.get(Item, item["id"]).status == "available"
    assert db.get(ItemRequest, request["id"]).status == "open"
    db.rollback()

    # a declined borrow request never touched the item
    tx2 = borrow(client, item["id"], w["th"]).json()
    assert act(client, tx2["id"], w["oh"], "decline").status_code == 200
    assert item_status(client, item["id"], w["th"]) == "available"
    # accept needs the item to be available
    tx3 = borrow(client, item["id"], w["th"]).json()
    client.patch(f"/api/items/{item['id']}", json={"status": "unavailable"}, headers=w["oh"])
    assert act(client, tx3["id"], w["oh"], "accept").status_code == 409


def test_fulfilled_request_auto_declines_remaining_offers(client, db, w):
    request = make_request(client, w["bh"])
    a = make_item(client, w["oh"], name="Tent A", transaction_type="give")
    b = make_item(client, w["th"], name="Tent B", transaction_type="give")
    offer_a = client.post(
        f"/api/requests/{request['id']}/offers", json={"item_id": a["id"]}, headers=w["oh"]
    ).json()
    offer_b = client.post(
        f"/api/requests/{request['id']}/offers", json={"item_id": b["id"]}, headers=w["th"]
    ).json()
    act(client, offer_a["id"], w["bh"], "accept")
    # different item → the other offer is still pending while this one is in progress
    assert (
        client.get(f"/api/transactions/{offer_b['id']}", headers=w["th"]).json()["status"]
        == "offered"
    )
    act(client, offer_a["id"], w["oh"], "hand_off")
    other = client.get(f"/api/transactions/{offer_b['id']}", headers=w["th"]).json()
    assert other["status"] == "declined"
    assert db.get(Item, b["id"]).status == "available"
    # no more offers on a closed request
    c = make_item(client, w["th"], name="Tent C")
    r = client.post(
        f"/api/requests/{request['id']}/offers", json={"item_id": c["id"]}, headers=w["th"]
    )
    assert r.status_code == 409


def test_borrow_rules(client, db, w):
    item = make_item(client, w["oh"], visibility="dorm")
    assert borrow(client, item["id"], w["bh"]).status_code == 404  # other dorm can't see it
    campus = make_item(client, w["oh"])
    assert borrow(client, campus["id"], w["oh"]).status_code == 400  # own item
    assert borrow(client, campus["id"], w["bh"], request_id=999).status_code == 400
    mine = make_request(client, w["bh"])
    r = borrow(
        client,
        campus["id"],
        w["bh"],
        request_id=mine["id"],
        start_date="2027-01-05",
        due_date="2027-01-01",
    )
    assert r.status_code == 400
    r = borrow(client, campus["id"], w["bh"], request_id=mine["id"])
    assert r.status_code == 201 and r.json()["request_id"] == mine["id"]

    # removing an item tells whoever was waiting on it
    assert client.delete(f"/api/items/{campus['id']}", headers=w["oh"]).status_code == 204
    assert (
        client.get(f"/api/transactions/{r.json()['id']}", headers=w["bh"]).json()["status"]
        == "declined"
    )


def test_request_hero_and_generous_badges(client, db, w):
    for n in range(5):
        request = make_request(client, w["bh"], title=f"Thing {n}")
        item = make_item(client, w["oh"], name=f"Thing {n}", transaction_type="give")
        tx = client.post(
            f"/api/requests/{request['id']}/offers", json={"item_id": item["id"]}, headers=w["oh"]
        ).json()
        act(client, tx["id"], w["bh"], "accept")
        assert act(client, tx["id"], w["oh"], "hand_off").status_code == 200
        client.post(f"/api/transactions/{tx['id']}/review", json={"rating": 5}, headers=w["bh"])
    owner = me(client, w["oh"])
    assert {b["code"] for b in owner["badges"]} == {
        "first_share",
        "generous",
        "request_hero",
        "trusted",
    }
    # 5 × (2 item + 15 give + 5 request bonus + 2 review)
    assert owner["points"] == 5 * 24 and owner["level"]["name"] == "Helper"
    badge_notes = [
        n for n in client.get("/api/notifications", headers=w["oh"]).json() if n["type"] == "badge"
    ]
    assert len(badge_notes) == 4 and all(n["link"] == "/profile" for n in badge_notes)
    assert db.scalar(select(Item.status).where(Item.name == "Thing 0")) == "unavailable"
