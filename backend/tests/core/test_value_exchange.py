"""Value exchange (VALUE_EXCHANGE_ENABLED + ITEM_VALUE_ENABLED): estimates only, no money moves."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app import schemas
from app.core.config import settings
from app.discovery import commercial
from app.models import Event, Item, PointsLedger, Transaction
from app.services import value_exchange as vx
from tests.ai.helpers import photo
from tests.core.factories import community_id, seed_base, signup


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(settings, "item_value_enabled", True)
    monkeypatch.setattr(settings, "value_exchange_enabled", True)
    monkeypatch.setattr(settings, "condition_check_enabled", False)  # a local .env may turn it on
    monkeypatch.setattr(settings, "commercial_provider", "mock")


@pytest.fixture
def w(client, db):
    seed_base(db)
    wilbur, flomo = community_id(db, "wilbur"), community_id(db, "flomo")
    oh, _ = signup(client, "Maya Owner", dorm_id=wilbur)
    bh, _ = signup(client, "Jordan Borrower", dorm_id=flomo)
    others = [signup(client, f"Neighbor {n}", dorm_id=flomo)[0] for n in range(5)]
    return {"oh": oh, "bh": bh, "others": others}


def make(client, headers, **kw):
    body = {"name": "Desk lamp", "category": "dorm", "transaction_type": "lend"}
    body |= {"visibility": "campus", **kw}
    r = client.post("/api/items", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def act(client, tx_id, headers, action, ok=True):
    r = client.post(f"/api/transactions/{tx_id}/actions", json={"action": action}, headers=headers)
    if ok:
        assert r.status_code == 200, r.text
    return r


def finish(client, oh, bh, item, kind="lend"):
    tx = client.post(f"/api/items/{item['id']}/borrow", json={}, headers=bh).json()
    act(client, tx["id"], oh, "accept")
    act(client, tx["id"], oh, "hand_off")
    if kind == "lend":
        act(client, tx["id"], oh, "mark_returned")
    return client.get(f"/api/transactions/{tx['id']}", headers=oh).json()


def bonus(db):
    q = select(PointsLedger).where(PointsLedger.reason == vx.BONUS_REASON)
    return list(db.scalars(q))


def me(client, h):
    return client.get("/api/me", headers=h).json()


def test_off_by_default(client, db, w, monkeypatch):
    assert type(settings).model_fields["value_exchange_enabled"].default is False
    monkeypatch.setattr(settings, "item_value_enabled", True)
    monkeypatch.setattr(settings, "value_exchange_enabled", False)
    tx = finish(client, w["oh"], w["bh"], make(client, w["oh"], value_usd=200))
    assert tx["value"] is None and tx["item"]["high_value"] is False
    assert db.get(Transaction, tx["id"]).value_usd is None, "no snapshot while off"
    assert not bonus(db)
    m = me(client, w["oh"])
    assert m["value_exchange_enabled"] is False and m["value_received_usd"] is None
    home = client.get("/api/feed/home", headers=w["oh"]).json()
    assert home["stats"]["dorm_value_shared_month_usd"] is None
    # Needs item value too.
    monkeypatch.setattr(settings, "item_value_enabled", False)
    monkeypatch.setattr(settings, "value_exchange_enabled", True)
    assert vx.enabled() is False


def test_lend_receipt_snapshot_bonus_and_totals(client, db, w, on):
    lamp = make(client, w["oh"], value_usd=45)
    tx = finish(client, w["oh"], w["bh"], lamp)
    v = tx["value"]
    assert v["value_usd"] == 45 and v["high_value"] is False
    assert v["bonus_points"] == 2, "1 point per $20"
    assert v["no_bonus_reason"] is None
    # The borrower gets no value bonus on a lend.
    assert (
        client.get(f"/api/transactions/{tx['id']}", headers=w["bh"]).json()["value"]["bonus_points"]
        == 0
    )
    # Later edits don't change the frozen value.
    client.patch(f"/api/items/{lamp['id']}", json={"value_usd": 90}, headers=w["oh"])
    assert db.get(Transaction, tx["id"]).value_usd == 45
    m, b = me(client, w["oh"]), me(client, w["bh"])
    assert (m["value_shared_usd"], m["value_received_usd"]) == (45, 0)
    assert (b["value_shared_usd"], b["value_received_usd"]) == (0, 45)
    home = client.get("/api/feed/home", headers=w["oh"]).json()
    assert home["stats"]["dorm_value_shared_month_usd"] == 45, "Wilbur shared it this month"
    flomo_home = client.get("/api/feed/home", headers=w["bh"]).json()
    assert flomo_home["stats"]["dorm_value_shared_month_usd"] == 0


def test_unfinished_exchanges_count_for_nothing(client, w, on):
    lamp = make(client, w["oh"], value_usd=45)
    tx = client.post(f"/api/items/{lamp['id']}/borrow", json={}, headers=w["bh"]).json()
    act(client, tx["id"], w["oh"], "accept")
    act(client, tx["id"], w["oh"], "hand_off")
    assert me(client, w["oh"])["value_shared_usd"] == 0
    other = make(client, w["oh"], name="Kettle", value_usd=30)
    t2 = client.post(f"/api/items/{other['id']}/borrow", json={}, headers=w["bh"]).json()
    act(client, t2["id"], w["oh"], "decline")
    assert me(client, w["bh"])["value_received_usd"] == 0


def test_high_value_rate_cap_and_badge(client, db, w, on):
    cam = make(client, w["oh"], name="Camera", category="tech", value_usd=150)
    assert cam["high_value"] is True
    assert client.get(f"/api/items/{cam['id']}", headers=w["bh"]).json()["high_value"] is True
    tx = finish(client, w["oh"], w["bh"], cam)
    assert tx["value"]["high_value"] is True and tx["value"]["bonus_points"] == 15, "1 per $10"
    assert vx.bonus_points(99) == 4 and vx.bonus_points(100) == 10
    assert vx.bonus_points(2000) == 30 and vx.bonus_points(0) == 0 and vx.bonus_points(None) == 0


def test_weekly_cap_and_repeat_pairs(client, db, w, on):
    # Same pair again within 7 days: no bonus the second time.
    a = finish(client, w["oh"], w["bh"], make(client, w["oh"], name="Speaker", value_usd=60))
    b = finish(client, w["oh"], w["bh"], make(client, w["oh"], name="Fan", value_usd=60))
    assert a["value"]["bonus_points"] == 3
    assert b["value"]["bonus_points"] == 0 and b["value"]["no_bonus_reason"] == "repeat"
    # 30 a time to 4 different people: 3, 30, 30, 30 → 93, then only 7 more fit under 100.
    got = []
    for n, h in enumerate(w["others"][:4]):
        item = make(client, w["oh"], name=f"Bike {n}", category="sports", value_usd=800)
        got.append(finish(client, w["oh"], h, item)["value"]["bonus_points"])
    assert got == [30, 30, 30, 7]
    total = sum(p.delta for p in bonus(db))
    assert total == 100


def test_give_and_swap_values(client, db, w, on):
    gift = make(client, w["oh"], name="Mini fridge", transaction_type="give", value_usd=80)
    g = finish(client, w["oh"], w["bh"], gift, kind="give")
    assert g["value"]["value_usd"] == 80 and g["value"]["bonus_points"] == 4

    swap = make(
        client,
        w["others"][0],
        name="Board game",
        category="events",
        transaction_type="exchange",
        value_usd=40,
    )
    tx = client.post(f"/api/items/{swap['id']}/borrow", json={}, headers=w["others"][1]).json()
    assert tx["value"]["can_set_swap_value"] is True
    # Only the borrower may say what their side is worth, and only before it's done.
    r = client.post(
        f"/api/transactions/{tx['id']}/swap-value", json={"value_usd": 25}, headers=w["others"][0]
    )
    assert r.status_code == 403
    for bad in (-1, 10001):
        r = client.post(
            f"/api/transactions/{tx['id']}/swap-value",
            json={"value_usd": bad},
            headers=w["others"][1],
        )
        assert r.status_code == 422
    r = client.post(
        f"/api/transactions/{tx['id']}/swap-value", json={"value_usd": 25}, headers=w["others"][1]
    )
    assert r.status_code == 200 and r.json()["value"]["difference_usd"] == 15
    act(client, tx["id"], w["others"][0], "accept")
    done = act(client, tx["id"], w["others"][0], "hand_off").json()
    assert done["value"]["value_usd"] == 40 and done["value"]["swap_value_usd"] == 25
    assert done["value"]["can_set_swap_value"] is False
    r = client.post(
        f"/api/transactions/{tx['id']}/swap-value", json={"value_usd": 999}, headers=w["others"][1]
    )
    assert r.status_code == 409, "locked once it's done"
    owner, borrower = me(client, w["others"][0]), me(client, w["others"][1])
    assert (owner["value_shared_usd"], owner["value_received_usd"]) == (40, 25)
    assert (borrower["value_shared_usd"], borrower["value_received_usd"]) == (25, 40)
    # Both people in a swap get the bonus (on the listed value: 40 → 2).
    rows = {p.user_id: p.delta for p in bonus(db) if p.ref_id == tx["id"]}
    assert sorted(rows.values()) == [2, 2]
    # Lends have no second side.
    lamp = make(client, w["oh"], value_usd=10)
    t = client.post(f"/api/items/{lamp['id']}/borrow", json={}, headers=w["bh"]).json()
    r = client.post(
        f"/api/transactions/{t['id']}/swap-value", json={"value_usd": 5}, headers=w["bh"]
    )
    assert r.status_code == 409


def test_value_locked_after_someone_asks(client, w, on):
    lamp = make(client, w["oh"], value_usd=30)
    tx = client.post(f"/api/items/{lamp['id']}/borrow", json={}, headers=w["bh"]).json()
    detail = client.get(f"/api/items/{lamp['id']}", headers=w["oh"]).json()
    assert detail["value_locked"] is True
    r = client.patch(f"/api/items/{lamp['id']}", json={"value_usd": 300}, headers=w["oh"])
    assert r.status_code == 409 and "locked" in r.json()["detail"]
    r = client.patch(f"/api/items/{lamp['id']}", json={"value_usd": 30}, headers=w["oh"])
    assert r.status_code == 200, "sending the same value is fine"
    r = client.patch(f"/api/items/{lamp['id']}", json={"name": "Lamp"}, headers=w["oh"])
    assert r.status_code == 200, "other edits still work"
    act(client, tx["id"], w["bh"], "cancel")
    r = client.patch(f"/api/items/{lamp['id']}", json={"value_usd": 35}, headers=w["oh"])
    assert r.status_code == 200, "unlocked once nobody is waiting"


def test_far_above_typical_is_flagged_and_earns_no_bonus(client, db, w, on):
    pen = make(client, w["oh"], name="Pen", category="consumables", value_usd=5000)
    detail = client.get(f"/api/items/{pen['id']}", headers=w["oh"]).json()
    assert detail["value_under_review"] is True
    other = client.get(f"/api/items/{pen['id']}", headers=w["bh"]).json()
    assert other["value_under_review"] is False, "only the owner sees the review note"
    assert db.scalar(select(Event).where(Event.type == vx.FLAG_EVENT)) is not None
    tx = finish(client, w["oh"], w["bh"], pen)
    assert tx["value"]["bonus_points"] == 0 and tx["value"]["no_bonus_reason"] == "under_review"
    # Fixing the value clears the flag.
    client.patch(f"/api/items/{pen['id']}", json={"value_usd": 3}, headers=w["oh"])
    assert db.get(Item, pen["id"]).value_flagged_at is None
    # With a typical price: over 3x and at least $50 more.
    assert vx.far_above_typical(400, 100, "tech") is True
    assert vx.far_above_typical(290, 100, "tech") is False
    assert vx.far_above_typical(40, 10, "tech") is False, "small numbers need a $50 gap"


def test_self_exchange_never_earns(db):
    tx = Transaction(owner_id=1, borrower_id=1, value_usd=500, kind="lend")
    item = Item(value_usd=500)
    assert vx.no_bonus_reason(db, tx, item) == "self"


def test_high_value_lend_needs_condition_check_before_handoff(client, w, on, monkeypatch):
    monkeypatch.setattr(settings, "condition_check_enabled", True)
    cam = make(client, w["oh"], name="Camera", category="tech", value_usd=300)
    tx = client.post(f"/api/items/{cam['id']}/borrow", json={}, headers=w["bh"]).json()
    accepted = act(client, tx["id"], w["oh"], "accept").json()
    assert accepted["value"]["needs_condition_check"] is True
    assert "hand_off" not in accepted["allowed_actions"]
    assert act(client, tx["id"], w["oh"], "hand_off", ok=False).status_code == 409
    for n, slot in enumerate(("front", "back", "marks")):
        r = client.put(
            f"/api/transactions/{tx['id']}/condition/handoff/{slot}",
            files={"file": (f"{slot}.jpg", photo(n + 1), "image/jpeg")},
            headers=w["oh"],
        )
        assert r.status_code == 200, r.text
    client.post(f"/api/transactions/{tx['id']}/condition/confirm", headers=w["bh"])
    now = client.get(f"/api/transactions/{tx['id']}", headers=w["oh"]).json()
    assert now["value"]["needs_condition_check"] is False and "hand_off" in now["allowed_actions"]
    act(client, tx["id"], w["oh"], "hand_off")
    # Cheaper items, or the condition check being off, never block a hand-off.
    lamp = make(client, w["oh"], value_usd=99)
    t = client.post(f"/api/items/{lamp['id']}/borrow", json={}, headers=w["bh"]).json()
    assert "hand_off" in act(client, t["id"], w["oh"], "accept").json()["allowed_actions"]


def test_starting_estimate_store_then_ai_never_invented(client, db, w, on, monkeypatch):
    h = w["oh"]
    # Mock store results are made up, so they never count.
    r = client.get("/api/items/value-estimate", params={"name": "graphing calculator"}, headers=h)
    assert r.json() == {"value_usd": None, "source": None}
    assert vx.suggest(db, "graphing calculator", 30).model_dump() == {
        "value_usd": 30,
        "source": "ai",
    }
    # A real lookup that's already cached wins, free.
    monkeypatch.setattr(settings, "commercial_provider", "exa")
    words, _ = commercial.search_words("graphing calculator")
    near = commercial._geo(
        settings.commercial_default_label,
        "campus",
        settings.commercial_default_lat,
        settings.commercial_default_lng,
    )

    def offer(price, kind="buy", unit="each", currency="USD"):
        return schemas.CommercialOffer(
            title="x",
            price=price,
            currency=currency,
            price_text=None,
            price_unit=unit,
            offer_type=kind,
            seller="Store",
            location=None,
            url="https://example.com",
            image_url=None,
        )

    offers = [offer(100), offer(120), offer(140), offer(9, kind="rent", unit="day"), offer(None)]
    commercial.cache_put(db, commercial.cache_key("exa", words, near), offers, datetime.now(UTC))
    db.commit()
    r = client.get("/api/items/value-estimate", params={"name": "graphing calculator"}, headers=h)
    assert r.json() == {"value_usd": 120, "source": "store"}, "median of buy prices only"
    r = client.get("/api/items/value-estimate", params={"name": "kayak paddle"}, headers=h)
    assert r.json() == {"value_usd": None, "source": None}, "no cache, no call, no guess"


def test_seed_demo_values_are_marked_and_snapshotted(db):
    from app.seed import seed

    values = seed.demo_values()
    assert values and all(0 <= v <= vx.MAX_VALUE_USD for v in values.values())
    raw = (seed.DATA_DIR / "demo_values.json").read_text()
    assert "DEMO DATA" in raw, "the file says it's demo data"
    seed.run(do_reset=True)
    ti84 = db.scalar(select(Item).where(Item.seed_key == "item:maya-ti84"))
    assert ti84.value_usd == values["maya-ti84"]
    done = db.scalar(
        select(Transaction).where(Transaction.item_id == ti84.id, Transaction.status == "completed")
    )
    assert done.value_usd == ti84.value_usd
