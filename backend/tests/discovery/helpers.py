"""A small world: two Wilbur users, one FloMo user, one group. Everything through the API."""

from dataclasses import dataclass

from tests.core.factories import community_id, seed_base, signup


@dataclass
class World:
    wilbur: dict  # headers
    wilbur_me: dict
    wilbur2: dict
    wilbur2_me: dict
    flomo: dict
    flomo_me: dict
    group_id: int


def world(client, db) -> World:
    seed_base(db)
    w1, w1me = signup(client, "Maya", dorm_id=community_id(db, "wilbur"))
    w2, w2me = signup(client, "Sam", dorm_id=community_id(db, "wilbur"))
    f1, f1me = signup(client, "Jordan", dorm_id=community_id(db, "flomo"))
    g = client.post(
        "/api/communities",
        headers=w1,
        json={"name": "Robotics", "group_type": "club", "is_private": False},
    )
    assert g.status_code == 201, g.text
    return World(w1, w1me, w2, w2me, f1, f1me, g.json()["id"])


def item(client, headers, name, visibility="campus", **kw) -> dict:
    body = {
        "name": name,
        "category": kw.pop("category", "other"),
        "transaction_type": "lend",
        "visibility": visibility,
        **kw,
    }
    r = client.post("/api/items", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def request(client, headers, raw_text, visibility="campus", **kw) -> dict:
    body = {
        "raw_text": raw_text,
        "title": kw.pop("title", raw_text[:60]),
        "visibility": visibility,
        **kw,
    }
    r = client.post("/api/requests", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def search(client, headers, q="", **params) -> dict:
    r = client.get("/api/search", headers=headers, params={"q": q, **params})
    assert r.status_code == 200, r.text
    return r.json()


def names(resp) -> list[str]:
    return [i["name"] for i in resp["items"]]
