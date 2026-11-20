"""`seed --sync-base`: new dorms reach a database that is already in use, and nothing is lost."""

from sqlalchemy import delete, func, select

from app.models import Community, Item, Membership, User
from app.seed.seed import sync_base
from tests.core.factories import community_id, seed_base, signup

EVGR = ["evgr-a", "evgr-b", "evgr-c", "evgr-d"]


def post_item(client, headers, name: str) -> None:
    body = {"name": name, "category": "dorm", "transaction_type": "lend", "visibility": "campus"}
    assert client.post("/api/items", headers=headers, json=body).status_code == 201


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_sync_adds_missing_dorms_and_keeps_everything_else(client, db):
    seed_base(db)
    headers, me = signup(client, "Rae", dorm_id=community_id(db, "wilbur"))
    post_item(client, headers, "Kettle")
    group = client.post(
        "/api/communities",
        headers=headers,
        json={"name": "Robotics", "group_type": "club", "is_private": False},
    ).json()
    # An older database: the EVGR dorms don't exist yet, and Wilbur was renamed by hand.
    db.execute(delete(Community).where(Community.slug.in_(EVGR)))
    db.get(Community, community_id(db, "wilbur")).name = "Wilbur (old name)"
    db.commit()
    before = (count(db, User), count(db, Item), count(db, Membership))

    assert sync_base() == {"communities added": 4, "dorms now": 39}
    assert sync_base() == {"communities added": 0, "dorms now": 39}  # running it again is harmless
    db.expire_all()
    assert (count(db, User), count(db, Item), count(db, Membership)) == before
    assert db.get(Community, group["id"]).name == "Robotics"  # people's own groups are untouched
    assert db.get(Community, community_id(db, "wilbur")).name == "Wilbur Hall"
    dorm = client.get("/api/me", headers=headers).json()["dorm"]
    assert dorm["slug"] == "wilbur"  # nobody is moved out of their dorm


def test_evgr_dorms_work_for_signup_switching_and_walking_minutes(client, db):
    seed_base(db)
    dorms = client.get("/api/communities", params={"kind": "dorm"}, headers=signup(client)[0])
    by_slug = {c["slug"]: c for c in dorms.json()}
    assert [by_slug[s]["name"] for s in EVGR] == ["EVGR A", "EVGR B", "EVGR C", "EVGR D"]
    assert all(by_slug[s]["lat"] and by_slug[s]["lng"] and by_slug[s]["emoji"] for s in EVGR)

    a, a_me = signup(client, "Ada", dorm_id=by_slug["evgr-a"]["id"])  # the signup dorm picker
    assert a_me["dorm"]["slug"] == "evgr-a"
    seen = {c["slug"]: c for c in client.get("/api/communities", headers=a).json()}
    assert seen["evgr-a"]["distance_min"] is None or seen["evgr-a"]["distance_min"] <= 1
    assert 1 <= seen["evgr-b"]["distance_min"] < seen["evgr-d"]["distance_min"] <= 8  # A→B→C→D
    assert 12 <= seen["flomo"]["distance_min"] <= 30  # across campus

    moved = client.patch("/api/me", headers=a, json={"dorm_id": by_slug["evgr-d"]["id"]})
    assert moved.json()["dorm"]["slug"] == "evgr-d"  # the profile dorm switcher
    page = client.get("/api/communities/evgr-d", headers=a).json()  # the community page
    assert page["member_count"] == 1 and page["is_member"] is True
    assert client.get("/api/communities/evgr-a", headers=a).json()["member_count"] == 0

    w, _ = signup(client, "Wes", dorm_id=by_slug["wilbur"]["id"])
    post_item(client, a, "Rice cooker")
    found = client.get("/api/search", headers=w, params={"q": "rice cooker"}).json()["items"]
    assert found and found[0]["distance_min"] and found[0]["distance_min"] >= 5


def test_a_group_that_already_uses_the_slug_is_left_alone(client, db, capsys):
    seed_base(db)
    db.execute(delete(Community).where(Community.slug == "evgr-a"))
    db.add(Community(slug="evgr-a", name="EVGR A board games", kind="group", group_type="club"))
    db.commit()
    assert sync_base() == {"communities added": 0, "dorms now": 38}
    assert "evgr-a" in capsys.readouterr().out
    db.expire_all()
    mine = db.scalar(select(Community).where(Community.slug == "evgr-a"))
    assert mine.kind == "group" and mine.name == "EVGR A board games"


GRAD = [
    "ev-blackwelder", "ev-quillen", "ev-abrams", "ev-barnes", "ev-hoskins", "ev-hulme",
    "ev-mcfarland", "ev-studio-1", "ev-studio-2", "ev-studio-3", "ev-studio-4", "ev-studio-5",
    "ev-studio-6", "kennedy", "rains", "lyman", "munger", "schwab", "jack-mcdonald", "highland",
]  # fmt: skip


def test_graduate_residences_reach_a_live_database_and_work_like_any_dorm(client, db):
    seed_base(db)
    headers, _ = signup(client, "Rae", dorm_id=community_id(db, "wilbur"))
    post_item(client, headers, "Kettle")
    db.execute(delete(Community).where(Community.slug.in_(GRAD)))  # a database from before
    db.commit()
    before = (count(db, User), count(db, Item), count(db, Membership))
    assert sync_base() == {"communities added": 20, "dorms now": 39}
    assert sync_base() == {"communities added": 0, "dorms now": 39}
    db.expire_all()
    assert (count(db, User), count(db, Item), count(db, Membership)) == before

    dorms = client.get("/api/communities", params={"kind": "dorm"}, headers=headers).json()
    by_slug = {c["slug"]: c for c in dorms}
    assert all(by_slug[s]["lat"] and by_slug[s]["lng"] and by_slug[s]["emoji"] for s in GRAD)
    assert len({c["name"] for c in dorms}) == len(dorms)  # no two dorms share a name

    m, m_me = signup(client, "Mo", dorm_id=by_slug["munger"]["id"])  # the signup dorm picker
    assert m_me["dorm"]["slug"] == "munger"
    seen = {c["slug"]: c for c in client.get("/api/communities", headers=m).json()}
    assert 1 <= seen["rains"]["distance_min"] <= 15  # Munger → Rains: a short walk
    assert seen["lyman"]["distance_min"] > seen["rains"]["distance_min"]  # Lyman is the far west
    assert seen["ev-studio-5"]["distance_min"] >= seen["ev-blackwelder"]["distance_min"]

    moved = client.patch("/api/me", headers=m, json={"dorm_id": by_slug["lyman"]["id"]})
    assert moved.json()["dorm"]["slug"] == "lyman"  # the profile dorm switcher
    page = client.get("/api/communities/lyman", headers=m).json()  # the community page
    assert page["member_count"] == 1 and page["is_member"] is True
