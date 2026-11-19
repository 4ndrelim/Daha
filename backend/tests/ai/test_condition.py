"""app/ai/condition.py: the condition-check agent. HarnessRouter is faked; no paid calls."""

import json
import sys

import httpx
import pytest
import respx

from app.ai import condition
from app.ai.providers import ProviderError
from app.core.config import settings
from tests.ai.helpers import photo
from tests.ai.test_harnessrouter import sse
from tests.ai.test_setup_harnessrouter import setup_script  # noqa: F401 (fixture)

BASE = "https://hr.test"
HARNESS = "hrn_condition"


@pytest.fixture
def hr_on(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "harnessrouter")
    monkeypatch.setattr(settings, "harnessrouter_base_url", BASE)
    monkeypatch.setattr(settings, "harnessrouter_api_key", "sk-hr-test")
    monkeypatch.setattr(settings, "harnessrouter_condition_harness_id", HARNESS)


PHOTOS = ([photo(1), photo(2), photo(3)], [photo(1), photo(2), photo(4)])


# ---------------------------------------------------------------- validation
def test_clean_verdict_keeps_a_good_answer():
    v = condition.clean_verdict({"result": "possible_changes", "note": "New scuff near the base."})
    assert (v.result, v.note, v.sample) == ("possible_changes", "New scuff near the base.", False)


@pytest.mark.parametrize(
    "note",
    ["The lamp is damaged.", "Looks broken now", "This is the borrower's fault", "Who to blame"],
)
def test_blaming_words_are_replaced_with_a_neutral_note(note):
    v = condition.clean_verdict({"result": "possible_changes", "note": note})
    assert v.note == condition.NEUTRAL_NOTE["possible_changes"]


def test_links_newlines_and_length_are_cleaned():
    v = condition.clean_verdict({"result": "no changes", "note": "ok https://x.y\n" + "a" * 300})
    assert v.result == "no_changes"
    assert "http" not in v.note and "\n" not in v.note and len(v.note) <= condition.NOTE_MAX


@pytest.mark.parametrize("data", [{"result": "ruined"}, {"note": "x"}, ["no_changes"], None])
def test_unknown_or_missing_result_is_rejected(data):
    with pytest.raises(ValueError):
        condition.clean_verdict(data)


# ---------------------------------------------------------------- sample results
async def test_mock_provider_gives_a_labeled_sample():
    assert settings.ai_provider == "mock"
    v = await condition.compare(*PHOTOS)
    assert v.sample is True and v.result == "no_changes" and v.note.startswith("Sample result")


async def test_harnessrouter_without_the_harness_gives_a_labeled_sample(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "harnessrouter")
    monkeypatch.setattr(settings, "harnessrouter_api_key", "sk-hr-test")
    monkeypatch.setattr(settings, "harnessrouter_condition_harness_id", "")
    v = await condition.compare(*PHOTOS)
    assert v.sample is True and "isn't set up yet" in v.note


# ---------------------------------------------------------------- the agent
@respx.mock
async def test_agent_uploads_six_photos_and_parses_the_verdict(hr_on):
    files = iter(f"file_{n}" for n in range(1, 7))
    up = respx.post(f"{BASE}/v1/files").mock(
        side_effect=lambda req: httpx.Response(200, json={"id": next(files)})
    )
    reply = '{"result": "possible_changes", "note": "A new scratch on the back."}'
    run = respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(
        return_value=sse(reply, usage={"cost_usd": 0.02})
    )
    v = await condition.compare(*PHOTOS)
    assert (v.result, v.note, v.sample, v.cost_usd) == (
        "possible_changes",
        "A new scratch on the back.",
        False,
        0.02,
    )
    assert up.call_count == 6 and run.call_count == 1
    content = json.loads(run.calls[0].request.content)["input"][0]["content"]
    assert [c["file_id"] for c in content[:6]] == [f"file_{n}" for n in range(1, 7)]
    assert "BEFORE" in content[6]["text"]
    assert up.calls[0].request.headers["authorization"] == "Bearer sk-hr-test"


@respx.mock
async def test_agent_gets_one_repair_turn_then_gives_up(hr_on):
    respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f"}))
    run = respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(return_value=sse("no idea, sorry"))
    with pytest.raises(ProviderError) as err:
        await condition.compare(*PHOTOS)
    assert run.call_count == 2 and "sk-hr" not in str(err.value)


# ---------------------------------------------------------------- setup script
@respx.mock
def test_setup_script_creates_the_condition_harness(setup_script, monkeypatch, capsys):  # noqa: F811
    respx.get(f"{BASE}/v1/bases").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{BASE}/v1/models").mock(return_value=httpx.Response(200, json=[]))
    ids = {"Bearer sk-hr-a": "hrn_ca", "Bearer sk-hr-b": "hrn_cb"}
    create = respx.post(f"{BASE}/v1/harnesses").mock(
        side_effect=lambda req: httpx.Response(200, json={"id": ids[req.headers["authorization"]]})
    )
    monkeypatch.setattr(sys, "argv", ["setup_harnessrouter.py", "--condition", "--write-env"])
    setup_script.main()
    assert setup_script.ENV_FILE.read_text() == "HARNESSROUTER_CONDITION_HARNESS_ID=hrn_ca,hrn_cb\n"
    body = json.loads(create.calls[0].request.content)
    assert body["name"] == "daha-condition-v1" and body["max_cost_usd"] == 0.05
    assert body["system_prompt"] == condition.CONDITION_SYSTEM
    assert "sk-hr" not in capsys.readouterr().out
