"""End-to-end API smoke test (A4). Run with `make smoke` while `make api` is running.

Talks to a real server over HTTP (API_URL, default http://localhost:8000), like the web app does.
It creates two fresh @stanford.edu users on every run and never touches existing data.
Prints ✅/❌ per step and exits non-zero if anything failed. No AI calls are made.
"""

import io
import os
import sys
import uuid

import httpx
from PIL import Image

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
PICKUP_NOTE = "Blue door on the east side — text me first"

failures: list[str] = []


class StepFailed(Exception):
    pass


def check(condition: bool, what: str) -> None:
    if not condition:
        raise StepFailed(what)


def step(title: str):
    """Decorator: run the function now, print ✅/❌, remember failures, keep going."""

    def run(fn):
        try:
            fn()
            print(f"✅ {title}")
        except StepFailed as exc:
            failures.append(title)
            print(f"❌ {title}\n     {exc}")
        except Exception as exc:  # noqa: BLE001 — a crash in one step is a failed step
            failures.append(title)
            print(f"❌ {title}\n     {type(exc).__name__}: {exc}")
        return fn

    return run


class User:
    def __init__(self, client: httpx.Client, name: str, dorm_id: int):
        self.client = client
        self.email = f"smoke-{uuid.uuid4().hex[:10]}@stanford.edu"
        r = client.post(
            "/api/auth/signup",
            json={
                "email": self.email,
                "password": "smoke-test-pw",
                "name": name,
                "dorm_id": dorm_id,
            },
        )
        check(r.status_code == 201, f"signup → {r.status_code} {r.text[:200]}")
        body = r.json()
        self.id = body["user"]["id"]
        self.headers = {"Authorization": f"Bearer {body['token']}"}

    def call(self, method: str, path: str, expect: int | None = None, **kw) -> httpx.Response:
        r = self.client.request(method, path, headers=self.headers, **kw)
        if expect is not None:
            check(
                r.status_code == expect,
                f"{method} {path} → {r.status_code}, expected {expect}: {r.text[:200]}",
            )
        return r

    def get(self, path: str, expect: int | None = 200, **kw):
        return self.call("GET", path, expect, **kw)

    def post(self, path: str, expect: int | None = None, **kw):
        return self.call("POST", path, expect, **kw)

    def me(self) -> dict:
        return self.get("/api/me").json()


def jpeg_with_exif() -> bytes:
    """A phone-like photo: camera make, GPS position, and a rotation flag in its EXIF."""
    img = Image.new("RGB", (2000, 1000), (180, 90, 40))
    exif = Image.Exif()
    exif[0x010F] = "SmokeCam"
    exif[0x0112] = 6
    exif[0x8825] = {1: "N", 2: (37.0, 25.0, 30.0), 3: "W", 4: (122.0, 10.0, 12.0)}
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif)
    return out.getvalue()


