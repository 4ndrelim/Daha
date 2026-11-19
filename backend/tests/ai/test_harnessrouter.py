import asyncio
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
    monkeypatch.setattr(settings, "harnessrouter_max_concurrency", 2)
    monkeypatch.setattr(settings, "harnessrouter_race", False)  # whatever a laptop's .env says
    monkeypatch.setattr(settings, "harnessrouter_agent_slots", 0)
    monkeypatch.setattr(hr, "_pool", None)


def sse(
    text: str, rid="resp_1", terminal="response.completed", usage=None, **extra
) -> httpx.Response:
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
            "response": {
                "id": rid,
                "status": terminal.split(".")[1],
                "usage": usage or {},
                **extra,
            },
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


# ---------------------------------------------------------------- several keys (load balancing)
def use_keys(monkeypatch, keys: str, harness_ids: str = HARNESS) -> None:
    monkeypatch.setattr(settings, "harnessrouter_api_key", keys)
    monkeypatch.setattr(settings, "harnessrouter_vision_harness_id", harness_ids)
    monkeypatch.setattr(hr, "_pool", None)


def auth_header(request: httpx.Request) -> str:
    return request.headers["authorization"]


def auth(call) -> str:
    return auth_header(call.request)


def test_keys_are_comma_separated_trimmed_and_deduplicated(monkeypatch):
    use_keys(monkeypatch, " sk-hr-a , sk-hr-b,,sk-hr-a ", "h1, h2, h3")
    assert settings.harnessrouter_api_keys == ["sk-hr-a", "sk-hr-b", "sk-hr-a"]
    pool = hr.get_pool()
    assert [(s.number, s.api_key, s.harness_id) for s in pool.slots] == [
        (1, "sk-hr-a", "h1"),
        (2, "sk-hr-b", "h2"),
    ]
    assert "sk-hr" not in repr(pool.slots[0])  # keys never show up in reprs or logs


@respx.mock
async def test_photos_rotate_across_keys(monkeypatch):
    use_keys(monkeypatch, "sk-hr-a,sk-hr-b,sk-hr-c")
    up = respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f"}))
    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(side_effect=lambda req: sse(GOOD))
    provider = hr.HarnessRouterVisionProvider()
    results = [await provider.detect(b"jpeg", "p.jpg") for _ in range(4)]
    assert [auth(c) for c in up.calls] == [
        "Bearer sk-hr-a",
        "Bearer sk-hr-b",
        "Bearer sk-hr-c",
        "Bearer sk-hr-a",
    ]
    assert [r.raw["key"] for r in results] == [1, 2, 3, 1]


@respx.mock
async def test_a_photo_stays_on_one_key_and_its_own_harness(monkeypatch):
    use_keys(monkeypatch, "sk-hr-a,sk-hr-b", "hrn_a,hrn_b")
    up = respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f"}))
    run_a = respx.post(f"{BASE}/hrn_a/v1/responses").mock(
        side_effect=[sse("not json"), sse(GOOD, rid="resp_2")]
    )
    run_b = respx.post(f"{BASE}/hrn_b/v1/responses").mock(side_effect=lambda req: sse(GOOD))
    provider = hr.HarnessRouterVisionProvider()
    await provider.detect(b"jpeg", "p1.jpg")  # key a: upload, run, repair turn
    await provider.detect(b"jpeg", "p2.jpg")  # key b
    assert [auth(c) for c in up.calls] == ["Bearer sk-hr-a", "Bearer sk-hr-b"]
    assert [auth(c) for c in run_a.calls] == ["Bearer sk-hr-a", "Bearer sk-hr-a"]
    assert [auth(c) for c in run_b.calls] == ["Bearer sk-hr-b"]


