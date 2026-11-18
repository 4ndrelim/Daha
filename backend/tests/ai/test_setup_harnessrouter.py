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
    assert "key 2/2: harness hrn_b" in out and "sk-hr" not in out


@respx.mock
def test_check_reports_each_key_without_printing_it(setup_script, monkeypatch, capsys):
    respx.get(f"{BASE}/v1/models").mock(
        side_effect=lambda req: httpx.Response(
            200 if req.headers["authorization"] == "Bearer sk-hr-a" else 401
        )
    )
    monkeypatch.setattr(sys, "argv", ["setup_harnessrouter.py", "--check"])
    with pytest.raises(SystemExit) as exit_info:
        setup_script.main()
    assert exit_info.value.code == 1
    out = capsys.readouterr().out
    assert "key 1/2: OK" in out and "key 2/2: HTTP 401" in out and "sk-hr" not in out