def main() -> int:
    print(f"DAHA API smoke test → {API_URL}\n")
    client = httpx.Client(base_url=API_URL, timeout=20)
    state: dict = {}

    @step("0. Server is up and seeded (health, dorms)")
    def _():
        r = client.get("/api/health")
        check(r.status_code == 200 and r.json() == {"ok": True}, f"health → {r.status_code}")
        check(client.get("/api/me").status_code == 401, "/api/me without a token must be 401")

    if failures:
        print("\nIs the backend running?  make db migrate seed api")
        return 1

    @step("1. Sign up fresh @stanford.edu users in two different dorms")
    def _():
        bad = client.post(
            "/api/auth/signup",
            json={
                "email": f"smoke-{uuid.uuid4().hex[:8]}@gmail.com",
                "password": "smoke-test-pw",
                "name": "Nope",
            },
        )
        check(bad.status_code == 400, f"non-Stanford signup → {bad.status_code}, expected 400")

        # The dorm list needs a login, so one setup account signs up first to read it.
        first = client.post(
            "/api/auth/signup",
            json={
                "email": f"smoke-{uuid.uuid4().hex[:10]}@stanford.edu",
                "password": "smoke-test-pw",
                "name": "Smoke Setup",
            },
        )
        check(first.status_code == 201, f"signup → {first.status_code} {first.text[:200]}")
        setup_headers = {"Authorization": f"Bearer {first.json()['token']}"}
        dorms = client.get("/api/communities", params={"kind": "dorm"}, headers=setup_headers)
        check(dorms.status_code == 200, f"GET /api/communities → {dorms.status_code}")
        with_coords = [d for d in dorms.json() if d["lat"] is not None]
        check(len(with_coords) >= 2, "need at least two dorms — run `make seed`")
        dorm_a, dorm_b = with_coords[0], with_coords[1]

        state["u1"] = User(client, "Smoke Lender", dorm_a["id"])
        state["u2"] = User(client, "Smoke Borrower", dorm_b["id"])
        me1, me2 = state["u1"].me(), state["u2"].me()
        check(me1["dorm"]["id"] == dorm_a["id"], "user 1 is not in dorm A")
        check(me2["dorm"]["id"] == dorm_b["id"], "user 2 is not in dorm B")
        check(me1["points"] == 0 and me1["badges"] == [], "new users start at zero")
        login = client.post(
            "/api/auth/login", json={"email": state["u1"].email, "password": "smoke-test-pw"}
        )
        check(login.status_code == 200, f"login → {login.status_code}")

    if failures:
        return finish()
    u1, u2 = state["u1"], state["u2"]

    @step("2. Upload a photo with EXIF/GPS → stored as a clean JPEG")
    def _():
        original = jpeg_with_exif()
        check(b"SmokeCam" in original, "test photo should carry EXIF")
        r = u1.post(
            "/api/uploads", expect=201, files={"file": ("desk.jpg", original, "image/jpeg")}
        )
        upload = r.json()
        check(max(upload["width"], upload["height"]) <= 1600, "long side must be ≤ 1600 px")
        check((upload["width"], upload["height"]) == (800, 1600), "EXIF rotation was not applied")
        served = client.get(upload["url"])
        check(served.status_code == 200, f"GET {upload['url']} → {served.status_code}")
        img = Image.open(io.BytesIO(served.content))
        check(img.format == "JPEG", f"served as {img.format}, expected JPEG")
        check(len(img.getexif()) == 0, "EXIF tags survived the upload")
        check(not img.getexif().get_ifd(0x8825), "GPS data survived the upload")
        check(b"SmokeCam" not in served.content, "camera make survived the upload")
        state["upload"] = upload

    @step("3. Visibility: campus item is visible to user 2; dorm-only item is 404")
    def _():
        base = {"category": "sports", "transaction_type": "lend", "condition": "good"}
        campus = u1.post(
            "/api/items",
            expect=201,
            json={
                **base,
                "name": "Smoke test tent",
                "visibility": "campus",
                "pickup_note": PICKUP_NOTE,
                "image_upload_ids": [state["upload"]["id"]] if "upload" in state else [],
            },
        ).json()
        dorm = u1.post(
            "/api/items",
            expect=201,
            json={**base, "name": "Smoke test dorm-only lamp", "visibility": "dorm"},
        ).json()
        private = u1.post(
            "/api/items",
            expect=201,
            json={**base, "name": "Smoke test private pump", "visibility": "private"},
        ).json()
        state["item"] = campus

        seen = u2.get(f"/api/items/{campus['id']}").json()
        check(
            seen["can_borrow"] is True and seen["is_mine"] is False,
            "user 2 should be able to borrow",
        )
        check(seen["pickup_note"] is None, "pickup note leaked before any agreement")
        check(seen["distance_min"] is not None and seen["same_dorm"] is False, "distance missing")
        u2.get(f"/api/items/{dorm['id']}", expect=404)
        u2.get(f"/api/items/{private['id']}", expect=404)
        listed = [i["id"] for i in u2.get(f"/api/users/{u1.id}/items").json()["items"]]
        check(listed == [campus["id"]], f"profile shows {listed}, expected only the campus item")
        mine = [i["id"] for i in u1.get("/api/me/items").json()]
        check(set(mine) == {campus["id"], dorm["id"], private["id"]}, "owner should see all three")

    @step("4. Request → offer → accept → hand off → returned")
    def _():
        req = u2.post(
            "/api/requests",
            expect=201,
            json={
                "raw_text": "anyone have a tent I can borrow this weekend?",
                "title": "Tent",
                "item_name": "tent",
                "category": "sports",
                "transaction_type": "lend",
                "visibility": "campus",
            },
        ).json()
        state["request"] = req
        u1.get(f"/api/requests/{req['id']}")

        tx = u1.post(
            f"/api/requests/{req['id']}/offers",
            expect=201,
            json={"item_id": state["item"]["id"], "message": "I have a tent you can use!"},
        ).json()
        state["tx"] = tx
        check(tx["status"] == "offered" and tx["allowed_actions"] == ["cancel"], "bad offer state")

        view = u2.get(f"/api/transactions/{tx['id']}").json()
        check(view["allowed_actions"] == ["accept", "decline"], "requester should accept/decline")
        check(view["pickup_note"] is None, "pickup note leaked before accept")
        u1.post(f"/api/transactions/{tx['id']}/actions", expect=409, json={"action": "accept"})

        accepted = u2.post(
            f"/api/transactions/{tx['id']}/actions", expect=200, json={"action": "accept"}
        ).json()
        check(accepted["status"] == "accepted", "accept did not work")
        check(accepted["pickup_note"] == PICKUP_NOTE, "pickup note should be revealed on accept")
        check(
            u2.get(f"/api/requests/{req['id']}").json()["status"] == "in_progress",
            "request should be in_progress",
        )
        check(
            u2.get(f"/api/items/{tx['item']['id']}").json()["status"] == "reserved",
            "item should be reserved",
        )

        chat = f"/api/conversations/{tx['conversation_id']}/messages"
        u2.post(chat, expect=201, json={"body": "Thanks! Tresidder at 5?"})
        u1.post(chat, expect=201, json={"body": "See you there."})
        kinds = [m["kind"] for m in u1.get(chat).json()]
        check(kinds.count("text") == 3 and "system" in kinds, f"unexpected chat: {kinds}")

        handed = u1.post(
            f"/api/transactions/{tx['id']}/actions", expect=200, json={"action": "hand_off"}
        ).json()
        check(handed["status"] == "handed_off", "hand_off did not work")
        u2.post(
            f"/api/transactions/{tx['id']}/actions", expect=409, json={"action": "mark_returned"}
        )
        done = u1.post(
            f"/api/transactions/{tx['id']}/actions", expect=200, json={"action": "mark_returned"}
        ).json()
        check(done["status"] == "completed" and done["can_review"] is True, "not completed")
        check(
            [e["status"] for e in done["timeline"]]
            == ["offered", "accepted", "handed_off", "completed"],
            "timeline is wrong",
        )
        check(
            u1.get(f"/api/items/{tx['item']['id']}").json()["status"] == "available",
            "item should be available again",
        )
        check(
            u2.get(f"/api/requests/{req['id']}").json()["status"] == "fulfilled",
            "request should be fulfilled",
        )

    @step("5. Reviews, points, badges, notifications, unread counts")
    def _():
        check("tx" in state, "step 4 did not produce a transaction")
        tx = state["tx"]
        review = f"/api/transactions/{tx['id']}/review"
        u2.post(review, expect=201, json={"rating": 5, "body": "Smooth handoff"})
        u1.post(review, expect=201, json={"rating": 5})
        u1.post(review, expect=409, json={"rating": 4})

        me1, me2 = u1.me(), u2.me()
        # lender: 2 items shared ×2 + lend 10 + fulfilled a request 5 + good review 2
        check(me1["points"] == 21, f"lender has {me1['points']} points, expected 21")
        # borrower: returned a borrowed item 2 + good review 2
        check(me2["points"] == 4, f"borrower has {me2['points']} points, expected 4")
        check(me1["level"]["name"] == "Good Neighbor", f"lender level is {me1['level']['name']}")
        badges = {b["code"] for b in me1["badges"]}
        check(badges == {"first_share", "first_lend"}, f"lender badges are {badges}")
        check(me1["rating_avg"] == 5.0 and me1["completed_count"] == 1, "rating/completed wrong")

        types1 = [n["type"] for n in u1.get("/api/notifications").json()]
        types2 = [n["type"] for n in u2.get("/api/notifications").json()]
        for wanted in ("badge", "tx_update", "review"):
            check(wanted in types1, f"lender is missing a '{wanted}' notification: {types1}")
        for wanted in ("offer", "tx_update", "review"):
            check(wanted in types2, f"borrower is missing a '{wanted}' notification: {types2}")

        counts = u2.get("/api/notifications/unread-count").json()
        check(counts["notifications"] == len(types2), f"unread count is off: {counts}")
        check(counts["messages"] >= 1, "borrower should have unread chat messages")
        u2.post("/api/notifications/read", expect=204, json={"all": True})
        u2.post(f"/api/conversations/{tx['conversation_id']}/read", expect=204)
        counts = u2.get("/api/notifications/unread-count").json()
        check(counts == {"notifications": 0, "messages": 0}, f"still unread: {counts}")
        check(
            u2.post("/api/events", json={"events": [{"type": "page_view"}]}).status_code == 204,
            "events endpoint failed",
        )

    return finish()


def finish() -> int:
    print()
    if failures:
        print(f"❌ {len(failures)} step(s) failed: " + "; ".join(failures))
        return 1
    print("✅ All smoke steps passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
