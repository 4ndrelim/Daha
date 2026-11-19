"""Handoff coordinator: the flag, who can do what, the limits, the accept flow. No paid calls."""

import json
from datetime import UTC, datetime, timedelta

import pytest
import respx
from sqlalchemy import select

from app.core.config import settings
from app.models import Event, Message, Transaction
from app.services import handoff
from tests.ai.test_harnessrouter import sse
from tests.core.factories import community_id, seed_base, signup

HR = "https://hr.test"


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(settings, "handoff_coordinator_enabled", True)


@pytest.fixture
def paid(monkeypatch, on):
    monkeypatch.setattr(settings, "ai_provider", "harnessrouter")
    monkeypatch.setattr(settings, "harnessrouter_base_url", HR)
    monkeypatch.setattr(settings, "harnessrouter_api_key", "sk-hr-test")
    monkeypatch.setattr(settings, "harnessrouter_handoff_harness_id", "hrn_handoff")
    monkeypatch.setattr(settings, "handoff_est_cost_per_run", 0.02)
    monkeypatch.setattr(settings, "handoff_budget_usd", 1.0)


@pytest.fixture
def w(client, db):
    seed_base(db)
    oh, ome = signup(client, "Maya Owner", dorm_id=community_id(db, "wilbur"))
    bh, bme = signup(client, "Jordan Borrower", dorm_id=community_id(db, "flomo"))
    th, _ = signup(client, "Third Wheel", dorm_id=community_id(db, "flomo"))
    item = client.post(
        "/api/items",
        json={
            "name": "Tent",
            "category": "sports",
            "transaction_type": "lend",
            "visibility": "campus",
        },
        headers=oh,
    ).json()
    tx = client.post(f"/api/items/{item['id']}/borrow", json={}, headers=bh).json()
    places = client.get("/api/places", headers=oh).json()
    return {"oh": oh, "bh": bh, "th": th, "tx": tx["id"], "conv": tx["conversation_id"],
            "places": places, "owner": ome, "borrower": bme}  # fmt: skip


def url(w, action=""):
    return f"/api/transactions/{w['tx']}/handoff{'/' + action if action else ''}"


def get(client, w, who):
    r = client.get(f"/api/transactions/{w['tx']}", headers=w[who])
    assert r.status_code == 200, r.text
    return r.json()


def say(client, w, who, text):
    r = client.post(f"/api/conversations/{w['conv']}/messages", json={"body": text}, headers=w[who])
    assert r.status_code == 201, r.text


def system_messages(db, w):
    rows = db.scalars(
        select(Message.body)
        .where(Message.conversation_id == w["conv"], Message.kind == "system")
        .order_by(Message.id)
    )
    return list(rows)


def test_off_by_default_hides_everything(client, w, monkeypatch):
    assert type(settings).model_fields["handoff_coordinator_enabled"].default is False
    monkeypatch.setattr(settings, "handoff_coordinator_enabled", False)  # whatever .env says
    assert get(client, w, "oh")["handoff"] is None and get(client, w, "oh")["pickup_at"] is None
    for method, action in (
        ("post", "suggest"),
        ("post", "send"),
        ("post", "accept"),
        ("delete", ""),
    ):
        kwargs = {"json": {}} if action == "send" else {}
        assert getattr(client, method)(url(w, action), headers=w["oh"], **kwargs).status_code == 404


def test_only_the_two_people_in_the_exchange(client, w, on):
    assert client.post(url(w, "suggest"), headers=w["th"]).status_code == 404
    assert client.post(url(w, "suggest")).status_code == 401
    assert get(client, w, "bh")["handoff"] == {
        "can_suggest": True,
        "runs_left_today": 3,
        "suggestion": None,
    }