@respx.mock
async def test_rate_limited_key_hands_the_photo_to_the_next_key(monkeypatch):
    use_keys(monkeypatch, "sk-hr-a,sk-hr-b")

    def files(request):
        if auth_header(request) == "Bearer sk-hr-a":
            return httpx.Response(429, headers={"retry-after": "120"})
        return httpx.Response(200, json={"id": "f"})

    up = respx.post(f"{BASE}/v1/files").mock(side_effect=files)
    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(side_effect=lambda req: sse(GOOD))
    provider = hr.HarnessRouterVisionProvider()
    first = await provider.detect(b"jpeg", "p.jpg")
    assert first.raw["key"] == 2
    # a was tried twice (one same-key retry), then rested; the next photo skips it
    assert [auth(c) for c in up.calls] == ["Bearer sk-hr-a", "Bearer sk-hr-a", "Bearer sk-hr-b"]
    second = await provider.detect(b"jpeg", "p.jpg")
    assert second.raw["key"] == 2
    assert hr.get_pool().slots[0].resting_until > hr.time.monotonic() + 100  # Retry-After: 120


@respx.mock
async def test_refused_and_out_of_credit_keys_are_skipped(monkeypatch):
    use_keys(monkeypatch, "sk-hr-revoked,sk-hr-broke,sk-hr-good")
    codes = {"Bearer sk-hr-revoked": 401, "Bearer sk-hr-broke": 402}

    def files(request):
        code = codes.get(auth_header(request))
        return httpx.Response(code) if code else httpx.Response(200, json={"id": "f"})

    up = respx.post(f"{BASE}/v1/files").mock(side_effect=files)
    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(side_effect=lambda req: sse(GOOD))
    result = await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")
    assert result.raw["key"] == 3
    assert len(up.calls) == 3  # no same-key retries for 401/402


@respx.mock
async def test_every_key_failing_gives_a_friendly_error_without_keys(monkeypatch):
    use_keys(monkeypatch, "sk-hr-a,sk-hr-b")
    respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(401, text="bad key sk-hr-a"))
    with pytest.raises(ProviderError) as exc:
        await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")
    assert "manually" in exc.value.user_message
    assert "sk-hr" not in str(exc.value) and "sk-hr" not in exc.value.user_message


async def test_harness_ids_must_be_one_or_one_per_key(monkeypatch):
    use_keys(monkeypatch, "sk-hr-a,sk-hr-b,sk-hr-c", "hrn_1,hrn_2")
    with pytest.raises(ProviderError) as exc:
        await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")
    assert "2 ids for 3 keys" in str(exc.value)
    assert "manually" in exc.value.user_message


@pytest.mark.parametrize("cap", [2, 4])  # 2 = one org's free-trial limit; 4 = two keys in two orgs
@respx.mock
async def test_concurrency_is_a_total_cap_spread_across_keys(monkeypatch, cap):
    use_keys(monkeypatch, "sk-hr-a,sk-hr-b")
    monkeypatch.setattr(settings, "harnessrouter_max_concurrency", cap)
    running: dict[str, int] = {}
    peak = {"total": 0}

    async def files(request):
        key = auth_header(request)
        running[key] = running.get(key, 0) + 1
        peak["total"] = max(peak["total"], sum(running.values()))
        peak[key] = max(peak.get(key, 0), running[key])
        await asyncio.sleep(0.05)
        running[key] -= 1
        return httpx.Response(200, json={"id": "f"})

    respx.post(f"{BASE}/v1/files").mock(side_effect=files)
    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(side_effect=lambda req: sse(GOOD))
    provider = hr.HarnessRouterVisionProvider()
    photos = 3 * cap
    results = await asyncio.gather(*(provider.detect(b"jpeg", f"p{i}.jpg") for i in range(photos)))
    keys = [r.raw["key"] for r in results]
    assert keys.count(1) == keys.count(2) == photos // 2  # spread evenly
    half = cap // 2  # never over the cap, and never more than half of it on one key
    assert peak == {"total": cap, "Bearer sk-hr-a": half, "Bearer sk-hr-b": half}


@respx.mock
async def test_retry_reuses_the_idempotency_key():
    respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f"}))
    run = respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(
        side_effect=[httpx.Response(503), sse(GOOD)]
    )
    await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")
    first, retry = (c.request.headers["idempotency-key"] for c in run.calls)
    assert first == retry  # the server replays a task it already ran instead of billing twice


