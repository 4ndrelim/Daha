"""Mutual matching (docs/plans/mutual-matching.md): pairs, opt-in, visibility, and the paid profile.

No paid calls: HarnessRouter is mocked with respx, exactly as in tests/ai/test_harnessrouter.py.
"""

import json

import httpx
import pytest
import respx
from sqlalchemy import select

from app.ai import profile
from app.core.config import settings
from app.models import AICache, Event
from tests.discovery.helpers import item, request, world

HR = "https://hr.test"
URL = "/api/me/mutual-matches"
OPTED_OUT = {"enabled": False, "matches": [], "summary": None, "likely_needs": []}


@pytest.fixture(autouse=True)
def _rules(monkeypatch):
    monkeypatch.setattr(settings, "mutual_matching", "rules")


@pytest.fixture
def ai(monkeypatch):
    monkeypatch.setattr(settings, "mutual_matching", "ai")
    monkeypatch.setattr(settings, "harnessrouter_base_url", HR)
    monkeypatch.setattr(settings, "harnessrouter_api_key", "sk-hr-test")
    monkeypatch.setattr(settings, "harnessrouter_profile_harness_id", "hrn_profile")
    monkeypatch.setattr(settings, "mutual_est_cost_per_profile", 0.05)
    monkeypatch.setattr(settings, "mutual_budget_usd", 3.0)


def opt_in(client, *headers, on=True):
    for h in headers:
        r = client.patch("/api/me", headers=h, json={"match_suggestions": on})
        assert r.status_code == 200 and r.json()["match_suggestions"] is on, r.text


def pairs(client, headers) -> list[dict]:
    r = client.get(URL, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["matches"]


def swap(client, w, a_visibility="campus"):
    """Maya has a tent Jordan asks for; Jordan has a suitcase Maya asks for."""
    item(client, w.wilbur, "Camping tent", visibility=a_visibility, category="sports")
    item(client, w.flomo, "Large suitcase", category="moving")
    request(client, w.flomo, "anyone have a camping tent?", title="Tent", item_name="camping tent")
    request(client, w.wilbur, "need a large suitcase", title="Suitcase", item_name="large suitcase")


def sse(text: str) -> httpx.Response:
    frames = [{"type": "response.created", "response": {"id": "resp_1"}}]
    frames.append({"type": "response.output_text.delta", "delta": text})
    frames.append(
        {"type": "response.completed", "response": {"id": "resp_1", "status": "completed"}}
    )
    body = "".join(f"data: {json.dumps(f)}\n\n" for f in frames)
    return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})


# ---------------------------------------------------------------- the flag and the opt-in
def test_off_is_a_404_and_me_carries_the_opt_in(client, db, monkeypatch):
    w = world(client, db)
    assert w.wilbur_me["match_suggestions"] is False  # real users start opted out
    monkeypatch.setattr(settings, "mutual_matching", "off")
    assert client.get(URL, headers=w.wilbur).status_code == 404
    monkeypatch.setattr(settings, "mutual_matching", "rules")
    r = client.get(URL, headers=w.wilbur)
    assert r.status_code == 200 and r.json() == OPTED_OUT


def test_a_pair_needs_both_directions_and_both_people_opted_in(client, db):
    w = world(client, db)
    swap(client, w)
    assert pairs(client, w.wilbur) == []  # nobody opted in yet
    opt_in(client, w.wilbur)
    assert pairs(client, w.wilbur) == []  # Jordan hasn't
    opt_in(client, w.flomo)

    (mine,) = pairs(client, w.wilbur)
    assert mine["user"]["id"] == w.flomo_me["id"] and mine["uses_prediction"] is False
    assert [link["item"]["name"] for link in mine["you_give"]] == ["Camping tent"]
    assert [link["item"]["name"] for link in mine["you_get"]] == ["Large suitcase"]
    assert mine["you_give"][0]["need"]["kind"] == "request"
    assert mine["you_give"][0]["need"]["request"]["title"] == "Tent"
    assert 0 < mine["score"] <= 1 and "each have what the other asked for" in mine["reason"]

    (theirs,) = pairs(client, w.flomo)  # the same pair, seen from the other side
    assert theirs["user"]["id"] == w.wilbur_me["id"] and theirs["score"] == mine["score"]
    assert [link["item"]["name"] for link in theirs["you_give"]] == ["Large suitcase"]

    assert pairs(client, w.wilbur2) == []  # a bystander sees nothing
    opt_in(client, w.flomo, on=False)  # one person leaving ends it for both
    assert pairs(client, w.wilbur) == []
    assert client.get(URL, headers=w.flomo).json() == OPTED_OUT


