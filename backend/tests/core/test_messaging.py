from tests.core.factories import community_id, seed_base, signup


def setup(client, db):
    seed_base(db)
    wilbur = community_id(db, "wilbur")
    a_h, a = signup(client, "Alice A", dorm_id=wilbur)
    b_h, b = signup(client, "Bob B", dorm_id=wilbur)
    c_h, c = signup(client, "Cara C", dorm_id=wilbur)
    return a_h, a, b_h, b, c_h, c


def counts(client, headers):
    return client.get("/api/notifications/unread-count", headers=headers).json()


def test_direct_conversation_and_unread_counts(client, db):
    a_h, a, b_h, b, c_h, _ = setup(client, db)
    r = client.post("/api/conversations", json={"user_id": b["id"]}, headers=a_h)
    assert r.status_code == 200, r.text
    conv = r.json()
    assert conv["other_user"]["name"] == "Bob B" and conv["transaction"] is None
    assert conv["last_message"] is None and conv["unread_count"] == 0
    # get-or-create: same thread from either side
    again = client.post("/api/conversations", json={"user_id": a["id"]}, headers=b_h).json()
    assert again["id"] == conv["id"] and again["other_user"]["name"] == "Alice A"
    assert (
        client.post("/api/conversations", json={"user_id": a["id"]}, headers=a_h).status_code == 400
    )
    assert client.post("/api/conversations", json={"user_id": 9999}, headers=a_h).status_code == 404

    url = f"/api/conversations/{conv['id']}/messages"
    first = client.post(url, json={"body": "hey, still have the kettle?"}, headers=a_h)
    assert first.status_code == 201 and first.json()["sender"]["name"] == "Alice A"
    client.post(url, json={"body": "need it tonight"}, headers=a_h)
    assert client.post(url, json={"body": "   "}, headers=a_h).status_code == 400
    assert client.post(url, json={"body": ""}, headers=a_h).status_code == 422

    assert counts(client, b_h) == {"notifications": 0, "messages": 2}
    assert counts(client, a_h) == {"notifications": 0, "messages": 0}
    assert client.get("/api/me", headers=b_h).json()["unread_messages"] == 2
    listed = client.get("/api/conversations", headers=b_h).json()
    assert listed[0]["unread_count"] == 2
    assert listed[0]["last_message"]["body"] == "need it tonight"

    msgs = client.get(url, headers=b_h).json()
    assert [m["body"] for m in msgs] == ["hey, still have the kettle?", "need it tonight"]
    # polling with after_id returns only what's new
    assert client.get(url, params={"after_id": msgs[-1]["id"]}, headers=b_h).json() == []
    client.post(url, json={"body": "yes!"}, headers=b_h)
    new = client.get(url, params={"after_id": msgs[-1]["id"]}, headers=a_h).json()
    assert [m["body"] for m in new] == ["yes!"]
    assert [m["body"] for m in client.get(url, params={"limit": 1}, headers=a_h).json()] == ["yes!"]

    # replying marks the thread read for the sender; /read does it explicitly
    assert counts(client, b_h)["messages"] == 0
    assert counts(client, a_h)["messages"] == 1
    assert client.post(f"/api/conversations/{conv['id']}/read", headers=a_h).status_code == 204
    assert counts(client, a_h)["messages"] == 0
    assert client.get("/api/conversations", headers=c_h).json() == []