@respx.mock
async def test_http_500_is_not_retried():
    up = respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(500))
    with pytest.raises(ProviderError):
        await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")
    assert len(up.calls) == 1  # docs: retry only network errors, 429, 502, 503, 504


@respx.mock
async def test_balance_exhausted_mid_task_moves_to_the_next_key(monkeypatch):
    use_keys(monkeypatch, "sk-hr-a,sk-hr-b")
    respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f"}))

    def run(request):
        if auth_header(request) == "Bearer sk-hr-a":
            return sse(
                "",
                terminal="response.incomplete",
                incomplete_details={"reason": "balance_exhausted"},
            )
        return sse(GOOD)

    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(side_effect=run)
    result = await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")
    assert result.raw["key"] == 2


# ---------------------------------------------------------------- racing (HARNESSROUTER_RACE)
def race_on(monkeypatch, cap: int = 4) -> None:
    use_keys(monkeypatch, "sk-hr-a,sk-hr-b")
    monkeypatch.setattr(settings, "harnessrouter_race", True)
    monkeypatch.setattr(settings, "harnessrouter_max_concurrency", cap)


def idle(pool: hr.KeyPool) -> bool:
    return all(s.in_flight == 0 for s in pool.slots) and not pool.backups and not pool.preempted


@respx.mock
async def test_race_takes_the_first_good_answer_and_cancels_the_other(monkeypatch):
    race_on(monkeypatch)
    finished: list[str] = []

    async def run(request):
        key = auth_header(request)
        await asyncio.sleep(0.5 if key == "Bearer sk-hr-a" else 0.05)  # key a has a slow spell
        finished.append(key)
        return sse(GOOD)

    up = respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f"}))
    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(side_effect=run)
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    result = await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")
    assert loop.time() - t0 < 0.4  # didn't wait for the slow key
    assert result.raw["key"] == 2 and result.raw["race"] == "backup won"
    assert sorted(auth(c) for c in up.calls) == ["Bearer sk-hr-a", "Bearer sk-hr-b"]
    assert finished == ["Bearer sk-hr-b"]  # the slow copy was cancelled, not waited for
    assert result.cost_usd == pytest.approx(0.14)  # two tasks' worth (0.07 each)
    assert [i.name for i in result.items] == ["Desk lamp"]
    assert idle(hr.get_pool())


@respx.mock
async def test_race_only_uses_spare_slots(monkeypatch):
    race_on(monkeypatch, cap=2)  # two photos fill both slots: no room for second copies

    async def run(request):
        await asyncio.sleep(0.05)
        return sse(GOOD)

    up = respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f"}))
    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(side_effect=run)
    provider = hr.HarnessRouterVisionProvider()
    results = await asyncio.gather(*(provider.detect(b"jpeg", f"p{i}.jpg") for i in range(2)))
    assert len(up.calls) == 2
    assert sorted(r.raw["key"] for r in results) == [1, 2]
    assert all("race" not in r.raw and r.cost_usd == pytest.approx(0.07) for r in results)
    assert idle(hr.get_pool())


@respx.mock
async def test_race_survives_one_copy_failing(monkeypatch):
    race_on(monkeypatch)

    async def run(request):
        if auth_header(request) == "Bearer sk-hr-a":
            await asyncio.sleep(0.01)
            return sse("", terminal="response.failed", error={"message": "boom"})
        await asyncio.sleep(0.1)  # the good copy is slower but still wins
        return sse(GOOD)

    respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f"}))
    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(side_effect=run)
    result = await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")
    assert result.raw["key"] == 2 and result.raw["race"] == "backup won"
    assert idle(hr.get_pool())