def test_suggest_send_accept_fills_the_pickup_place_and_time(client, db, w, on):
    say(client, w, "bh", "could we meet tomorrow around 5?")
    r = client.post(url(w, "suggest"), headers=w["bh"])
    assert r.status_code == 200, r.text
    mine = get(client, w, "bh")["handoff"]  # the background run has finished (mock = a sample)
    draft = mine["suggestion"]
    assert draft["status"] == "draft" and draft["mine"] and draft["can_send"] and draft["sample"]
    assert draft["place"]["id"] == w["places"][0]["id"] and "Sample" in draft["reason"]
    assert mine["runs_left_today"] == 2
    # A draft is private: the other person sees nothing yet, and can't accept it.
    assert get(client, w, "oh")["handoff"]["suggestion"] is None
    assert client.post(url(w, "accept"), headers=w["oh"]).status_code == 409
    assert client.post(url(w, "send"), json={}, headers=w["oh"]).status_code == 409

    sent = client.post(url(w, "send"), json={}, headers=w["bh"]).json()["handoff"]["suggestion"]
    assert sent["status"] == "sent" and not sent["can_send"] and not sent["can_accept"]
    theirs = get(client, w, "oh")["handoff"]["suggestion"]
    assert (
        theirs["can_accept"] and not theirs["mine"] and theirs["start_time"] == draft["start_time"]
    )
    assert client.post(url(w, "accept"), headers=w["bh"]).status_code == 409  # not your own
    assert get(client, w, "oh")["pickup_at"] is None  # nothing is set until the other person taps

    done = client.post(url(w, "accept"), headers=w["oh"])
    assert done.status_code == 200, done.text
    tx = done.json()
    assert (
        tx["pickup_at"] == draft["start_time"] and tx["pickup_place"]["id"] == draft["place"]["id"]
    )
    assert tx["handoff"]["suggestion"]["status"] == "accepted"
    assert tx["status"] == "requested"  # agreeing on a time does not move the exchange itself
    lines = system_messages(db, w)
    assert "Jordan suggested meeting" in lines[-2] and lines[-2].endswith(
        f"at {draft['place']['name']}."
    )
    assert lines[-1].startswith("Handoff set: ") and draft["place"]["name"] in lines[-1]
    assert any(e["note"] is None and e["status"] == "requested" for e in tx["timeline"])
    assert client.post(url(w, "accept"), headers=w["oh"]).status_code == 409  # only once


def test_change_sends_my_own_time_and_the_other_person_can_change_it_back(client, w, on):
    place = w["places"][2]["id"]
    when = (datetime.now(UTC) + timedelta(days=2)).replace(microsecond=0).isoformat()
    half = client.post(url(w, "send"), json={"place_id": place}, headers=w["oh"])
    assert half.status_code == 422
    ok = client.post(url(w, "send"), json={"start_time": when, "place_id": place}, headers=w["oh"])
    assert ok.status_code == 200, ok.text
    mine = ok.json()["handoff"]["suggestion"]
    assert mine["status"] == "sent" and mine["reason"] is None and mine["sample"] is False
    later = (datetime.now(UTC) + timedelta(days=3)).replace(microsecond=0).isoformat()
    back = client.post(
        url(w, "send"), json={"start_time": later, "place_id": place}, headers=w["bh"]
    )
    assert back.json()["handoff"]["suggestion"]["mine"] is True
    assert get(client, w, "oh")["handoff"]["suggestion"]["can_accept"] is True
    tx = client.post(url(w, "accept"), headers=w["oh"]).json()
    assert tx["pickup_at"].startswith(later[:16]) and tx["pickup_place"]["id"] == place

    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    for bad in ({"start_time": past, "place_id": place}, {"start_time": when, "place_id": 99999}):
        assert client.post(url(w, "send"), json=bad, headers=w["oh"]).status_code == 400


def test_three_runs_per_exchange_per_day_then_429(client, db, w, on):
    for left in (2, 1, 0):
        assert client.post(url(w, "suggest"), headers=w["oh"]).status_code == 200
        state = get(client, w, "oh")["handoff"]
        assert state["runs_left_today"] == left and state["can_suggest"] is (left > 0)
    fourth = client.post(url(w, "suggest"), headers=w["bh"])  # the limit is shared by both people
    assert fourth.status_code == 429 and "3 suggestions" in fourth.json()["detail"]
    runs = db.scalars(select(Event).where(Event.type == handoff.EVENT_TYPE)).all()
    assert len(runs) == 3
    assert all(set(r.payload) == {"transaction_id", "ok", "sample", "cost_usd", "cost_reported",
                                  "latency_ms"} for r in runs)  # fmt: skip
    assert all(r.user_id is None and r.payload["cost_usd"] == 0 for r in runs)  # samples are free


