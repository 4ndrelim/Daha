from datetime import timedelta

from app.core.geo import campus_today
from app.models import ItemRequest
from tests.core.factories import community_id, seed_base, signup


def request_body(**kw):
    body = {
        "raw_text": "Can I borrow a black binder next Wednesday?",
        "title": "Black binder",
        "item_name": "black binder",
        "category": "academic",
        "attributes": {"color": "black"},
        "transaction_type": "lend",
        "visibility": "dorm",
    }
    body.update(kw)
    return body


def world(client, db):
    seed_base(db)
    wilbur, flomo = community_id(db, "wilbur"), community_id(db, "flomo")
    a_h, a = signup(client, "Asker", dorm_id=flomo)
    mate_h, _ = signup(client, "Mate", dorm_id=flomo)
    out_h, out = signup(client, "Outsider", dorm_id=wilbur)
    return a_h, a, mate_h, out_h, out


def test_create_get_and_visibility(client, db):
    a_h, a, mate_h, out_h, _ = world(client, db)
    today = campus_today()
    r = client.post(
        "/api/requests",
        json=request_body(
            needed_from=str(today + timedelta(days=2)),
            needed_until=str(today + timedelta(days=3)),
            pickup_place_id=2,
        ),
        headers=a_h,
    )
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["status"] == "open" and req["is_mine"] is True and req["offers"] == []
    assert req["community_label"] == "Florence Moore Hall (FloMo)"
    assert req["attributes"] == {"color": "black"} and req["quantity"] == 1
    assert req["requester"]["name"] == "Asker" and req["match_count"] == 0
    assert req["pickup_place"]["name"] == "Cecil H. Green Library"

    seen = client.get(f"/api/requests/{req['id']}", headers=mate_h)
    assert seen.status_code == 200
    assert seen.json()["is_mine"] is False and seen.json()["same_dorm"] is True
    assert client.get(f"/api/requests/{req['id']}", headers=out_h).status_code == 404
    assert [r["id"] for r in client.get("/api/me/requests", headers=a_h).json()] == [req["id"]]
    assert client.get("/api/me/requests", headers=mate_h).json() == []

    assert (
        client.post(
            "/api/requests", json=request_body(visibility="private"), headers=a_h
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/requests", json=request_body(visibility="groups"), headers=a_h
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/requests",
            json=request_body(needed_from="2027-02-02", needed_until="2027-02-01"),
            headers=a_h,
        ).status_code
        == 400
    )
    assert client.post("/api/requests", json=request_body(title=""), headers=a_h).status_code == 422


def test_patch_is_requester_only_and_can_close(client, db):
    a_h, _, mate_h, _, _ = world(client, db)
    req = client.post("/api/requests", json=request_body(), headers=a_h).json()
    url = f"/api/requests/{req['id']}"
    assert client.patch(url, json={"title": "x"}, headers=mate_h).status_code == 403

    r = client.patch(
        url, json={"title": "Black 2-inch binder", "visibility": "campus"}, headers=a_h
    )
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Black 2-inch binder" and r.json()["community_label"] == "Campus"

    r = client.patch(url, json={"status": "cancelled"}, headers=a_h)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert client.patch(url, json={"title": "again"}, headers=a_h).status_code == 409
    assert client.patch(url, json={"status": "open"}, headers=a_h).status_code == 422


def test_cancelling_declines_pending_offers(client, db):
    a_h, _, mate_h, _, _ = world(client, db)
    req = client.post("/api/requests", json=request_body(), headers=a_h).json()
    item = client.post(
        "/api/items",
        json={
            "name": "Binder",
            "category": "academic",
            "transaction_type": "lend",
            "visibility": "dorm",
        },
        headers=mate_h,
    ).json()
    tx = client.post(
        f"/api/requests/{req['id']}/offers", json={"item_id": item["id"]}, headers=mate_h
    ).json()
    client.patch(f"/api/requests/{req['id']}", json={"status": "cancelled"}, headers=a_h)
    assert (
        client.get(f"/api/transactions/{tx['id']}", headers=mate_h).json()["status"] == "declined"
    )


