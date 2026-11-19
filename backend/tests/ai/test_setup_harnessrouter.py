"""scripts/setup_harnessrouter.py: one harness per key, ids saved to backend/.env in key order."""

import importlib.util
import json
import sys

import httpx
import pytest
import respx

from app.core.config import BACKEND_DIR, settings

BASE = "https://hr.test"


@pytest.fixture
def setup_script(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "setup_harnessrouter", BACKEND_DIR / "scripts/setup_harnessrouter.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(settings, "harnessrouter_base_url", BASE)
    monkeypatch.setattr(settings, "harnessrouter_api_key", "sk-hr-a, sk-hr-b")
    return module


def test_write_env_replaces_only_the_harness_line(setup_script):
    setup_script.ENV_FILE.write_text(
        "AI_PROVIDER=mock\nHARNESSROUTER_VISION_HARNESS_ID=   # old comment\nEXTRA=1\n"
    )
    setup_script.write_env("hrn_1,hrn_2")
    assert setup_script.ENV_FILE.read_text() == (
        "AI_PROVIDER=mock\nHARNESSROUTER_VISION_HARNESS_ID=hrn_1,hrn_2\nEXTRA=1\n"
    )


def test_write_env_appends_when_missing(setup_script):
    setup_script.ENV_FILE.write_text("AI_PROVIDER=mock\n")
    setup_script.write_env("hrn_1")
    assert setup_script.ENV_FILE.read_text().splitlines()[-1] == (
        "HARNESSROUTER_VISION_HARNESS_ID=hrn_1"
    )


@respx.mock
def test_creates_one_harness_per_key_in_order(setup_script, monkeypatch, capsys):
    respx.get(f"{BASE}/v1/bases").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{BASE}/v1/models").mock(return_value=httpx.Response(200, json=[]))
    ids = {"Bearer sk-hr-a": "hrn_a", "Bearer sk-hr-b": "hrn_b"}
    create = respx.post(f"{BASE}/v1/harnesses").mock(
        side_effect=lambda req: httpx.Response(200, json={"id": ids[req.headers["authorization"]]})
    )
    monkeypatch.setattr(sys, "argv", ["setup_harnessrouter.py", "--write-env"])
    setup_script.main()
    assert setup_script.ENV_FILE.read_text() == "HARNESSROUTER_VISION_HARNESS_ID=hrn_a,hrn_b\n"
    assert json.loads(create.calls[0].request.content)["max_cost_usd"] == 0.5
    out = capsys.readouterr().out
    assert "key 2/2: vision harness hrn_b" in out and "sk-hr" not in out


@respx.mock
def test_harnesses_get_the_model_and_reasoning_effort(setup_script, monkeypatch):
    respx.get(f"{BASE}/v1/bases").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{BASE}/v1/models").mock(return_value=httpx.Response(200, json=[]))
    create = respx.post(f"{BASE}/v1/harnesses").mock(
        return_value=httpx.Response(200, json={"id": "hrn_x"})
    )
    monkeypatch.setattr(settings, "harnessrouter_model", "claude-opus-5.5")
    monkeypatch.setattr(settings, "harnessrouter_reasoning_effort", "low")
    monkeypatch.setattr(sys, "argv", ["setup_harnessrouter.py"])
    setup_script.main()
    body = json.loads(create.calls[0].request.content)
    assert body["default_model"] == "claude-opus-5.5"
    assert body["reasoning_effort"] == "low"
    assert body["memory_hint"] == setup_script.NO_MEMORY  # photos are never remembered

    monkeypatch.setattr(settings, "harnessrouter_reasoning_effort", "")  # unset → not sent
    setup_script.main()
    assert "reasoning_effort" not in json.loads(create.calls[-1].request.content)


@respx.mock
def test_check_reports_each_key_without_printing_it(setup_script, monkeypatch, capsys):
    monkeypatch.setattr(settings, "harnessrouter_api_key", "sk-hr-a,sk-hr-b,sk-hr-c")
    me = {"org": "org_1", "org_name": "Daha", "workspace": "org_1__hr_default"}

    def who(request):
        if request.headers["authorization"] == "Bearer sk-hr-c":
            return httpx.Response(401)
        return httpx.Response(200, json=me)

    respx.get(f"{BASE}/v1/me").mock(side_effect=who)
    monkeypatch.setattr(sys, "argv", ["setup_harnessrouter.py", "--check"])
    with pytest.raises(SystemExit) as exit_info:
        setup_script.main()
    assert exit_info.value.code == 1
    out = capsys.readouterr().out
    assert "key 1/3: OK · organization Daha" in out and "key 3/3: HTTP 401" in out
    assert "keys 1, 2 are in the same organization" in out
    assert "sk-hr" not in out


@respx.mock
def test_missing_adds_harnesses_only_for_new_keys(setup_script, monkeypatch, capsys):
    respx.get(f"{BASE}/v1/bases").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{BASE}/v1/models").mock(return_value=httpx.Response(200, json=[]))
    create = respx.post(f"{BASE}/v1/harnesses").mock(
        return_value=httpx.Response(200, json={"id": "hrn_c"})
    )
    monkeypatch.setattr(settings, "harnessrouter_api_key", "sk-hr-a,sk-hr-b,sk-hr-c")
    monkeypatch.setattr(settings, "harnessrouter_vision_harness_id", "hrn_a,hrn_b")
    monkeypatch.setattr(sys, "argv", ["setup_harnessrouter.py", "--missing", "--write-env"])
    setup_script.main()
    assert [c.request.headers["authorization"] for c in create.calls] == ["Bearer sk-hr-c"]
    saved = setup_script.ENV_FILE.read_text()
    assert saved == "HARNESSROUTER_VISION_HARNESS_ID=hrn_a,hrn_b,hrn_c\n"

    monkeypatch.setattr(settings, "harnessrouter_vision_harness_id", "hrn_a,hrn_b,hrn_c")
    setup_script.main()  # every key has one now: nothing to create
    assert len(create.calls) == 1
    assert "nothing to do" in capsys.readouterr().out


@respx.mock
def test_all_missing_adds_every_harness_on_a_new_key_only(setup_script, monkeypatch):
    respx.get(f"{BASE}/v1/bases").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{BASE}/v1/models").mock(return_value=httpx.Response(200, json=[]))
    create = respx.post(f"{BASE}/v1/harnesses").mock(
        side_effect=lambda req: httpx.Response(
            200, json={"id": "new_" + json.loads(req.content)["name"][:12]}
        )
    )
    monkeypatch.setattr(settings, "harnessrouter_api_key", "sk-hr-a,sk-hr-b,sk-hr-c")
    for var in ("vision", "condition", "profile", "handoff"):
        monkeypatch.setattr(settings, f"harnessrouter_{var}_harness_id", f"{var}1,{var}2")
    monkeypatch.setattr(settings, "harnessrouter_handoff_model", "claude-haiku-5.5")
    monkeypatch.setattr(
        sys, "argv", ["setup_harnessrouter.py", "--all", "--missing", "--write-env"]
    )
    setup_script.main()
    assert {c.request.headers["authorization"] for c in create.calls} == {"Bearer sk-hr-c"}
    assert len(create.calls) == 4  # photos, condition check, profiles, handoff
    saved = setup_script.ENV_FILE.read_text().splitlines()
    assert "HARNESSROUTER_VISION_HARNESS_ID=vision1,vision2,new_daha-vision-" in saved
    assert any(
        line.startswith("HARNESSROUTER_HANDOFF_HARNESS_ID=handoff1,handoff2,") for line in saved
    )


@respx.mock
def test_smoke_needs_yes_then_reports_each_key(setup_script, monkeypatch, capsys):
    monkeypatch.setattr(settings, "harnessrouter_vision_harness_id", "hrn_a,hrn_b")
    monkeypatch.setattr(sys, "argv", ["setup_harnessrouter.py", "--smoke"])
    with pytest.raises(SystemExit) as stop:
        setup_script.main()
    assert "Add --yes" in str(stop.value)

    good = '{"items":[{"name":"Desk lamp","category":"dorm","confidence":0.9}]}'
    frames = [{"type": "response.created", "response": {"id": "r1"}}]
    frames += [{"type": "response.output_text.delta", "delta": good}]
    frames += [{"type": "response.completed", "response": {"id": "r1", "status": "completed"}}]
    stream = "".join(f"data: {json.dumps(f)}\n\n" for f in frames)
    respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f"}))
    respx.post(f"{BASE}/hrn_a/v1/responses").mock(
        return_value=httpx.Response(200, headers={"content-type": "text/event-stream"}, text=stream)
    )
    respx.post(f"{BASE}/hrn_b/v1/responses").mock(return_value=httpx.Response(401))
    monkeypatch.setattr(sys, "argv", ["setup_harnessrouter.py", "--smoke", "--yes"])
    setup_script.main()
    out = capsys.readouterr().out
    assert "key 1/2: OK" in out and "key 2/2: FAILED" in out and "sk-hr" not in out