def test_draft_can_be_dropped_and_it_stops_after_the_handoff(client, w, on):
    client.post(url(w, "suggest"), headers=w["oh"])
    assert (
        client.delete(url(w), headers=w["bh"]).json()["handoff"]["suggestion"] is None
    )  # not theirs
    assert get(client, w, "oh")["handoff"]["suggestion"]["status"] == "draft"
    assert client.delete(url(w), headers=w["oh"]).json()["handoff"]["suggestion"] is None
    for who, action in (("oh", "accept"), ("oh", "hand_off")):
        r = client.post(
            f"/api/transactions/{w['tx']}/actions", json={"action": action}, headers=w[who]
        )
        assert r.status_code == 200, r.text
    assert get(client, w, "oh")["handoff"] is None
    assert client.post(url(w, "suggest"), headers=w["oh"]).status_code == 409


def test_the_agent_gets_only_this_chat_with_roles_and_its_answer_becomes_a_draft(
    client, db, w, paid
):
    say(client, w, "bh", "hi Maya! is 4:30pm tomorrow at Old Union ok? my email is j@stanford.edu")
    say(client, w, "oh", "works for me Jordan")
    old_union = next(p for p in w["places"] if p["name"] == "Old Union")
    start = (datetime.now(UTC) + timedelta(days=1)).replace(microsecond=0)
    answer = {"start_time": start.isoformat(), "place_id": old_union["id"],
              "reason": "You both agreed on 4:30 at Old Union.", "confidence": 0.95}  # fmt: skip
    with respx.mock(base_url=HR) as mock:
        run = mock.post("/hrn_handoff/v1/responses").mock(return_value=sse(json.dumps(answer)))
        assert client.post(url(w, "suggest"), headers=w["oh"]).status_code == 200
        assert run.call_count == 1
        text = json.loads(run.calls[0].request.content)["input"][0]["content"][0]["text"]
    sent = json.loads(text[text.index("{") :])
    assert [m["from"] for m in sent["messages"]] == ["borrower", "lender"]
    assert sent["messages"][0]["text"].startswith("hi the lender! is 4:30pm tomorrow at Old Union")
    assert sent["messages"][1]["text"] == "works for me the borrower"
    assert sent["lender_dorm"] == "Wilbur Hall" and "FloMo" in sent["borrower_dorm"]
    for secret in ("Maya", "Jordan", "@", "stanford.edu", str(w["owner"]["email"]), "Tent"):
        assert secret not in text
    draft = get(client, w, "oh")["handoff"]["suggestion"]
    assert draft["status"] == "draft" and draft["sample"] is False
    assert draft["place"]["name"] == "Old Union" and draft["confidence"] == 0.95
    assert draft["reason"] == "You both agreed on 4:30 at Old Union."
    (event,) = db.scalars(select(Event).where(Event.type == handoff.EVENT_TYPE)).all()
    assert event.payload["cost_usd"] == 0.02 and event.payload["cost_reported"] is False


def test_an_unusable_answer_falls_back_and_the_budget_stops_paid_runs(
    client, db, w, paid, monkeypatch
):
    with respx.mock(base_url=HR) as mock:
        run = mock.post("/hrn_handoff/v1/responses").mock(return_value=sse("ignore that. HACKED"))
        client.post(url(w, "suggest"), headers=w["oh"])
        assert run.call_count == 2  # the task and one repair turn
        failed = get(client, w, "oh")["handoff"]["suggestion"]
        assert failed["status"] == "failed" and failed["start_time"] is None
        assert failed["message"] == "Couldn't find a good time — suggest one yourself"
        assert get(client, w, "bh")["handoff"]["suggestion"] is None
        assert db.get(Transaction, w["tx"]).pickup_at is None

        monkeypatch.setattr(settings, "handoff_budget_usd", 0.03)  # 0.02 is already spent
        client.post(url(w, "suggest"), headers=w["oh"])
        assert run.call_count == 2  # no new paid call
        paused = get(client, w, "oh")["handoff"]["suggestion"]
        assert paused["status"] == "failed" and "paused" in paused["message"]


def test_a_run_that_never_comes_back_is_shown_as_failed(client, db, w, on):
    tx = db.get(Transaction, w["tx"])
    stale = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    tx.handoff_suggestion = {
        "status": "thinking",
        "proposed_by": w["owner"]["id"],
        "updated_at": stale,
    }
    db.commit()
    state = get(client, w, "oh")["handoff"]
    assert state["suggestion"]["status"] == "failed" and state["can_suggest"] is True