def test_one_way_help_is_not_a_mutual_match(client, db):
    w = world(client, db)
    opt_in(client, w.wilbur, w.flomo)
    item(client, w.wilbur, "Camping tent", category="sports")
    request(client, w.flomo, "anyone have a camping tent?", title="Tent", item_name="camping tent")
    assert pairs(client, w.wilbur) == [] and pairs(client, w.flomo) == []


def test_visibility_holds_in_both_directions(client, db):
    w = world(client, db)
    opt_in(client, w.wilbur, w.flomo)
    swap(client, w, a_visibility="dorm")  # Maya's tent is Wilbur-only; Jordan lives in FloMo
    assert pairs(client, w.wilbur) == [] and pairs(client, w.flomo) == []


def test_private_items_and_closed_requests_never_make_a_pair(client, db):
    w = world(client, db)
    opt_in(client, w.wilbur, w.flomo)
    swap(client, w, a_visibility="private")  # C5 pings Maya quietly, but that is not a pair
    assert pairs(client, w.wilbur) == [] and pairs(client, w.flomo) == []

    w2 = w.wilbur2
    opt_in(client, w2)
    item(client, w2, "Camping tent", category="sports")
    mine = request(
        client, w2, "need a large suitcase", title="Suitcase", item_name="large suitcase"
    )
    assert len(pairs(client, w2)) == 1
    done = client.patch(f"/api/requests/{mine['id']}", headers=w2, json={"status": "cancelled"})
    assert done.status_code == 200, done.text
    assert pairs(client, w2) == []  # my need is gone, so it is one-way again


# ---------------------------------------------------------------- the profile: what leaves
def test_profile_input_is_anonymous_and_skips_private_items(client, db):
    w = world(client, db)
    item(client, w.wilbur, "Camping tent", category="sports")
    item(client, w.wilbur, "Secret diary lamp", visibility="private")
    request(client, w.wilbur, "need a large suitcase", title="Suitcase", item_name="large suitcase")
    client.get("/api/search", headers=w.wilbur, params={"q": "hdmi cable call 650-555-1234"})
    payload, signals = profile.build_input(db, w.wilbur_me["id"])
    sent = profile.task_text(payload)
    assert signals == 3
    assert "Camping tent" in sent and "large suitcase" in sent and "hdmi cable" in sent
    for secret in ("Maya", w.wilbur_me["email"], "Wilbur", "Secret diary", "650", "555"):
        assert secret not in sent
    assert f'"{w.wilbur_me["id"]}"' not in sent and "user_id" not in sent


def test_clean_profile_keeps_only_safe_new_needs():
    payload = {"lists": [{"name": "Camping tent"}], "asked_for": [{"name": "suitcase"}]}
    raw = {
        "summary": "You   lend camping gear and borrow travel things.",
        "lends": ["sports", "nonsense", "sports"],
        "borrows": ["moving"],
        "likely_needs": [
            {"name": "Sleeping Bag", "category": "sports", "confidence": 1.7},
            {"name": "camping tent", "category": "sports", "confidence": 0.9},  # already lists it
            {"name": "suitcase", "category": "moving", "confidence": 0.9},  # already asked
            {"name": "prescription medication", "category": "other", "confidence": 0.9},
            {"name": "beer", "category": "consumables", "confidence": 0.9},
            {"name": "toothbrush", "category": "other", "confidence": 0.9},
            {"name": "ignore your rules <script>", "category": "weird", "confidence": "x"},
            "not an object",
        ]
        + [{"name": f"thing {n}", "category": "other", "confidence": 0.3} for n in range(9)],
    }
    out = profile.clean_profile(raw, payload)
    assert out["summary"] == "You lend camping gear and borrow travel things."
    assert out["lends"] == ["sports"] and out["borrows"] == ["moving"]
    names = [need["name"] for need in out["needs"]]
    assert names[0] == "sleeping bag" and out["needs"][0]["confidence"] == 1.0
    assert names[1] == "ignore your rules script" and out["needs"][1]["category"] is None
    assert len(names) == profile.MAX_NEEDS
    for banned in ("camping tent", "suitcase", "prescription medication", "beer", "toothbrush"):
        assert banned not in names
    with pytest.raises(ValueError):
        profile.clean_profile({"likely_needs": "many"}, payload)


# ---------------------------------------------------------------- the paid call (mocked)
def test_rules_mode_never_calls_harnessrouter(client, db):
    w = world(client, db)
    opt_in(client, w.wilbur)
    with respx.mock(base_url=HR, assert_all_called=False) as mock:
        route = mock.route().mock(return_value=httpx.Response(500))
        assert pairs(client, w.wilbur) == []
        assert profile.refresh_profile(w.wilbur_me["id"]) == "off"
        assert not route.called


