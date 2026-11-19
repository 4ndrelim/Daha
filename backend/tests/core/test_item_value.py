"""Item value (ITEM_VALUE_ENABLED): optional estimated new price, display only, never points."""

import pytest
from sqlalchemy import select

from app.ai import normalize, prompts
from app.core.config import settings
from app.models import Item, ScanDetection
from tests.ai.helpers import upload, user_in_wilbur
from tests.core.factories import community_id, seed_base, signup


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(settings, "item_value_enabled", True)


@pytest.fixture
def w(client, db):
    seed_base(db)
    oh, owner = signup(client, "Maya Owner", dorm_id=community_id(db, "wilbur"))
    bh, _ = signup(client, "Jordan Borrower", dorm_id=community_id(db, "flomo"))
    return {"oh": oh, "bh": bh, "owner": owner}


def make(client, headers, **kw):
    body = {"name": "Desk lamp", "category": "dorm", "transaction_type": "lend"}
    body |= {"visibility": "campus", **kw}
    return client.post("/api/items", json=body, headers=headers)


def me(client, headers):
    return client.get("/api/me", headers=headers).json()


def test_off_by_default_ignores_and_hides_value(client, db, w, monkeypatch):
    assert type(settings).model_fields["item_value_enabled"].default is False
    monkeypatch.setattr(settings, "item_value_enabled", False)  # a local .env may turn it on
    r = make(client, w["oh"], value_usd=40)
    assert r.status_code == 201, r.text
    assert r.json()["value_usd"] is None
    assert db.get(Item, r.json()["id"]).value_usd is None  # not stored while off
    m = me(client, w["oh"])
    assert m["item_value_enabled"] is False and m["value_shared_usd"] is None
    assert "Worth" not in prompts.vision_task("x.jpg") and "value_usd" not in prompts.vision_task(
        "x.jpg"
    )
    assert prompts.prompt_version() == "vision-v1"


def test_create_edit_clear_and_validate(client, w, on):
    item = make(client, w["oh"], value_usd=40).json()
    assert item["value_usd"] == 40
    assert me(client, w["oh"])["item_value_enabled"] is True
    # Other people see it on the card and the item page.
    assert client.get(f"/api/items/{item['id']}", headers=w["bh"]).json()["value_usd"] == 40

    r = client.patch(f"/api/items/{item['id']}", json={"value_usd": 55}, headers=w["oh"])
    assert r.status_code == 200 and r.json()["value_usd"] == 55
    r = client.patch(f"/api/items/{item['id']}", json={"name": "Lamp"}, headers=w["oh"])
    assert r.json()["value_usd"] == 55, "an edit that doesn't send it keeps it"
    r = client.patch(f"/api/items/{item['id']}", json={"value_usd": None}, headers=w["oh"])
    assert r.json()["value_usd"] is None, "null clears it"

    assert make(client, w["oh"]).json()["value_usd"] is None, "optional"
    assert make(client, w["oh"], value_usd=0).json()["value_usd"] == 0
    assert make(client, w["oh"], value_usd=10000).json()["value_usd"] == 10000
    for bad in (-1, 10001, 12.5, "lots"):
        assert make(client, w["oh"], value_usd=bad).status_code == 422, bad
    r = client.patch(f"/api/items/{item['id']}", json={"value_usd": 20000}, headers=w["oh"])
    assert r.status_code == 422


def test_never_changes_points(client, w, on):
    make(client, w["oh"], name="Warm-up")  # first-item bonuses out of the way
    p0 = me(client, w["oh"])["points"]
    make(client, w["oh"], name="Ruler")
    p1 = me(client, w["oh"])["points"]
    make(client, w["oh"], name="Laptop stand", value_usd=9999)
    p2 = me(client, w["oh"])["points"]
    assert p2 - p1 == p1 - p0, "an item with a value earns the same points as one without"


def act(client, tx_id, headers, action):
    r = client.post(f"/api/transactions/{tx_id}/actions", json={"action": action}, headers=headers)
    assert r.status_code == 200, r.text


def lend_and_finish(client, w, item_id, finish=True):
    tx = client.post(f"/api/items/{item_id}/borrow", json={}, headers=w["bh"]).json()
    act(client, tx["id"], w["oh"], "accept")
    if finish:
        act(client, tx["id"], w["oh"], "hand_off")
        act(client, tx["id"], w["oh"], "mark_returned")
    return tx["id"]


