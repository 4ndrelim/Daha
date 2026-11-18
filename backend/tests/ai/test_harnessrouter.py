import json

import httpx
import pytest
import respx

from app.ai.providers import ProviderError
from app.ai.providers import harnessrouter as hr
from app.core.config import settings

BASE = "https://hr.test"
HARNESS = "hrn_vision"


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    monkeypatch.setattr(settings, "harnessrouter_base_url", BASE)
    monkeypatch.setattr(settings, "harnessrouter_api_key", "sk-hr-test")
    monkeypatch.setattr(settings, "harnessrouter_vision_harness_id", HARNESS)
    monkeypatch.setattr(settings, "harnessrouter_est_cost_per_image", 0.07)
    monkeypatch.setattr(hr, "_semaphore", None)


def sse(text: str, rid="resp_1", terminal="response.completed", usage=None) -> httpx.Response:
    frames = [
        {"type": "response.created", "response": {"id": rid, "metadata": {"session_id": "s1"}}},
        {"type": "response.output_item.added"},
    ]
    frames += [
        {"type": "response.output_text.delta", "delta": text[i : i + 7]}
        for i in range(0, len(text), 7)
    ]
    frames.append(
        {
            "type": terminal,
            "response": {"id": rid, "status": terminal.split(".")[1], "usage": usage or {}},
        }
    )
    body = "".join(f"data: {json.dumps(f)}\n\n" for f in frames)
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)


GOOD = 'Sure!\n```json\n{"items":[{"name":"Desk lamp","category":"dorm","confidence":0.9}]}\n```'


@respx.mock
async def test_happy_path_streams_and_parses():
    up = respx.post(f"{BASE}/v1/files").mock(
        return_value=httpx.Response(200, json={"id": "file_1"})
    )
    run = respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(
        return_value=sse(GOOD, usage={"cost_usd": 0.031})
    )
    result = await hr.HarnessRouterVisionProvider().detect(b"jpeg", "photo_1.jpg")
    assert [i.name for i in result.items] == ["Desk lamp"]
    assert result.cost_usd == 0.031
    assert up.calls[0].request.headers["authorization"] == "Bearer sk-hr-test"
    sent = json.loads(run.calls[0].request.content)
    assert sent["stream"] is True
    assert sent["input"][0]["content"][0] == {"type": "input_file", "file_id": "file_1"}
    assert "photo_1.jpg" in sent["input"][0]["content"][1]["text"]
    assert run.calls[0].request.headers["idempotency-key"]


@respx.mock
async def test_invalid_json_gets_one_repair_turn():
    respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "file_1"}))
    run = respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(
        side_effect=[
            sse("I looked at the photo, it has a lamp."),
            sse('{"items":[{"name":"Lamp"}]}', rid="resp_2"),
        ]
    )
    result = await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")
    assert [i.name for i in result.items] == ["Lamp"]
    assert result.cost_usd == 0.07  # estimate when no cost is reported
    repair = json.loads(run.calls[1].request.content)
    assert repair["previous_response_id"] == "resp_1"


@respx.mock
async def test_still_invalid_after_repair_raises():
    respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f"}))
    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(side_effect=[sse("nope"), sse("still nope")])
    with pytest.raises(ProviderError):
        await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")


@respx.mock
async def test_retries_once_on_5xx():
    respx.post(f"{BASE}/v1/files").mock(
        side_effect=[httpx.Response(502), httpx.Response(200, json={"id": "f"})]
    )
    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(return_value=sse(GOOD))
    result = await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")
    assert len(result.items) == 1


@respx.mock
async def test_two_5xx_gives_up():
    respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(503))
    with pytest.raises(ProviderError):
        await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")


@respx.mock
async def test_failed_task_raises_without_leaking_key():
    respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f"}))
    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(
        return_value=sse("", terminal="response.failed")
    )
    with pytest.raises(ProviderError) as exc:
        await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")
    assert "sk-hr" not in str(exc.value) and "sk-hr" not in exc.value.user_message


@respx.mock
async def test_falls_back_to_metadata_form_on_404():
    respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f"}))
    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(return_value=httpx.Response(404))
    alt = respx.post(f"{BASE}/v1/responses").mock(return_value=sse(GOOD))
    result = await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")
    assert len(result.items) == 1
    assert json.loads(alt.calls[0].request.content)["metadata"] == {"harness_id": HARNESS}


async def test_missing_key_is_a_friendly_error(monkeypatch):
    monkeypatch.setattr(settings, "harnessrouter_api_key", "")
    with pytest.raises(ProviderError) as exc:
        await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")
    assert "manually" in exc.value.user_message
