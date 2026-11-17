import pytest

from tests.core.factories import community_id, jpeg_with_exif, seed_base, signup


@pytest.fixture
def world(client, db):
    seed_base(db)
    wilbur, flomo = community_id(db, "wilbur"), community_id(db, "flomo")
    owner_h, owner = signup(client, "Owner", dorm_id=wilbur)
    mate_h, _ = signup(client, "Mate", dorm_id=wilbur)
    out_h, _ = signup(client, "Outsider", dorm_id=flomo)
    return {"owner": owner, "owner_h": owner_h, "mate_h": mate_h, "out_h": out_h}


def item_body(**kw):
    body = {
        "name": "TI-84 graphing calculator",
        "category": "academic",
        "transaction_type": "lend",
        "visibility": "dorm",
    }
    body.update(kw)
    return body


def test_create_get_and_points(client, db, world):
    up = client.post(
        "/api/uploads",
        files={"file": ("a.jpg", jpeg_with_exif((400, 300)))},
        headers=world["owner_h"],
    ).json()
    r = client.post(
        "/api/items",
        json=item_body(
            description="Works great",
            condition="good",
            max_lend_days=7,
            pickup_place_id=1,
            pickup_note="Room side door, text me",
            image_upload_ids=[up["id"]],
        ),
        headers=world["owner_h"],
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["is_mine"] is True and item["can_borrow"] is False
    assert item["status"] == "available" and item["source"] == "manual"
    assert item["quantity"] == 1 and item["pings_enabled"] is True
    assert item["community_label"] == "Wilbur Hall"
    assert item["thumbnail_url"] == up["url"] and item["images"][0]["id"] == up["id"]
    assert item["pickup_place"]["name"] == "Tresidder Memorial Union"
    assert item["pickup_note"] == "Room side door, text me"
    assert item["group_ids"] == [] and item["active_transaction_id"] is None

    me = client.get("/api/me", headers=world["owner_h"]).json()
    assert me["points"] == 2 and me["items_shared_count"] == 1
    assert [b["code"] for b in me["badges"]] == ["first_share"]
    assert me["unread_notifications"] == 1  # the badge

    # a dorm-mate sees it, but not the private pickup note
    seen = client.get(f"/api/items/{item['id']}", headers=world["mate_h"])
    assert seen.status_code == 200
    body = seen.json()
    assert body["pickup_note"] is None and body["is_mine"] is False and body["can_borrow"] is True
    assert body["same_dorm"] is True and body["pickup_place"]["distance_min"] is not None
    # someone in another dorm gets 404, not 403
    assert client.get(f"/api/items/{item['id']}", headers=world["out_h"]).status_code == 404
    assert client.get("/api/items/99999", headers=world["owner_h"]).status_code == 404


def test_validation_errors(client, db, world):
    h = world["owner_h"]

    def post(**kw):
        return client.post("/api/items", json=item_body(**kw), headers=h)

    assert post(category="services", transaction_type="lend").status_code == 400
    assert post(category="services", transaction_type="give").status_code == 201
    assert post(visibility="groups").status_code == 400  # no group_ids
    assert post(visibility="groups", group_ids=[1]).status_code == 400  # campus is not a group
    assert post(image_upload_ids=[999]).status_code == 400
    assert post(pickup_place_id=999).status_code == 400
    assert post(available_from="2026-12-10", available_until="2026-12-01").status_code == 400
    assert post(category="weapons").status_code == 422
    assert post(name="").status_code == 422
    assert client.post("/api/items", json=item_body()).status_code == 401

    # someone else's upload can't be attached
    up = client.post(
        "/api/uploads",
        files={"file": ("a.jpg", jpeg_with_exif((50, 50)))},
        headers=world["mate_h"],
    ).json()
    assert post(image_upload_ids=[up["id"]]).status_code == 400

    # groups: must be a member
    group = client.post(
        "/api/communities",
        json={"name": "Hiking", "group_type": "club", "is_private": False},
        headers=world["mate_h"],
    ).json()
    assert post(visibility="groups", group_ids=[group["id"]]).status_code == 400
    client.post(f"/api/communities/{group['id']}/join", headers=h)
    r = post(visibility="groups", group_ids=[group["id"]])
    assert r.status_code == 201
    assert r.json()["group_ids"] == [group["id"]] and r.json()["community_label"] == "Hiking"

    # dorm visibility needs a dorm
    nodorm_h, _ = signup(client, "Nodorm")
    assert client.post("/api/items", json=item_body(), headers=nodorm_h).status_code == 400
    assert (
        client.post("/api/items", json=item_body(visibility="campus"), headers=nodorm_h).status_code
        == 201
    )


def test_patch_and_delete_are_owner_only(client, db, world):
    item = client.post(
        "/api/items", json=item_body(visibility="campus"), headers=world["owner_h"]
    ).json()
    url = f"/api/items/{item['id']}"

    assert client.patch(url, json={"name": "Hacked"}, headers=world["out_h"]).status_code == 403
    assert client.delete(url, headers=world["out_h"]).status_code == 403

    r = client.patch(
        url,
        json={"name": "TI-84 Plus", "status": "unavailable", "visibility": "dorm"},
        headers=world["owner_h"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "TI-84 Plus" and body["status"] == "unavailable"
    assert body["visibility"] == "dorm" and body["community_label"] == "Wilbur Hall"
    # the audience was rewritten: the other dorm can no longer see it
    assert client.get(url, headers=world["out_h"]).status_code == 404
    # status can only be available/unavailable
    assert (
        client.patch(url, json={"status": "borrowed"}, headers=world["owner_h"]).status_code == 422
    )
    # editing does not award the "published" points twice
    assert client.get("/api/me", headers=world["owner_h"]).json()["points"] == 2

    assert client.delete(url, headers=world["owner_h"]).status_code == 204
    assert client.get(url, headers=world["owner_h"]).status_code == 404
    assert client.get("/api/me/items", headers=world["owner_h"]).json() == []


def test_private_items_are_invisible_to_everyone_else(client, db, world):
    r = client.post(
        "/api/items",
        json=item_body(name="Bike pump", category="sports", visibility="private"),
        headers=world["owner_h"],
    )
    assert r.status_code == 201
    item = r.json()
    assert item["community_label"] == "Only you" and item["visibility"] == "private"

    me = client.get("/api/me", headers=world["owner_h"]).json()
    assert me["points"] == 0 and me["badges"] == [] and me["items_shared_count"] == 0

    assert client.get(f"/api/items/{item['id']}", headers=world["owner_h"]).status_code == 200
    for other in (world["mate_h"], world["out_h"]):
        assert client.get(f"/api/items/{item['id']}", headers=other).status_code == 404
        listed = client.get(f"/api/users/{world['owner']['id']}/items", headers=other).json()
        assert listed["items"] == []
    mine = client.get("/api/me/items", headers=world["owner_h"]).json()
    assert [i["id"] for i in mine] == [item["id"]]

    # pings can be switched off; sharing it later earns the points once
    r = client.patch(
        f"/api/items/{item['id']}", json={"pings_enabled": False}, headers=world["owner_h"]
    )
    assert r.json()["pings_enabled"] is False
    r = client.patch(
        f"/api/items/{item['id']}", json={"visibility": "dorm"}, headers=world["owner_h"]
    )
    assert r.status_code == 200
    assert client.get("/api/me", headers=world["owner_h"]).json()["points"] == 2
    assert client.get(f"/api/items/{item['id']}", headers=world["mate_h"]).status_code == 200


def test_batch(client, db, world):
    h = world["owner_h"]
    names = ["Bike pump", "Tool kit", "Iron", "Umbrella"]
    r = client.post(
        "/api/items/batch",
        json={"items": [item_body(name=n, visibility="private", category="other") for n in names]},
        headers=h,
    )
    assert r.status_code == 201, r.text
    assert [i["name"] for i in r.json()["items"]] == names
    assert len(client.get("/api/me/items", headers=h).json()) == 4

    # one bad item → nothing is created
    r = client.post(
        "/api/items/batch",
        json={
            "items": [
                item_body(name="Good one"),
                item_body(name="Bad", category="services", transaction_type="lend"),
            ]
        },
        headers=h,
    )
    assert r.status_code == 400
    assert len(client.get("/api/me/items", headers=h).json()) == 4
    assert client.get("/api/me", headers=h).json()["points"] == 0

    too_many = {"items": [item_body(name=f"Item {i}") for i in range(31)]}
    assert client.post("/api/items/batch", json=too_many, headers=h).status_code == 400
    assert client.post("/api/items/batch", json={"items": []}, headers=h).status_code == 400


def test_item_points_cap_at_ten_per_day(client, db, world):
    h = world["owner_h"]
    r = client.post(
        "/api/items/batch",
        json={"items": [item_body(name=f"Book {i}") for i in range(12)]},
        headers=h,
    )
    assert r.status_code == 201
    assert client.get("/api/me", headers=h).json()["points"] == 20


def test_my_items_status_filter(client, db, world):
    h = world["owner_h"]
    a = client.post("/api/items", json=item_body(name="A"), headers=h).json()
    client.post("/api/items", json=item_body(name="B"), headers=h)
    client.patch(f"/api/items/{a['id']}", json={"status": "unavailable"}, headers=h)
    listed = client.get("/api/me/items", params={"status": "unavailable"}, headers=h).json()
    assert [i["name"] for i in listed] == ["A"]
    assert len(client.get("/api/me/items", headers=h).json()) == 2