@respx.mock
async def test_race_both_copies_failing_gives_the_usual_error(monkeypatch):
    race_on(monkeypatch)

    async def run(request):
        await asyncio.sleep(0.01)
        return sse("", terminal="response.failed", error={"message": "boom"})

    respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f"}))
    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(side_effect=run)
    with pytest.raises(ProviderError) as exc:
        await hr.HarnessRouterVisionProvider().detect(b"jpeg", "p.jpg")
    assert "task failed" in str(exc.value)
    assert idle(hr.get_pool())


@respx.mock
async def test_a_new_photo_takes_a_backups_slot_instead_of_waiting(monkeypatch):
    race_on(monkeypatch, cap=2)  # photo 1 races on both slots, then photo 2 arrives

    async def run(request):
        await asyncio.sleep(0.3)
        return sse(GOOD)

    up = respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f"}))
    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(side_effect=run)
    provider = hr.HarnessRouterVisionProvider()
    loop = asyncio.get_running_loop()

    async def second():
        await asyncio.sleep(0.05)
        t0 = loop.time()
        result = await provider.detect(b"jpeg", "p2.jpg")
        return result, loop.time() - t0

    first, (other, took) = await asyncio.gather(provider.detect(b"jpeg", "p1.jpg"), second())
    assert took < 0.45  # ran straight away on the backup's slot, not after photo 1 finished
    assert first.raw["key"] == 1 and first.raw["race"] == "backup gave its slot to another photo"
    assert other.raw["key"] == 2 and "race" not in other.raw
    assert len(up.calls) == 3  # photo 1 twice (one copy cancelled), photo 2 once
    assert idle(hr.get_pool())


# ------------------------------------------- a slot on key 1 kept free for the other agents
def busy_tracker():
    running: dict[str, int] = {}
    peak: dict[str, int] = {"total": 0}

    async def files(request):
        key = auth_header(request)
        running[key] = running.get(key, 0) + 1
        peak["total"] = max(peak["total"], sum(running.values()))
        peak[key] = max(peak.get(key, 0), running[key])
        await asyncio.sleep(0.05)
        running[key] -= 1
        return httpx.Response(200, json={"id": "f"})

    return files, peak


@respx.mock
async def test_photos_leave_a_slot_on_key_1_for_the_other_agents(monkeypatch):
    use_keys(monkeypatch, "sk-hr-a,sk-hr-b")
    monkeypatch.setattr(settings, "harnessrouter_max_concurrency", 4)  # 2 per key (2 orgs)
    monkeypatch.setattr(settings, "harnessrouter_agent_slots", 1)
    files, peak = busy_tracker()
    respx.post(f"{BASE}/v1/files").mock(side_effect=files)
    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(side_effect=lambda req: sse(GOOD))
    provider = hr.HarnessRouterVisionProvider()
    results = await asyncio.gather(*(provider.detect(b"jpeg", f"p{i}.jpg") for i in range(9)))
    assert len(results) == 9
    # never more than 1 photo on key 1, so the coordinator / condition check always fit there
    assert peak == {"total": 3, "Bearer sk-hr-a": 1, "Bearer sk-hr-b": 2}


@respx.mock
async def test_a_racing_backup_never_takes_the_reserved_slot(monkeypatch):
    race_on(monkeypatch)  # 2 keys, 4 at once
    monkeypatch.setattr(settings, "harnessrouter_agent_slots", 1)
    files, peak = busy_tracker()
    respx.post(f"{BASE}/v1/files").mock(side_effect=files)

    async def run(request):
        await asyncio.sleep(0.05)
        return sse(GOOD)

    respx.post(f"{BASE}/{HARNESS}/v1/responses").mock(side_effect=run)
    provider = hr.HarnessRouterVisionProvider()
    alone = await provider.detect(b"jpeg", "p.jpg")
    assert alone.raw["race"] in ("first won", "backup won")  # one photo still races
    results = await asyncio.gather(*(provider.detect(b"jpeg", f"p{i}.jpg") for i in range(4)))
    assert len(results) == 4
    assert peak["Bearer sk-hr-a"] == 1 and peak["Bearer sk-hr-b"] <= 2 and peak["total"] <= 3
    assert idle(hr.get_pool())