def test_value_shared_counts_only_completed_exchanges(client, w, on):
    lamp = make(client, w["oh"], value_usd=40).json()
    kettle = make(client, w["oh"], name="Kettle", value_usd=25).json()
    plain = make(client, w["oh"], name="Ruler").json()  # no value: adds nothing
    assert me(client, w["oh"])["value_shared_usd"] == 0

    lend_and_finish(client, w, lamp["id"])
    lend_and_finish(client, w, plain["id"])
    lend_and_finish(client, w, kettle["id"], finish=False)  # accepted, not completed
    assert me(client, w["oh"])["value_shared_usd"] == 40
    lend_and_finish(client, w, lamp["id"])  # lent again: counts again
    assert me(client, w["oh"])["value_shared_usd"] == 80
    # The borrower didn't share anything; the public profile shows the same total.
    assert me(client, w["bh"])["value_shared_usd"] == 0
    public = client.get(f"/api/users/{w['owner']['id']}", headers=w["bh"]).json()
    assert public["value_shared_usd"] == 80


# ---------------------------------------------------------------- scan
def test_normalize_value_never_invents():
    def v(raw):
        return normalize.coerce_item({"name": "Desk lamp", "value_usd": raw}).value_usd

    assert v(25) == 25 and v(24.6) == 25 and v("$1,200") == 1200 and v("30 USD") == 30
    for bad in (None, "", "about twenty", -5, 10001, True, float("nan"), [3]):
        assert v(bad) is None, bad
    assert normalize.coerce_item({"name": "Desk lamp"}).value_usd is None


def test_prompt_asks_for_value_only_when_on(on):
    task = prompts.vision_task("x.jpg")
    assert '"value_usd"' in task and "whole dollars" in task
    assert "value_usd" in prompts.vision_task_inline()
    assert prompts.prompt_version() == "vision-v1+value"


def _scan(client, headers):
    ids = [upload(client, headers, 1)]
    r = client.post("/api/scans", headers=headers, json={"upload_ids": ids})
    assert r.status_code == 201, r.text
    return client.get(f"/api/scans/{r.json()['id']}", headers=headers).json()


def test_mock_scan_leaves_value_empty_and_publish_keeps_edits(client, db, on):
    headers, _ = user_in_wilbur(client, db)
    scan = _scan(client, headers)
    dets = scan["detections"]
    assert dets and all(d["value_estimate_usd"] is None for d in dets), "AI off: no values"
    a, b = dets[0], dets[1]

    def entry(d, **kw):
        return {
            "detection_id": d["id"],
            "name": d["name"],
            "category": d["category"],
            "transaction_type": "give" if d["category"] == "services" else "lend",
            "visibility": "dorm",
            **kw,
        }

    r = client.post(
        f"/api/scans/{scan['id']}/publish",
        headers=headers,
        json={"items": [entry(a, value_usd=30), entry(b)]},
    )
    assert r.status_code == 200, r.text
    got = r.json()["items"]
    assert got[0]["value_usd"] == 30 and got[1]["value_usd"] is None
    rows = {d.id: d for d in db.scalars(select(ScanDetection))}
    assert rows[a["id"]].edits.get("value_usd") == {"from": None, "to": 30}
    assert "value_usd" not in (rows[b["id"]].edits or {})


def test_scan_shows_ai_estimate_when_on(client, db, on, monkeypatch):
    from app.ai.providers import mock as mock_provider

    real = mock_provider.MockVisionProvider.detect

    async def with_values(self, image, filename):
        result = await real(self, image, filename)
        for n, item in enumerate(result.items):
            item.value_usd = 20 + n
        return result

    monkeypatch.setattr(mock_provider.MockVisionProvider, "detect", with_values)
    headers, _ = user_in_wilbur(client, db)
    dets = _scan(client, headers)["detections"]
    assert dets and all(isinstance(d["value_estimate_usd"], int) for d in dets)

    monkeypatch.setattr(settings, "item_value_enabled", False)
    scan_id = db.scalar(select(ScanDetection.scan_id))
    hidden = client.get(f"/api/scans/{scan_id}", headers=headers).json()["detections"]
    assert all(d["value_estimate_usd"] is None for d in hidden), "flag off hides estimates"