def test_expired_is_computed(client, db):
    a_h, _, mate_h, _, _ = world(client, db)
    today = campus_today()
    old = client.post(
        "/api/requests", json=request_body(needed_until=str(today + timedelta(days=1))), headers=a_h
    ).json()
    undated = client.post("/api/requests", json=request_body(title="No dates"), headers=a_h).json()
    row = db.get(ItemRequest, old["id"])
    row.needed_until = today - timedelta(days=1)
    stale = db.get(ItemRequest, undated["id"])
    stale.created_at = stale.created_at - timedelta(days=15)
    db.commit()
    assert client.get(f"/api/requests/{old['id']}", headers=a_h).json()["status"] == "expired"
    assert client.get(f"/api/requests/{undated['id']}", headers=a_h).json()["status"] == "expired"
    assert db.get(ItemRequest, old["id"]).status == "open"  # stored value is untouched
    db.rollback()
    # the dorm's open-request count ignores expired ones, and nobody can offer on them
    flomo = client.get("/api/communities/flomo", headers=mate_h).json()
    assert flomo["open_request_count"] == 0
    item = client.post(
        "/api/items",
        json={
            "name": "Binder",
            "category": "academic",
            "transaction_type": "lend",
            "visibility": "dorm",
        },
        headers=mate_h,
    ).json()
    r = client.post(
        f"/api/requests/{old['id']}/offers", json={"item_id": item["id"]}, headers=mate_h
    )
    assert r.status_code == 409


def test_offer_rules_and_new_item_offer(client, db):
    a_h, a, mate_h, out_h, _ = world(client, db)
    req = client.post("/api/requests", json=request_body(), headers=a_h).json()
    offers = f"/api/requests/{req['id']}/offers"
    mine = client.post(
        "/api/items",
        json={
            "name": "Asker's binder",
            "category": "academic",
            "transaction_type": "lend",
            "visibility": "dorm",
        },
        headers=a_h,
    ).json()
    item = client.post(
        "/api/items",
        json={
            "name": "Binder",
            "category": "academic",
            "transaction_type": "lend",
            "visibility": "private",
        },
        headers=mate_h,
    ).json()
    new_item = {
        "name": "Spare black binder",
        "category": "academic",
        "transaction_type": "give",
        "visibility": "dorm",
    }

    assert client.post(offers, json={"item_id": mine["id"]}, headers=a_h).status_code == 400
    assert client.post(offers, json={"item_id": item["id"]}, headers=out_h).status_code == 404
    assert client.post(offers, json={}, headers=mate_h).status_code == 400
    assert (
        client.post(
            offers, json={"item_id": item["id"], "new_item": new_item}, headers=mate_h
        ).status_code
        == 400
    )
    assert client.post(offers, json={"item_id": mine["id"]}, headers=mate_h).status_code == 400

    # a private "I have this" item can be offered (the anonymous-ping flow ends here)
    r = client.post(offers, json={"item_id": item["id"], "message": "I have one"}, headers=mate_h)
    assert r.status_code == 201, r.text
    assert r.json()["item"]["name"] == "Binder"
    assert client.post(offers, json={"item_id": item["id"]}, headers=mate_h).status_code == 409

    # offering something not listed yet creates the item with source='offer'
    r = client.post(offers, json={"new_item": new_item}, headers=mate_h)
    assert r.status_code == 201, r.text
    created = client.get(f"/api/items/{r.json()['item']['id']}", headers=mate_h).json()
    assert created["source"] == "offer" and created["name"] == "Spare black binder"
    assert r.json()["kind"] == "give"

    detail = client.get(f"/api/requests/{req['id']}", headers=a_h).json()
    assert detail["offer_count"] == 2 and len(detail["offers"]) == 2
    assert all(o["my_role"] == "borrower" for o in detail["offers"])
