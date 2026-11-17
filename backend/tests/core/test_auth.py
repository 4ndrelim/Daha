from tests.core.factories import community_id, seed_base, signup


def test_signup_requires_allowed_domain(client, db):
    seed_base(db)
    r = client.post(
        "/api/auth/signup",
        json={"email": "eve@gmail.com", "password": "password123", "name": "Eve"},
    )
    assert r.status_code == 400
    r = client.post(
        "/api/auth/signup",
        json={"email": "eve@stanford.edu.evil.com", "password": "password123", "name": "Eve"},
    )
    assert r.status_code == 400


def test_signup_rules_and_memberships(client, db):
    seed_base(db)
    wilbur = community_id(db, "wilbur")
    r = client.post(
        "/api/auth/signup",
        json={"email": "Sam@Stanford.EDU", "password": "short", "name": "Sam"},
    )
    assert r.status_code == 400  # password too short

    headers, me = signup(client, "Sam", dorm_id=wilbur, email="Sam@Stanford.EDU")
    assert me["email"] == "sam@stanford.edu"
    assert me["dorm"]["slug"] == "wilbur"
    assert me["dorm_name"] == "Wilbur Hall"
    assert me["points"] == 0 and me["level"]["name"] == "New Neighbor"
    assert me["level"]["next_level_name"] == "Good Neighbor"
    assert me["onboarded"] is False and me["groups"] == [] and me["badges"] == []
    assert me["unread_notifications"] == 0 and me["unread_messages"] == 0

    mine = client.get("/api/communities", params={"mine": True}, headers=headers).json()
    assert {c["kind"] for c in mine} == {"campus", "dorm"}

    r = client.post(
        "/api/auth/signup",
        json={"email": "sam@stanford.edu", "password": "password123", "name": "Sam 2"},
    )
    assert r.status_code == 409


def test_signup_stores_referrer(client, db):
    from app.models import User

    seed_base(db)
    _, first = signup(client, "First")
    r = client.post(
        "/api/auth/signup",
        json={
            "email": "second@stanford.edu",
            "password": "password123",
            "name": "Second",
            "ref_user_id": first["id"],
        },
    )
    assert r.status_code == 201
    assert db.get(User, r.json()["user"]["id"]).referred_by == first["id"]


def test_login_and_me(client, db):
    seed_base(db)
    signup(client, "Maya", email="maya@stanford.edu")
    r = client.post("/api/auth/login", json={"email": "MAYA@stanford.edu", "password": "nope"})
    assert r.status_code == 401
    r = client.post(
        "/api/auth/login", json={"email": "MAYA@stanford.edu", "password": "password123"}
    )
    assert r.status_code == 200
    token = r.json()["token"]
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["name"] == "Maya"


def test_patch_me_switches_dorm(client, db):
    seed_base(db)
    wilbur, flomo = community_id(db, "wilbur"), community_id(db, "flomo")
    headers, _ = signup(client, "Sam", dorm_id=wilbur)
    r = client.patch(
        "/api/me",
        json={"dorm_id": flomo, "bio": "hi", "onboarded": True, "walking_radius_min": 15},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["dorm"]["slug"] == "flomo" and me["bio"] == "hi"
    assert me["onboarded"] is True and me["walking_radius_min"] == 15
    dorms = client.get(
        "/api/communities", params={"mine": True, "kind": "dorm"}, headers=headers
    ).json()
    assert [d["slug"] for d in dorms] == ["flomo"]
    # bio can be cleared with an explicit null; omitted fields stay untouched
    me = client.patch("/api/me", json={"bio": None}, headers=headers).json()
    assert me["bio"] is None and me["walking_radius_min"] == 15


def test_demo_login_only_for_demo_users(client, db):
    from app.core.config import settings
    from app.models import User

    seed_base(db)
    _, real = signup(client, "Real")
    assert client.get("/api/auth/demo-users").json() == []
    assert client.post("/api/auth/demo-login", json={"user_id": real["id"]}).status_code == 404

    user = db.get(User, real["id"])
    user.is_demo = True
    db.commit()
    assert [u["id"] for u in client.get("/api/auth/demo-users").json()] == [real["id"]]
    r = client.post("/api/auth/demo-login", json={"user_id": real["id"]})
    assert r.status_code == 200 and r.json()["user"]["id"] == real["id"]

    settings.demo_mode = False
    try:
        assert client.get("/api/auth/demo-users").status_code == 404
        assert client.post("/api/auth/demo-login", json={"user_id": real["id"]}).status_code == 404
    finally:
        settings.demo_mode = True


def test_public_profile(client, db):
    seed_base(db)
    headers, _ = signup(client, "A")
    _, other = signup(client, "Other", dorm_id=community_id(db, "roble"))
    r = client.get(f"/api/users/{other['id']}", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Other" and body["dorm_name"] == "Roble Hall"
    assert "email" not in body
    assert client.get("/api/users/99999", headers=headers).status_code == 404
    assert client.get(f"/api/users/{other['id']}/reviews", headers=headers).json() == []
