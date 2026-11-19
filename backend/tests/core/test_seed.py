from sqlalchemy import func, select

from app.models import (
    Community,
    Item,
    ItemRequest,
    Place,
    PointsLedger,
    Review,
    Transaction,
    User,
    UserBadge,
)
from app.seed.seed import run


def _login(client, who):
    r = client.post("/api/auth/login", json={"email": f"{who}@demo.daha", "password": "daha-demo"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]


def test_seed_runs_twice_cleanly_and_is_deterministic(db):
    first = run(do_reset=True)
    snapshot = db.execute(select(Item.id, Item.name, Item.owner_id, Item.visibility)).all()
    db.rollback()  # release our read snapshot, or the next TRUNCATE would wait on it forever
    second = run(do_reset=True)
    assert first == second
    assert db.execute(select(Item.id, Item.name, Item.owner_id, Item.visibility)).all() == snapshot
    db.rollback()
    # running again without --reset adds nothing
    assert run() == second

    assert first["users"] == 30 and first["places"] == 6
    assert (
        db.scalar(select(func.count()).select_from(Community).where(Community.kind == "campus"))
        == 1
    )
    assert (
        db.scalar(select(func.count()).select_from(Community).where(Community.kind == "dorm")) == 19
    )
    assert (
        db.scalar(select(func.count()).select_from(Community).where(Community.kind == "group")) == 6
    )
    assert db.scalar(select(func.count()).select_from(Place)) == 6

    public = db.scalar(select(func.count()).select_from(Item).where(Item.visibility != "private"))
    private = db.scalar(select(func.count()).select_from(Item).where(Item.visibility == "private"))
    assert 140 <= public <= 160 and 18 <= private <= 24
    assert (
        db.scalar(select(func.count()).select_from(ItemRequest).where(ItemRequest.status == "open"))
        >= 25
    )
    assert (
        db.scalar(
            select(func.count()).select_from(Transaction).where(Transaction.status == "completed")
        )
        == 10
    )
    # no real-looking emails, ever
    assert all(e.endswith("@demo.daha") for e in db.scalars(select(User.email)))
    assert all(db.scalars(select(User.is_demo)))


def test_seed_hero_accounts_and_consistent_reputation(client, db):
    run(do_reset=True)
    maya_h, maya = _login(client, "maya")
    jordan_h, jordan = _login(client, "jordan")
    sam_h, sam = _login(client, "sam")

    assert maya["dorm"]["slug"] == "wilbur" and maya["items_shared_count"] == 12
    assert {b["code"] for b in maya["badges"]} == {"first_share", "first_lend", "trusted"}
    assert maya["rating_count"] == 5 and maya["rating_avg"] == 4.8
    # 12 items ×2 + 5 lends ×10 + request bonus 5 + 5 good reviews ×2
    assert maya["points"] == 24 + 50 + 5 + 10 and maya["level"]["name"] == "Helper"
    assert maya["completed_count"] == 5 and maya["unread_notifications"] == 1
    assert maya["unread_messages"] == 1  # Ethan's borrow request is waiting

    assert jordan["dorm"]["slug"] == "flomo"
    assert jordan["unread_notifications"] == 1 and jordan["unread_messages"] == 1
    assert sam["dorm"]["slug"] == "wilbur" and sam["onboarded"] is False
    assert client.get("/api/me/items", headers=sam_h).json() == []

    binder = db.execute(
        select(ItemRequest).where(ItemRequest.seed_key == "request:jordan-binder")
    ).scalar_one()
    assert binder.requester_id == jordan["id"]
    assert binder.raw_text == "Can I borrow a black binder next Wednesday?"
    assert binder.needed_from.weekday() == 2 and binder.status == "open"

    # every badge row is one the rules actually grant, and points equal the ledger
    from app.services.points import _earned_codes

    for user in db.execute(select(User)).scalars():
        have = set(db.scalars(select(UserBadge.code).where(UserBadge.user_id == user.id)))
        assert have == _earned_codes(db, user.id), user.name
    good_reviews = db.scalar(select(func.count()).select_from(Review).where(Review.rating >= 4))
    assert (
        db.scalar(
            select(func.count())
            .select_from(PointsLedger)
            .where(PointsLedger.reason == "good_review")
        )
        == good_reviews
    )

    # the demo logins are listed for one-tap login, heroes first
    demo = client.get("/api/auth/demo-users").json()
    assert [u["name"] for u in demo[:3]] == ["Maya C.", "Jordan R.", "Sam T."]


def test_seed_supports_the_demo_queries_and_privacy(client, db):
    run(do_reset=True)
    sam_h, sam = _login(client, "sam")  # Wilbur
    jordan_h, _ = _login(client, "jordan")  # FloMo

    def visible_names(headers, viewer_dorm_only=False):
        names = []
        for item_id, name, vis in db.execute(select(Item.id, Item.name, Item.visibility)).all():
            if viewer_dorm_only and vis != "dorm":
                continue
            if client.get(f"/api/items/{item_id}", headers=headers).status_code == 200:
                names.append(name.lower())
        return names

    sam_sees = visible_names(sam_h)
    assert sum("binder" in n and "black" in n for n in sam_sees) >= 2
    assert sum("graphing calculator" in n for n in sam_sees) >= 2
    assert any("navy suit" in n for n in sam_sees) and any("blazer" in n for n in sam_sees)
    assert any("moving boxes" in n for n in sam_sees)
    assert any("bike repair" in n for n in sam_sees)
    assert sum("vacuum" in n for n in visible_names(sam_h, viewer_dorm_only=True)) == 2

    # Maya's Wilbur-only vacuum is hidden from FloMo; her campus binder is not
    vacuum = db.execute(select(Item).where(Item.seed_key == "item:maya-vacuum")).scalar_one()
    binder = db.execute(select(Item).where(Item.seed_key == "item:maya-black-binder")).scalar_one()
    assert client.get(f"/api/items/{vacuum.id}", headers=jordan_h).status_code == 404
    assert client.get(f"/api/items/{binder.id}", headers=jordan_h).status_code == 200

    # private haves exist but nobody else can see them
    pump = (
        db.execute(select(Item).where(Item.visibility == "private", Item.name == "Bike pump"))
        .scalars()
        .first()
    )
    assert client.get(f"/api/items/{pump.id}", headers=sam_h).status_code == 404
    listed = client.get(f"/api/users/{pump.owner_id}/items", headers=sam_h).json()["items"]
    assert pump.id not in [i["id"] for i in listed]
