"""Condition check on loans: flag, permissions, the flow, no points, photos deleted at the end."""

import pytest

from app.core.config import settings
from app.models import Upload
from tests.ai.helpers import photo
from tests.core.factories import community_id, seed_base, signup


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(settings, "condition_check_enabled", True)


@pytest.fixture
def w(client, db):
    seed_base(db)
    oh, _ = signup(client, "Maya Owner", dorm_id=community_id(db, "wilbur"))
    bh, _ = signup(client, "Jordan Borrower", dorm_id=community_id(db, "flomo"))
    th, _ = signup(client, "Third Wheel", dorm_id=community_id(db, "flomo"))
    return {"oh": oh, "bh": bh, "th": th}


def loan(client, w, kind="lend"):
    item = client.post(
        "/api/items",
        json={
            "name": "Desk lamp",
            "category": "dorm",
            "transaction_type": kind,
            "visibility": "campus",
        },
        headers=w["oh"],
    ).json()
    tx = client.post(f"/api/items/{item['id']}/borrow", json={}, headers=w["bh"]).json()
    act(client, tx["id"], w["oh"], "accept")
    return tx["id"]


def act(client, tx_id, headers, action):
    r = client.post(f"/api/transactions/{tx_id}/actions", json={"action": action}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def snap(client, tx_id, headers, stage, slot, seed=1):
    return client.put(
        f"/api/transactions/{tx_id}/condition/{stage}/{slot}",
        files={"file": (f"{slot}.jpg", photo(seed), "image/jpeg")},
        headers=headers,
    )


def points(client, headers):
    return client.get("/api/me", headers=headers).json()["points"]


def test_off_by_default_hides_everything(client, w, monkeypatch):
    assert type(settings).model_fields["condition_check_enabled"].default is False
    monkeypatch.setattr(settings, "condition_check_enabled", False)  # local .env may turn it on
    tx_id = loan(client, w)
    assert client.get(f"/api/transactions/{tx_id}", headers=w["oh"]).json()["condition"] is None
    assert snap(client, tx_id, w["oh"], "handoff", "front").status_code == 404
    assert (
        client.post(f"/api/transactions/{tx_id}/condition/confirm", headers=w["bh"]).status_code
        == 404
    )


def test_full_flow_sample_result_no_points_and_photos_deleted(client, db, w, on):
    tx_id = loan(client, w)
    tx = client.get(f"/api/transactions/{tx_id}", headers=w["oh"]).json()
    assert tx["condition"]["status"] == "waiting" and tx["condition"]["can_add_handoff_photos"]

    # only the lender adds handoff photos; the borrower can't confirm until all 3 are in
    assert snap(client, tx_id, w["bh"], "handoff", "front").status_code == 409
    for n, slot in enumerate(("front", "back"), 1):
        assert snap(client, tx_id, w["oh"], "handoff", slot, n).status_code == 200
    assert (
        client.post(f"/api/transactions/{tx_id}/condition/confirm", headers=w["bh"]).status_code
        == 409
    )
    r = snap(client, tx_id, w["oh"], "handoff", "marks", 3)
    assert r.json()["condition"]["handoff_photos"]["marks"].startswith("/uploads/")

    b = client.get(f"/api/transactions/{tx_id}", headers=w["bh"]).json()["condition"]
    assert b["can_confirm"] and not b["can_add_return_photos"]
    r = client.post(f"/api/transactions/{tx_id}/condition/confirm", headers=w["bh"])
    assert r.status_code == 200 and r.json()["condition"]["handoff_confirmed_at"]
    assert snap(client, tx_id, w["oh"], "handoff", "front").status_code == 409  # locked now

    act(client, tx_id, w["oh"], "hand_off")
    before = (points(client, w["oh"]), points(client, w["bh"]))
    assert snap(client, tx_id, w["oh"], "return", "front").status_code == 409  # borrower only
    for n, slot in enumerate(("front", "back", "marks"), 1):
        assert snap(client, tx_id, w["bh"], "return", slot, n).status_code == 200

    # the 3rd return photo starts the comparison; with AI_PROVIDER=mock it's a labeled sample
    for headers in (w["oh"], w["bh"]):
        c = client.get(f"/api/transactions/{tx_id}", headers=headers).json()["condition"]
        assert c["status"] == "done" and c["result"] == "no_changes" and c["sample"] is True
        assert c["note"].startswith("Sample result") and not c["can_add_return_photos"]
    assert (points(client, w["oh"]), points(client, w["bh"])) == before  # never touches points
    again = client.post(f"/api/transactions/{tx_id}/condition/compare", headers=w["oh"])
    assert again.json()["condition"]["checked_at"] == c["checked_at"]  # idempotent

    files = [u.path for u in db.query(Upload).all()]
    assert len(files) == 6
    act(client, tx_id, w["oh"], "mark_returned")
    done = client.get(f"/api/transactions/{tx_id}", headers=w["bh"]).json()["condition"]
    assert done["photos_deleted"] and done["result"] == "no_changes"
    assert done["handoff_photos"] == {"front": None, "back": None, "marks": None}
    assert done["return_photos"] == {"front": None, "back": None, "marks": None}
    db.expire_all()
    assert db.query(Upload).count() == 0
    assert not any((settings.upload_path / f).exists() for f in files)


def test_cancelling_deletes_photos_too(client, db, w, on):
    tx_id = loan(client, w)
    snap(client, tx_id, w["oh"], "handoff", "front")
    act(client, tx_id, w["oh"], "cancel")
    c = client.get(f"/api/transactions/{tx_id}", headers=w["oh"]).json()["condition"]
    assert c["photos_deleted"] and c["handoff_photos"]["front"] is None
    db.expire_all()
    assert db.query(Upload).count() == 0


def test_replacing_a_photo_deletes_the_old_one(client, db, w, on):
    tx_id = loan(client, w)
    snap(client, tx_id, w["oh"], "handoff", "front", 1)
    snap(client, tx_id, w["oh"], "handoff", "front", 2)
    db.expire_all()
    assert db.query(Upload).count() == 1


def test_gives_have_no_condition_check_and_strangers_get_404(client, w, on):
    give_id = loan(client, w, kind="give")
    assert client.get(f"/api/transactions/{give_id}", headers=w["oh"]).json()["condition"] is None
    assert snap(client, give_id, w["oh"], "handoff", "front").status_code == 409
    tx_id = loan(client, w)
    assert snap(client, tx_id, w["th"], "handoff", "front").status_code == 404


def test_bad_slot_and_bad_file(client, w, on):
    tx_id = loan(client, w)
    assert snap(client, tx_id, w["oh"], "handoff", "side").status_code == 422
    r = client.put(
        f"/api/transactions/{tx_id}/condition/handoff/front",
        files={"file": ("x.txt", b"not an image", "text/plain")},
        headers=w["oh"],
    )
    assert r.status_code == 400