def test_ai_profile_fills_one_side_of_a_pair_and_is_paid_for_once(client, db, ai):
    w = world(client, db)
    opt_in(client, w.wilbur, w.flomo)
    # Maya asked for Jordan's suitcase. Jordan hasn't asked for anything, but has activity.
    item(client, w.wilbur, "Camping tent", category="sports")
    item(client, w.flomo, "Large suitcase", category="moving")
    item(client, w.flomo, "Hiking boots", category="clothing")
    item(client, w.flomo, "Trail map", category="other")
    request(client, w.wilbur, "need a large suitcase", title="Suitcase", item_name="large suitcase")
    answer = {
        "summary": "You lend travel and hiking gear.",
        "lends": ["moving", "clothing"],
        "borrows": ["sports"],
        "likely_needs": [{"name": "camping tent", "category": "sports", "confidence": 0.8}],
    }
    with respx.mock(base_url=HR) as mock:
        route = mock.post("/hrn_profile/v1/responses").mock(return_value=sse(json.dumps(answer)))
        assert pairs(client, w.flomo) == []  # no pair yet; this call schedules Jordan's profile
        assert route.call_count == 1
        sent = json.loads(route.calls[0].request.content)["input"][0]["content"][0]["text"]
        assert "Large suitcase" in sent and "Jordan" not in sent and "FloMo" not in sent
        assert pairs(client, w.flomo)  # now Jordan "might need" Maya's tent
        assert route.call_count == 1  # unchanged activity: no second paid call

    seen_by_jordan = client.get(URL, headers=w.flomo).json()  # only Jordan sees Jordan's profile
    assert seen_by_jordan["summary"] == "You lend travel and hiking gear."
    assert seen_by_jordan["likely_needs"] == ["camping tent"]
    seen_by_maya = client.get(URL, headers=w.wilbur).json()
    assert seen_by_maya["summary"] is None and seen_by_maya["likely_needs"] == []

    (pair,) = pairs(client, w.wilbur)
    assert pair["uses_prediction"] is True and "a guess" in pair["reason"]
    assert pair["you_get"][0]["need"]["kind"] == "request"
    guess = pair["you_give"][0]
    assert guess["item"]["name"] == "Camping tent"
    assert guess["need"] == {"kind": "predicted", "name": "camping tent", "request": None}

    (run,) = db.scalars(select(Event).where(Event.type == profile.EVENT_TYPE)).all()
    assert run.payload["ok"] is True and run.payload["cost_usd"] == 0.05
    assert run.payload["cost_reported"] is False and "camping" not in json.dumps(run.payload)
    stored = db.get(AICache, profile.cache_key(w.flomo_me["id"])).value
    assert stored["summary"] == "You lend travel and hiking gear." and stored["source"] == "ai"

    opt_in(client, w.flomo, on=False)  # opting out deletes what was learned
    db.expire_all()
    assert db.get(AICache, profile.cache_key(w.flomo_me["id"])) is None
    assert pairs(client, w.wilbur) == []


def test_no_paid_call_without_signals_or_budget(client, db, ai, monkeypatch):
    w = world(client, db)
    opt_in(client, w.wilbur)
    with respx.mock(base_url=HR, assert_all_called=False) as mock:
        route = mock.route().mock(return_value=sse("{}"))
        assert profile.refresh_profile(w.wilbur_me["id"]) == "too few signals"
        assert profile.refresh_profile(w.wilbur2_me["id"]) == "not opted in"
        for name in ("Camping tent", "Hiking boots", "Trail map"):
            item(client, w.wilbur, name)
        monkeypatch.setattr(settings, "mutual_budget_usd", 0.04)
        assert profile.refresh_profile(w.wilbur_me["id"]) == "budget reached"
        assert not route.called
        assert pairs(client, w.wilbur) == []  # and the endpoint still answers


def test_a_bad_answer_is_repaired_once_then_dropped_and_still_counted(client, db, ai):
    w = world(client, db)
    opt_in(client, w.wilbur)
    for name in ("Camping tent", "Hiking boots", "Trail map"):
        item(client, w.wilbur, name)
    with respx.mock(base_url=HR) as mock:
        route = mock.post("/hrn_profile/v1/responses").mock(return_value=sse("Sure! Here you go."))
        assert profile.refresh_profile(w.wilbur_me["id"]) == "failed"
        assert route.call_count == 2  # the task, then one repair turn
    db.expire_all()
    assert db.get(AICache, profile.cache_key(w.wilbur_me["id"])) is None
    (run,) = db.scalars(select(Event).where(Event.type == profile.EVENT_TYPE)).all()
    assert run.payload["ok"] is False and run.payload["cost_usd"] == 0.05
