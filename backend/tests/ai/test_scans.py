from sqlalchemy import select

from app.core.config import settings
from app.models import Item, ScanDetection, ScanImage, User
from tests.ai.helpers import upload, user_in_wilbur


def _scan(client, headers, seeds):
    ids = [upload(client, headers, s) for s in seeds]
    r = client.post("/api/scans", headers=headers, json={"upload_ids": ids})
    assert r.status_code == 201, r.text
    # TestClient runs background tasks before returning, so polling once sees the result.
    r = client.get(f"/api/scans/{r.json()['id']}", headers=headers)
    assert r.status_code == 200
    return r.json()


def test_mock_scan_end_to_end(client, db):
    headers, me = user_in_wilbur(client, db)
    scan = _scan(client, headers, [1, 2])
    assert scan["status"] == "done" and scan["provider"] == "mock"
    assert [i["status"] for i in scan["images"]] == ["done", "done"]
    dets = scan["detections"]
    assert len(dets) >= 8 and {d["image_index"] for d in dets} == {0, 1}
    for d in dets:
        assert d["status"] == "pending" and 0 <= d["confidence"] <= 1
        if d["confidence"] < 0.35:
            assert d["suggested_share"] is False

    first, second = dets[0], dets[1]
    items = [
        {
            "detection_id": first["id"],
            "name": "Renamed thing",
            "category": first["category"],
            "quantity": first["quantity"],
            "description": first["description"],
            "condition": first["condition_guess"],
            "transaction_type": "give"
            if first["category"] == "services"
            else first["suggested_transaction_type"],
            "visibility": "dorm",
        },
        {
            "detection_id": second["id"],
            "name": second["name"],
            "category": second["category"],
            "quantity": second["quantity"],
            "description": second["description"],
            "condition": second["condition_guess"],
            "transaction_type": second["suggested_transaction_type"],
            "visibility": "campus",
        },
        {
            "detection_id": None,
            "name": "Something we missed",
            "category": "other",
            "transaction_type": "lend",
            "visibility": "dorm",
        },
    ]
    r = client.post(f"/api/scans/{scan['id']}/publish", headers=headers, json={"items": items})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == 3 and body["points_awarded"] == 6
    assert body["items"][0]["name"] == "Renamed thing" and body["items"][0]["source"] == "scan"
    assert body["items"][0]["images"], "detection items get a (cropped) photo"
    assert body["items"][2]["images"] == []

    rows = {d.id: d for d in db.scalars(select(ScanDetection))}
    assert rows[first["id"]].status == "published"
    assert rows[first["id"]].edits == {"name": {"from": first["name"], "to": "Renamed thing"}}
    assert rows[second["id"]].edits == {}
    assert all(
        d.status == "discarded" for i, d in rows.items() if i not in (first["id"], second["id"])
    )
    item = db.get(Item, body["items"][0]["id"])
    assert item.scan_detection_id == first["id"]
    db.expire_all()
    assert db.get(User, me["id"]).onboarded is True

    again = client.post(f"/api/scans/{scan['id']}/publish", headers=headers, json={"items": items})
    assert again.status_code == 409


def test_scan_is_private_to_its_owner(client, db):
    headers, _ = user_in_wilbur(client, db)
    scan = _scan(client, headers, [3])
    from tests.core.factories import signup

    other, _ = signup(client, "Other")
    assert client.get(f"/api/scans/{scan['id']}", headers=other).status_code == 404
    det = scan["detections"][0]
    r = client.post(
        f"/api/scans/{scan['id']}/publish",
        headers=other,
        json={
            "items": [
                {
                    "detection_id": det["id"],
                    "name": "x",
                    "category": "other",
                    "transaction_type": "lend",
                    "visibility": "campus",
                }
            ]
        },
    )
    assert r.status_code == 404


def test_cannot_scan_someone_elses_upload(client, db):
    headers, _ = user_in_wilbur(client, db)
    from tests.core.factories import signup

    other, _ = signup(client, "Other")
    uid = upload(client, other, 9)
    r = client.post("/api/scans", headers=headers, json={"upload_ids": [uid]})
    assert r.status_code == 400
    assert client.post("/api/scans", headers=headers, json={"upload_ids": []}).status_code == 400


