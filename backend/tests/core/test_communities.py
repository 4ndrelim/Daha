from tests.core.factories import community_id, seed_base, signup


def test_list_and_get(client, db):
    seed_base(db)
    headers, _ = signup(client, "Sam", dorm_id=community_id(db, "wilbur"))
    everything = client.get("/api/communities", headers=headers).json()
    assert everything[0]["kind"] == "campus" and everything[0]["is_member"] is True
    dorms = client.get("/api/communities", params={"kind": "dorm"}, headers=headers).json()
    assert len(dorms) == 39  # 15 + EVGR A–D + 20 graduate residences
    found = client.get("/api/communities", params={"q": "flo"}, headers=headers).json()
    assert [c["slug"] for c in found] == ["flomo"]
    assert found[0]["distance_min"] is not None and found[0]["is_member"] is False

    by_slug = client.get("/api/communities/wilbur", headers=headers).json()
    by_id = client.get(f"/api/communities/{by_slug['id']}", headers=headers).json()
    assert by_slug == by_id and by_slug["member_count"] == 1 and by_slug["my_role"] == "member"
    assert client.get("/api/communities/nope", headers=headers).status_code == 404
    assert client.get("/api/communities").status_code == 401


def test_private_group_needs_join_code(client, db):
    seed_base(db)
    admin_h, _ = signup(client, "Admin")
    other_h, _ = signup(client, "Other")
    r = client.post(
        "/api/communities",
        json={"name": "Bio Lab 3rd Floor", "group_type": "research", "is_private": True},
        headers=admin_h,
    )
    assert r.status_code == 201, r.text
    group = r.json()
    code = group["join_code"]
    assert group["slug"] == "bio-lab-3rd-floor" and group["my_role"] == "admin"
    assert len(code) == 6

    # non-members never see the code and cannot list members
    seen = client.get(f"/api/communities/{group['id']}", headers=other_h).json()
    assert seen["join_code"] is None and seen["is_member"] is False
    assert client.get(f"/api/communities/{group['id']}/members", headers=other_h).status_code == 404

    assert client.post(f"/api/communities/{group['id']}/join", headers=other_h).status_code == 403
    r = client.post(
        f"/api/communities/{group['id']}/join", json={"join_code": "WRONG1"}, headers=other_h
    )
    assert r.status_code == 403
    r = client.post(
        f"/api/communities/{group['id']}/join", json={"join_code": code.lower()}, headers=other_h
    )
    assert r.status_code == 200
    joined = r.json()
    assert joined["is_member"] is True and joined["my_role"] == "member"
    assert joined["join_code"] is None and joined["member_count"] == 2

    members = client.get(f"/api/communities/{group['id']}/members", headers=other_h).json()
    assert [m["name"] for m in members["items"]] == ["Admin", "Other"]
    assert members["next_offset"] is None

    assert client.post(f"/api/communities/{group['id']}/leave", headers=other_h).status_code == 204
    after = client.get(f"/api/communities/{group['id']}", headers=other_h).json()
    assert after["is_member"] is False and after["member_count"] == 1


def test_group_slugs_are_unique_and_public_groups_open(client, db):
    seed_base(db)
    a_h, _ = signup(client, "A")
    b_h, _ = signup(client, "B")
    body = {"name": "Film Society", "group_type": "org", "is_private": False}
    first = client.post("/api/communities", json=body, headers=a_h).json()
    second = client.post("/api/communities", json=body, headers=a_h).json()
    assert (first["slug"], second["slug"]) == ("film-society", "film-society-2")
    assert first["join_code"] is None
    assert client.post(f"/api/communities/{first['id']}/join", headers=b_h).status_code == 200
    me = client.get("/api/me", headers=b_h).json()
    assert [g["slug"] for g in me["groups"]] == ["film-society"]


def test_joining_a_dorm_replaces_the_old_one_and_campus_cannot_be_left(client, db):
    seed_base(db)
    wilbur, stern = community_id(db, "wilbur"), community_id(db, "stern")
    headers, _ = signup(client, "Sam", dorm_id=wilbur)
    assert client.post(f"/api/communities/{stern}/join", headers=headers).status_code == 200
    assert client.get("/api/me", headers=headers).json()["dorm"]["slug"] == "stern"
    campus = community_id(db, "campus")
    assert client.post(f"/api/communities/{campus}/leave", headers=headers).status_code == 400


def test_places_have_walking_minutes(client, db):
    seed_base(db)
    with_dorm, _ = signup(client, "Sam", dorm_id=community_id(db, "wilbur"))
    no_dorm, _ = signup(client, "Nodorm")
    places = client.get("/api/places", headers=with_dorm).json()
    assert len(places) == 6 and all(p["distance_min"] >= 1 for p in places)
    assert all(p["distance_min"] is None for p in client.get("/api/places", headers=no_dorm).json())
