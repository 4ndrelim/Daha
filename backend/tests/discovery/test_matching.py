from datetime import timedelta

from sqlalchemy import select

from app.core.geo import campus_today
from app.models import ItemRequest, Notification
from tests.core.factories import community_id, signup
from tests.discovery.helpers import item, request, world

BINDER_Q = "anyone have a black binder I can borrow next Wednesday?"


def notes(db, user_id, type_=None):
    q = select(Notification).where(Notification.user_id == user_id)
    if type_:
        q = q.where(Notification.type == type_)
    return db.scalars(q).all()


def matches(client, headers, rid):
    r = client.get(f"/api/requests/{rid}/matches", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_black_binder_matches_same_dorm_first_and_notifies(client, db):
    w = world(client, db)
    ana, ana_me = signup(client, "Ana", dorm_id=community_id(db, "flomo"))
    item(client, w.wilbur, "Black 3-ring binder", category="academic")
    item(client, ana, "Black binder with dividers", category="academic")
    item(client, w.wilbur2, "Desk lamp", category="dorm")
    req = request(
        client,
        w.flomo,
        BINDER_Q,
        title="Black binder",
        item_name="black binder",
        category="academic",
    )
    m = matches(client, w.flomo, req["id"])
    assert m["matching_status"] == "done"
    assert [i["name"] for i in m["items"]] == ["Black binder with dividers", "Black 3-ring binder"]
    assert m["items"][0]["same_dorm"] and "Same dorm" in m["items"][0]["match_reason"]
    assert m["private_pinged_count"] == 0
    (n,) = notes(db, ana_me["id"], "match")
    assert (
        n.link == f"/requests/{req['id']}"
        and "black binder" in n.body
        and n.actor_id == w.flomo_me["id"]
    )
    assert len(notes(db, w.wilbur_me["id"], "match")) == 1
    assert notes(db, w.wilbur2_me["id"], "match") == []
    detail = client.get(f"/api/requests/{req['id']}", headers=w.flomo).json()
    assert detail["matching_status"] == "done" and detail["match_count"] == 2


def test_no_match_or_ping_for_owners_who_cannot_see_the_request(client, db):
    w = world(client, db)
    ana, ana_me = signup(client, "Ana", dorm_id=community_id(db, "flomo"))
    item(client, w.wilbur, "Black binder", category="academic")  # campus, but owner in Wilbur
    item(client, ana, "Black binder", category="academic")
    item(client, w.wilbur2, "Black binder", "private", category="academic")
    req = request(client, w.flomo, BINDER_Q, "dorm", title="Black binder", item_name="black binder")
    m = matches(client, w.flomo, req["id"])
    assert [i["owner"]["id"] for i in m["items"]] == [ana_me["id"]]
    for uid in (w.wilbur_me["id"], w.wilbur2_me["id"]):
        assert notes(db, uid, "match") == [] and notes(db, uid, "private_match") == []


def test_matches_only_items_the_requester_can_see(client, db):
    w = world(client, db)
    item(client, w.wilbur, "Black binder", "dorm", category="academic")  # Wilbur-only
    req = request(client, w.flomo, BINDER_Q, title="Black binder", item_name="black binder")
    assert matches(client, w.flomo, req["id"])["items"] == []
    assert notes(db, w.wilbur_me["id"], "match") == []
    # A Wilbur viewer of the same (campus) request also gets only what they can see.
    assert client.get(f"/api/requests/{req['id']}/matches", headers=w.wilbur2).status_code == 200


def test_request_update_notifies_only_new_owners(client, db):
    w = world(client, db)
    ana, ana_me = signup(client, "Ana", dorm_id=community_id(db, "flomo"))
    item(client, w.wilbur, "Camping tent", category="sports")
    req = request(client, w.flomo, "anyone have a tent?", title="Tent", item_name="tent")
    assert len(notes(db, w.wilbur_me["id"], "match")) == 1
    item(client, ana, "Two-person tent", category="sports")
    r = client.patch(f"/api/requests/{req['id']}", headers=w.flomo, json={"title": "Tent please"})
    assert r.status_code == 200, r.text
    assert len(notes(db, w.wilbur_me["id"], "match")) == 1  # not twice
    assert len(notes(db, ana_me["id"], "match")) == 1
    assert len(matches(client, w.flomo, req["id"])["items"]) == 2


def test_closed_request_is_not_matched(client, db):
    w = world(client, db)
    item(client, w.wilbur, "Camping tent", category="sports")
    req = request(client, w.flomo, "anyone have a tent?", title="Tent", item_name="tent")
    db.query(Notification).delete()
    db.commit()
    client.patch(f"/api/requests/{req['id']}", headers=w.flomo, json={"status": "cancelled"})
    from app.discovery.hooks import on_request_updated

    on_request_updated(req["id"])
    assert notes(db, w.wilbur_me["id"], "match") == []


def test_hook_failure_still_marks_done(client, db, monkeypatch):
    w = world(client, db)
    from app.discovery import matching

    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(matching, "_match", boom)
    req = request(client, w.flomo, "anyone have a tent?", title="Tent")
    db.expire_all()
    assert db.get(ItemRequest, req["id"]).matching_status == "done"


def test_fulfillable(client, db):
    w = world(client, db)
    item(client, w.wilbur, "Black binder", category="academic")
    item(client, w.wilbur, "Desk lamp", category="dorm")
    req = request(client, w.flomo, BINDER_Q, title="Black binder", item_name="black binder")
    old = request(
        client,
        w.flomo,
        "need a black binder",
        title="Black binder",
        needed_until=str(campus_today() - timedelta(days=1)),
        needed_from=str(campus_today() - timedelta(days=2)),
    )
    r = client.get("/api/me/fulfillable", headers=w.wilbur)
    assert r.status_code == 200
    body = r.json()
    assert [f["request"]["id"] for f in body] == [req["id"]]  # expired one excluded
    assert [i["name"] for i in body[0]["my_matching_items"]] == ["Black binder"]
    assert old["id"] not in [f["request"]["id"] for f in body]
    assert client.get("/api/me/fulfillable", headers=w.flomo).json() == []  # never my own
    assert client.get("/api/me/fulfillable", headers=w.wilbur2).json() == []  # no matching items


def test_home_feed(client, db):
    w = world(client, db)
    item(client, w.wilbur, "Black binder", category="academic")
    item(client, w.wilbur, "Bike pump", "private", category="sports")
    item(client, w.flomo, "Kettle", category="dorm")
    request(client, w.flomo, BINDER_Q, title="Black binder", item_name="black binder")
    request(client, w.wilbur2, "anyone have a kettle?", title="Kettle", item_name="kettle")
    r = client.get("/api/feed/home", headers=w.wilbur)
    assert r.status_code == 200, r.text
    feed = r.json()
    assert feed["dorm"]["slug"] == "wilbur" and feed["my_item_count"] == 1 and feed["show_scan_cta"]
    assert [x["request"]["title"] for x in feed["you_can_help"]] == ["Black binder"]
    assert [x["title"] for x in feed["requests_nearby"]] == [
        "Kettle",
        "Black binder",
    ]  # same dorm first
    assert [x["name"] for x in feed["new_nearby"]] == ["Kettle"]  # not mine, not private
    assert feed["stats"]["open_requests"] == 2
    sam = client.get("/api/feed/home", headers=w.wilbur2).json()
    assert {x["name"] for x in sam["new_nearby"]} == {"Black binder", "Kettle"}
    assert sam["new_nearby"][0]["name"] == "Black binder"
    assert sam["stats"]["dorm_items"] == 1


def test_community_feed_visibility(client, db):
    w = world(client, db)
    wilbur = community_id(db, "wilbur")
    item(client, w.wilbur, "Dorm-only vacuum", "dorm", category="dorm")
    item(client, w.wilbur, "Campus lamp", category="dorm")
    item(client, w.flomo, "FloMo kettle", category="dorm")
    request(client, w.wilbur2, "anyone have a stapler?", "dorm", title="Stapler")
    inside = client.get(f"/api/communities/{wilbur}/feed", headers=w.wilbur2).json()
    assert [e["kind"] for e in inside["items"]] == ["request", "item", "item"]
    assert {e["item"]["name"] for e in inside["items"] if e["kind"] == "item"} == {
        "Dorm-only vacuum",
        "Campus lamp",
    }
    outside = client.get(f"/api/communities/{wilbur}/feed", headers=w.flomo).json()
    assert [e["item"]["name"] for e in outside["items"]] == ["Campus lamp"]
    only_req = client.get(
        f"/api/communities/{wilbur}/feed", headers=w.wilbur2, params={"kind": "requests"}
    ).json()
    assert [e["kind"] for e in only_req["items"]] == ["request"]
    paged = client.get(
        f"/api/communities/{wilbur}/feed", headers=w.wilbur2, params={"limit": 2}
    ).json()
    assert len(paged["items"]) == 2 and paged["next_offset"] == 2
    secret = client.post(
        "/api/communities",
        headers=w.wilbur,
        json={"name": "Secret lab", "group_type": "research", "is_private": True},
    ).json()
    assert client.get(f"/api/communities/{secret['id']}/feed", headers=w.flomo).status_code == 404
    assert client.get(f"/api/communities/{secret['id']}/feed", headers=w.wilbur).status_code == 200
    assert client.get("/api/communities/99999/feed", headers=w.wilbur).status_code == 404


def test_item_added_after_request_shows_in_fulfillable(client, db):
    """Reverse matching: an item saved after the request still surfaces in "You could help"."""
    w = world(client, db)
    req = request(client, w.flomo, BINDER_Q, title="Black binder", item_name="black binder")
    assert client.get("/api/me/fulfillable", headers=w.wilbur).json() == []
    binder = item(client, w.wilbur, "Black binder", category="academic")
    body = client.get("/api/me/fulfillable", headers=w.wilbur).json()
    assert [f["request"]["id"] for f in body] == [req["id"]]
    # Marking it unavailable takes it out again; it never notifies anyone by itself.
    r = client.patch(f"/api/items/{binder['id']}", headers=w.wilbur, json={"status": "unavailable"})
    assert r.status_code == 200
    assert client.get("/api/me/fulfillable", headers=w.wilbur).json() == []
    assert notes(db, w.wilbur_me["id"], "match") == []