def test_publish_rejects_foreign_detection_and_bad_input(client, db):
    headers, _ = user_in_wilbur(client, db)
    a = _scan(client, headers, [4])
    b = _scan(client, headers, [5])
    det_b = b["detections"][0]
    bad = {
        "detection_id": det_b["id"],
        "name": "x",
        "category": "other",
        "transaction_type": "lend",
        "visibility": "campus",
    }
    assert (
        client.post(
            f"/api/scans/{a['id']}/publish", headers=headers, json={"items": [bad]}
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/api/scans/{a['id']}/publish", headers=headers, json={"items": []}
        ).status_code
        == 400
    )
    det_a = a["detections"][0]
    dup = {**bad, "detection_id": det_a["id"]}
    r = client.post(f"/api/scans/{a['id']}/publish", headers=headers, json={"items": [dup, dup]})
    assert r.status_code == 400
    # A failed publish changes nothing: the scan can still be published.
    ok = client.post(f"/api/scans/{a['id']}/publish", headers=headers, json={"items": [dup]})
    assert ok.status_code == 200, ok.text


def test_daily_limit(client, db, monkeypatch):
    headers, _ = user_in_wilbur(client, db)
    monkeypatch.setattr(settings, "ai_daily_scans_per_user", 1)
    _scan(client, headers, [6])
    uid = upload(client, headers, 7)
    r = client.post("/api/scans", headers=headers, json={"upload_ids": [uid]})
    assert r.status_code == 429


def test_budget_limit(client, db, monkeypatch):
    headers, _ = user_in_wilbur(client, db)
    _scan(client, headers, [8])
    db.execute(ScanImage.__table__.update().values(cost_usd=39.95))
    db.commit()
    monkeypatch.setattr(settings, "ai_provider", "harnessrouter")
    uid = upload(client, headers, 10)
    r = client.post("/api/scans", headers=headers, json={"upload_ids": [uid]})
    assert r.status_code == 429 and "paused" in r.json()["detail"]


def test_too_many_photos(client, db, monkeypatch):
    headers, _ = user_in_wilbur(client, db)
    monkeypatch.setattr(settings, "ai_max_images_per_scan", 1)
    ids = [upload(client, headers, s) for s in (11, 12)]
    assert client.post("/api/scans", headers=headers, json={"upload_ids": ids}).status_code == 400


def test_same_photo_uses_cache(client, db):
    headers, _ = user_in_wilbur(client, db)
    a = _scan(client, headers, [13])
    b = _scan(client, headers, [13])
    assert [d["name"] for d in a["detections"]] == [d["name"] for d in b["detections"]]
    raws = [img.raw_response for img in db.scalars(select(ScanImage).order_by(ScanImage.id))]
    assert "cache" in raws[-1]


def test_provider_failure_marks_image_failed(client, db, monkeypatch):
    from app.ai.providers import ProviderError
    from app.ai.providers.mock import MockVisionProvider

    async def boom(self, image, filename):
        raise ProviderError("secret detail", "We couldn't read this photo. Try again.")

    monkeypatch.setattr(MockVisionProvider, "detect", boom)
    headers, _ = user_in_wilbur(client, db)
    scan = _scan(client, headers, [14])
    assert scan["status"] == "failed"
    assert scan["images"][0]["status"] == "failed"
    assert "secret" not in scan["images"][0]["error"]
    r = client.post(f"/api/scans/{scan['id']}/publish", headers=headers, json={"items": []})
    assert r.status_code == 409


def test_stuck_scan_is_closed(client, db, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from app.ai import scans as scans_mod
    from app.models import Scan

    headers, _ = user_in_wilbur(client, db)
    monkeypatch.setattr(scans_mod, "process_scan", lambda scan_id: None)
    uid = upload(client, headers, 15)
    sid = client.post("/api/scans", headers=headers, json={"upload_ids": [uid]}).json()["id"]
    assert client.get(f"/api/scans/{sid}", headers=headers).json()["status"] == "processing"
    db.execute(Scan.__table__.update().values(created_at=datetime.now(UTC) - timedelta(minutes=11)))
    db.commit()
    body = client.get(f"/api/scans/{sid}", headers=headers).json()
    assert body["status"] == "failed" and body["images"][0]["status"] == "failed"
