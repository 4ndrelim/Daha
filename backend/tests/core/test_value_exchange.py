"""Value exchange (VALUE_EXCHANGE_ENABLED + ITEM_VALUE_ENABLED): estimates only, no money moves."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app import schemas
from app.core.config import settings
from app.discovery import commercial
from app.models import Item, PointsLedger, Transaction
from app.services import value_exchange as vx
from tests.core.factories import community_id, seed_base, signup


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(settings, "item_value_enabled", True)
    monkeypatch.setattr(settings, "value_exchange_enabled", True)
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
    assert tx["value"] is None
    assert db.get(Transaction, tx["id"]).value_usd is None, "nothing stored while off"
    assert not bonus(db)
    m = me(client, w["oh"])
    assert m["value_exchange_enabled"] is False
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
    assert v["value_usd"] == 45
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
    assert me(client, w["oh"])["value_shared_usd"] == 45
    assert me(client, w["bh"])["value_shared_usd"] == 0, "the borrower shared nothing"
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
    assert me(client, w["bh"])["value_shared_usd"] == 0


def test_bonus_rate_cap_repeat_and_swaps(client, db, w, on):
    assert vx.bonus_points(19) == 0 and vx.bonus_points(45) == 2 and vx.bonus_points(150) == 7
    assert vx.bonus_points(2000) == 30 and vx.bonus_points(0) == 0 and vx.bonus_points(None) == 0
    bike = finish(client, w["oh"], w["bh"], make(client, w["oh"], name="Bike", value_usd=900))
    assert bike["value"]["bonus_points"] == 30, "capped at 30 per exchange"
    again = finish(client, w["oh"], w["bh"], make(client, w["oh"], name="Fan", value_usd=60))
    assert again["value"]["bonus_points"] == 3, "no extra anti-gaming rules in this version"
    gift = make(client, w["oh"], name="Mini fridge", transaction_type="give", value_usd=80)
    assert finish(client, w["oh"], w["bh"], gift, kind="give")["value"]["bonus_points"] == 4
    swap = make(
        client,
        w["others"][0],
        name="Board game",
        category="events",
        transaction_type="exchange",
        value_usd=40,
    )
    tx = finish(client, w["others"][0], w["others"][1], swap, kind="exchange")
    rows = [p.delta for p in bonus(db) if p.ref_id == tx["id"]]
    assert sorted(rows) == [2, 2], "both people in a swap"


def test_self_exchange_never_earns_or_counts(client, db, w, on):
    tx = Transaction(owner_id=1, borrower_id=1, value_usd=500, kind="lend")
    assert vx.no_bonus_reason(tx) == "self"
    # Even if one sneaks into the table, totals ignore it.
    lamp = make(client, w["oh"], value_usd=70)
    real = finish(client, w["oh"], w["bh"], lamp)
    row = db.get(Transaction, real["id"])
    row.borrower_id = row.owner_id
    db.commit()
    assert me(client, w["oh"])["value_shared_usd"] == 0


def test_no_value_no_bonus_and_no_receipt_before_done(client, w, on):
    plain = finish(client, w["oh"], w["bh"], make(client, w["oh"], name="Ruler"))
    assert plain["value"] == {"value_usd": None, "bonus_points": 0, "no_bonus_reason": "no_value"}
    lamp = make(client, w["oh"], value_usd=30)
    tx = client.post(f"/api/items/{lamp['id']}/borrow", json={}, headers=w["bh"]).json()
    assert tx["value"] is None, "the receipt only comes once it's done"


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