def test_transaction_thread_and_ordering(client, db):
    a_h, a, b_h, b, _, _ = setup(client, db)
    direct = client.post("/api/conversations", json={"user_id": b["id"]}, headers=a_h).json()
    client.post(f"/api/conversations/{direct['id']}/messages", json={"body": "hi"}, headers=a_h)
    item = client.post(
        "/api/items",
        json={
            "name": "Kettle",
            "category": "dorm",
            "transaction_type": "lend",
            "visibility": "dorm",
        },
        headers=a_h,
    ).json()
    tx = client.post(
        f"/api/items/{item['id']}/borrow", json={"message": "Can I borrow it?"}, headers=b_h
    ).json()

    listed = client.get("/api/conversations", headers=a_h).json()
    assert [c["id"] for c in listed] == [tx["conversation_id"], direct["id"]]  # newest first
    thread = listed[0]
    assert thread["transaction"] == {
        "id": tx["id"],
        "status": "requested",
        "kind": "lend",
        "item_name": "Kettle",
    }
    assert thread["unread_count"] == 1 and thread["other_user"]["name"] == "Bob B"

    client.post(f"/api/transactions/{tx['id']}/actions", json={"action": "accept"}, headers=a_h)
    msgs = client.get(f"/api/conversations/{tx['conversation_id']}/messages", headers=b_h).json()
    assert [m["kind"] for m in msgs] == ["text", "system"]
    assert msgs[1]["sender"] is None and "accepted" in msgs[1]["body"]
    # Bob has two unread: Alice's direct "hi" and the system message. Alice acted in the
    # thread, so everything in it counts as read for her.
    assert counts(client, b_h)["messages"] == 2
    summary = client.get(f"/api/conversations/{tx['conversation_id']}", headers=a_h).json()
    assert summary["unread_count"] == 0
    assert summary["transaction"]["status"] == "accepted"


def test_notifications_list_and_mark_read(client, db):
    a_h, _, b_h, _, _, _ = setup(client, db)
    for name in ("Kettle", "Lamp", "Fan"):
        item = client.post(
            "/api/items",
            json={
                "name": name,
                "category": "dorm",
                "transaction_type": "lend",
                "visibility": "dorm",
            },
            headers=a_h,
        ).json()
        client.post(f"/api/items/{item['id']}/borrow", json={}, headers=b_h)
    notes = client.get("/api/notifications", headers=a_h).json()
    borrow_notes = [n for n in notes if n["type"] == "borrow_request"]
    assert len(borrow_notes) == 3 and [n["body"] for n in borrow_notes] == ["Fan", "Lamp", "Kettle"]
    total = len(notes)
    assert counts(client, a_h)["notifications"] == total

    r = client.post("/api/notifications/read", json={"ids": [borrow_notes[0]["id"]]}, headers=a_h)
    assert r.status_code == 204
    assert counts(client, a_h)["notifications"] == total - 1
    unread = client.get("/api/notifications", params={"unread_only": True}, headers=a_h).json()
    assert borrow_notes[0]["id"] not in [n["id"] for n in unread]
    # someone else can't mark mine
    client.post("/api/notifications/read", json={"all": True}, headers=b_h)
    assert counts(client, a_h)["notifications"] == total - 1
    assert client.post("/api/notifications/read", json={}, headers=a_h).status_code == 204
    assert counts(client, a_h)["notifications"] == total - 1
    client.post("/api/notifications/read", json={"all": True}, headers=a_h)
    assert counts(client, a_h)["notifications"] == 0
    assert len(client.get("/api/notifications", params={"limit": 2}, headers=a_h).json()) == 2
    assert client.get("/api/notifications").status_code == 401


def test_events_are_stored_and_never_fail(client, db):
    from sqlalchemy import select

    from app.models import Event

    a_h, a, *_ = setup(client, db)
    body = {
        "events": [
            {"type": "page_view", "payload": {"path": "/home"}},
            {"type": "search_performed", "payload": {"results": 3}, "ts": "2026-11-17T10:00:00Z"},
            {"type": "share_clicked"},
        ]
    }
    assert client.post("/api/events", json=body, headers=a_h).status_code == 204
    # logged-out and bad-token clients are accepted too
    assert client.post("/api/events", json=body).status_code == 204
    assert (
        client.post("/api/events", json=body, headers={"Authorization": "Bearer nope"}).status_code
        == 204
    )
    rows = db.execute(select(Event).order_by(Event.id)).scalars().all()
    assert len(rows) == 9
    assert [r.user_id for r in rows] == [a["id"]] * 3 + [None] * 6
    assert rows[0].type == "page_view" and rows[0].payload == {"path": "/home"}
    assert rows[1].payload["results"] == 3 and "client_ts" in rows[1].payload
    assert rows[2].payload == {}
