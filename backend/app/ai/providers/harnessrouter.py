"""HarnessRouter vision: upload → run a harness task (SSE stream) → JSON (PLAN.md C0/C1.2).

HarnessRouter runs full agent harnesses, so a "task" can take tens of seconds. Guard rails:
- several API keys (HARNESSROUTER_API_KEY, comma-separated) are load-balanced: each photo goes to
  the least-busy key and stays on it for upload → run → repair, because a file id only works with
  the key that uploaded it (docs: "Any other key that names it gets 404");
- at most HARNESSROUTER_MAX_CONCURRENCY tasks at once in total (the free trial allows 2 per
  organization; keys in one organization share that limit and its credit);
- a key that is refused (401/403), out of credit (402, or a task that ends "balance_exhausted"),
  or still rate-limited after a retry (429) rests for a while, and the photo moves to the next key;
- an overall timeout per photo (HARNESSROUTER_TIMEOUT_S);
- one retry on network errors, 429, 502, 503 and 504 (the documented retry policy), reusing the
  same Idempotency-Key so the server replays rather than reruns; one "repair" turn if the reply
  isn't valid JSON.
Keys are only ever sent in the Authorization header and never logged (logs say "key 2/3").
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.ai.normalize import payload_from_text
from app.ai.prompts import REPAIR_TURN, vision_task
from app.ai.providers.base import ProviderError
from app.ai.schemas import ProviderResult
from app.core.config import settings

log = logging.getLogger(__name__)
TERMINAL = {"response.completed", "response.incomplete", "response.failed"}

# How long a key rests after it fails in a way another key might not.
REST_RATE_LIMITED_S = 30.0  # unless the API sends Retry-After
REST_NO_CREDIT_S = 600.0
REST_REFUSED_S = 900.0
NOT_SET_UP = "AI scanning isn't set up yet — list items manually"
SET_UP_WRONG = "AI scanning isn't set up correctly — list items manually"
NO_CREDIT = "AI scanning is paused — list items manually"


class _Retryable(Exception):
    pass


class _RateLimited(_Retryable):
    def __init__(self, retry_after: float | None):
        super().__init__("HTTP 429")
        self.retry_after = retry_after


class _NoRoom(Exception):
    """A racing backup copy found no free task slot, so it doesn't run (it never waits)."""


class _KeyUnavailable(Exception):
    """This key can't serve the photo right now; another key might."""

    def __init__(self, reason: str, rest_s: float, user_message: str):
        super().__init__(reason)
        self.rest_s = rest_s
        self.user_message = user_message


# ---------------------------------------------------------------- key pool
@dataclass(eq=False)
class KeySlot:
    number: int  # 1-based; the only thing about a key that is ever logged
    api_key: str = field(repr=False)
    harness_id: str
    in_flight: int = 0  # photos running on this key now
    resting_until: float = 0.0  # time.monotonic()
    last_used: int = 0  # round-robin tie-break


class KeyPool:
    def __init__(self, pairs: list[tuple[str, str]], concurrency: int):
        self.slots = [KeySlot(i + 1, key, harness) for i, (key, harness) in enumerate(pairs)]
        self.semaphore = asyncio.Semaphore(concurrency)  # tasks at once, all keys together
        self._ticks = 0
        # Racing (HARNESSROUTER_RACE): the second copies of photos, newest last. They only use
        # spare task slots and give one back as soon as a new photo needs it.
        self.backups: dict[asyncio.Task, None] = {}
        self.preempted: set[asyncio.Task] = set()

    def __len__(self) -> int:
        return len(self.slots)

    def awake_other(self, number: int) -> bool:
        """Is some key other than `number` free to take a backup copy right now?"""
        now = time.monotonic()
        return any(s.number != number and s.resting_until <= now for s in self.slots)

    def preempt_backup(self) -> bool:
        """Cancel the newest backup copy so a waiting photo gets its task slot."""
        for task in reversed(list(self.backups)):
            if not task.done():
                self.preempted.add(task)
                task.cancel()
                return True
        return False

    def pick(self, exclude: set[int]) -> KeySlot | None:
        """The least-busy key that isn't resting (least recently used on a tie).

        If every remaining key is resting, the one that wakes up first; None when all are excluded.
        """
        left = [s for s in self.slots if s.number not in exclude]
        if not left:
            return None
        now = time.monotonic()
        awake = [s for s in left if s.resting_until <= now]
        if awake:
            return min(awake, key=lambda s: (s.in_flight, s.last_used))
        return min(left, key=lambda s: s.resting_until)

    @contextmanager
    def running(self, slot: KeySlot) -> Iterator[KeySlot]:
        self._ticks += 1
        slot.last_used = self._ticks
        slot.in_flight += 1
        try:
            yield slot
        finally:
            slot.in_flight -= 1

    def rest(self, slot: KeySlot, seconds: float) -> None:
        slot.resting_until = max(slot.resting_until, time.monotonic() + seconds)


def key_pairs(keys: list[str], harness_ids: list[str]) -> list[tuple[str, str]]:
    """(key, harness id) per key: one shared harness id, or one per key in the same order."""
    if not keys or not harness_ids:
        raise ProviderError(
            "HARNESSROUTER_API_KEY / HARNESSROUTER_VISION_HARNESS_ID not set", NOT_SET_UP
        )
    if len(harness_ids) == 1:
        harness_ids = harness_ids * len(keys)
    elif len(harness_ids) != len(keys):
        raise ProviderError(
            f"HARNESSROUTER_VISION_HARNESS_ID has {len(harness_ids)} ids for {len(keys)} keys: "
            "use one shared id, or one per key in the same order "
            "(scripts/setup_harnessrouter.py --write-env)",
            SET_UP_WRONG,
        )
    pairs: dict[str, str] = {}
    for key, harness in zip(keys, harness_ids, strict=True):
        pairs.setdefault(key, harness)  # a key listed twice still counts once
    return list(pairs.items())


_pool: KeyPool | None = None
_pool_config = ""


def get_pool() -> KeyPool:
    """The process-wide pool, rebuilt only when the key/harness settings change."""
    global _pool, _pool_config
    keys, ids = settings.harnessrouter_api_keys, settings.harnessrouter_vision_harness_ids
    concurrency = max(1, settings.harnessrouter_max_concurrency)
    config = hashlib.sha256(f"{keys}|{ids}|{concurrency}".encode()).hexdigest()
    if _pool is None or config != _pool_config:
        _pool = KeyPool(key_pairs(keys, ids), concurrency)
        _pool_config = config
    return _pool


def _idempotency_keys() -> tuple[str, str]:
    return str(uuid.uuid4()), str(uuid.uuid4())


def _retry_after(resp: httpx.Response) -> float | None:
    value = resp.headers.get("retry-after")
    try:
        return min(max(float(value), 1.0), REST_NO_CREDIT_S) if value else None
    except ValueError:  # the HTTP-date form; use the default rest
        return None


# ---------------------------------------------------------------- response parsing
def _cost_from(response: dict[str, Any]) -> float | None:
    """Look for a reported cost in the final response object (shape not guaranteed)."""
    for container in (response, response.get("usage") or {}, response.get("metadata") or {}):
        if not isinstance(container, dict):
            continue
        for key in ("cost_usd", "total_cost_usd", "cost"):
            value = container.get(key)
            if isinstance(value, int | float) and value >= 0:
                return float(value)
    return None


def _final_text(response: dict[str, Any]) -> str:
    """Text from a Responses-style object: output[].content[].text where type is output_text."""
    parts: list[str] = []
    for out in response.get("output") or []:
        if not isinstance(out, dict):
            continue
        for block in out.get("content") or []:
            if isinstance(block, dict) and block.get("type") in ("output_text", "text"):
                parts.append(str(block.get("text") or ""))
    return "".join(parts) or str(response.get("output_text") or "")


# ---------------------------------------------------------------- provider
async def _first_good(
    primary: asyncio.Task, backup: asyncio.Task
) -> tuple[ProviderResult, asyncio.Task]:
    """The first copy that succeeds. A failed copy doesn't end the race while the other runs;
    a cancelled (preempted) backup is ignored. Both failing raises the first copy's error."""
    pending = {primary, backup}
    errors: dict[asyncio.Task, BaseException] = {}
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task.cancelled() or isinstance(task.exception(), _NoRoom):
                continue  # a backup that gave its slot away, or never found one
            exc = task.exception()
            if exc is None:
                return task.result(), task
            errors[task] = exc
    raise (
        errors.get(primary)
        or errors.get(backup)
        or ProviderError("harnessrouter: both copies of the photo were cancelled", NOT_SET_UP)
    )


class HarnessRouterVisionProvider:
    name = "harnessrouter"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self.model = settings.harnessrouter_model or settings.harnessrouter_base
        self._transport = transport

    def _client(self, slot: KeySlot) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=settings.harnessrouter_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {slot.api_key}"},
            timeout=httpx.Timeout(30.0, read=float(settings.harnessrouter_timeout_s)),
            transport=self._transport,
        )

    async def detect(self, image_jpeg: bytes, filename: str) -> ProviderResult:
        pool = get_pool()
        start = time.monotonic()
        if settings.harnessrouter_race and len(pool) > 1:
            return await self._race(pool, image_jpeg, filename, start)
        return await self._on_a_key(pool, image_jpeg, filename, start)

    async def _race(
        self, pool: KeyPool, image_jpeg: bytes, filename: str, start: float
    ) -> ProviderResult:
        """The photo on two keys at once when there's room; the first good answer wins.

        HarnessRouter's speed varies a lot between tasks (the same photo took 12 s or 28 s), and
        a slow spell usually hits one account at a time. The second copy is a backup: it starts
        only when a task slot is free, and it is cancelled the moment another photo needs that
        slot, so racing never delays anyone. A finished race costs about two tasks.
        """
        chosen: list[int] = []
        primary = asyncio.create_task(
            self._on_a_key(pool, image_jpeg, filename, start, chosen=chosen)
        )
        await asyncio.sleep(0)  # the primary takes its slot and key (so do sibling photos)
        if (
            primary.done()
            or not chosen
            or pool.semaphore.locked()
            or not pool.awake_other(chosen[0])
        ):
            return await primary
        ran: list[int] = []  # the backup's key, once it has one
        backup = asyncio.create_task(
            self._on_a_key(
                pool, image_jpeg, filename, start, avoid=chosen[0], chosen=ran, backup=True
            )
        )
        pool.backups[backup] = None
        backup.add_done_callback(lambda task: pool.backups.pop(task, None))
        try:
            result, winner = await _first_good(primary, backup)
        finally:
            for task in (primary, backup):
                task.cancel()  # the loser; no-op for the finished one
            await asyncio.gather(primary, backup, return_exceptions=True)
            preempted = backup in pool.preempted
            pool.preempted.discard(backup)
        if not ran:
            return result  # no free slot for a second copy: an ordinary run
        cost = result.cost_usd
        if cost is not None:
            cost += settings.harnessrouter_est_cost_per_image  # the other copy ran too
        race = "backup won" if winner is backup else "first won"
        if preempted:
            race = "backup gave its slot to another photo"
        return result.model_copy(update={"cost_usd": cost, "raw": {**result.raw, "race": race}})

    async def _on_a_key(
        self,
        pool: KeyPool,
        image_jpeg: bytes,
        filename: str,
        start: float,
        *,
        avoid: int | None = None,
        chosen: list[int] | None = None,
        backup: bool = False,
    ) -> ProviderResult:
        """Run the photo on the least-busy key, moving to the next key if one can't take it."""
        tried: set[int] = set() if avoid is None else {avoid}
        last: _KeyUnavailable | None = None
        if pool.semaphore.locked():
            if backup:
                raise _NoRoom  # a backup never waits; checking and taking a slot is atomic
            pool.preempt_backup()  # a racing duplicate gives its slot to this photo
        async with pool.semaphore:  # wait for a free task slot, then pick the least-busy key
            while (slot := pool.pick(tried)) is not None:
                if backup and slot.resting_until > time.monotonic():
                    break  # a backup never waits for a resting key
                tried.add(slot.number)
                if chosen is not None:
                    chosen.append(slot.number)
                with pool.running(slot):
                    try:
                        return await asyncio.wait_for(
                            self._detect(slot, image_jpeg, filename, start),
                            settings.harnessrouter_timeout_s,
                        )
                    except TimeoutError as exc:
                        raise ProviderError(
                            "harnessrouter timeout", "The AI took too long on this photo"
                        ) from exc
                    except _KeyUnavailable as exc:
                        last = exc
                        pool.rest(slot, exc.rest_s)
                        nxt = "trying the next key" if len(tried) < len(pool) else "no keys left"
                        log.warning(
                            "harnessrouter: key %d/%d %s; %s", slot.number, len(pool), exc, nxt
                        )
        raise ProviderError(
            f"harnessrouter: no key could take the photo ({last})",
            last.user_message if last else NOT_SET_UP,
        )

    async def _detect(
        self, slot: KeySlot, image: bytes, filename: str, start: float
    ) -> ProviderResult:
        async with self._client(slot) as client:
            file_id = await self._with_retry(lambda: self._upload(client, image, filename))
            content = [
                {"type": "input_file", "file_id": file_id},
                {"type": "input_text", "text": vision_task(filename)},
            ]
            body: dict[str, Any] = {"input": [{"role": "user", "content": content}], "stream": True}
            harness, keys = slot.harness_id, _idempotency_keys()
            text, response = await self._with_retry(lambda: self._run(client, body, harness, keys))
            raw: dict[str, Any] = {
                "response_id": response.get("id"),
                "key": slot.number,  # which key (account) paid for this photo; never the key
                "text": text[:20000],
            }
            try:
                payload = payload_from_text(text)
            except ValueError as first:
                log.info("harnessrouter: invalid JSON (%s); one repair turn", first)
                repair = {
                    "input": [
                        {"role": "user", "content": [{"type": "input_text", "text": REPAIR_TURN}]}
                    ],
                    "previous_response_id": response.get("id"),
                    "stream": True,
                }
                keys = _idempotency_keys()
                text, response = await self._with_retry(
                    lambda: self._run(client, repair, harness, keys)
                )
                raw["repair_text"] = text[:20000]
                try:
                    payload = payload_from_text(text)
                except ValueError as exc:
                    raise ProviderError(f"harnessrouter: unusable reply ({exc})") from exc
        cost = _cost_from(response)
        return ProviderResult(
            items=payload.items,
            latency_ms=int((time.monotonic() - start) * 1000),
            cost_usd=cost if cost is not None else settings.harnessrouter_est_cost_per_image,
            raw=raw,
        )

    async def _with_retry(self, fn):
        try:
            return await fn()
        except _Retryable as exc:
            log.warning("harnessrouter: retrying once after %s", exc)
            await asyncio.sleep(1.0)
            try:
                return await fn()
            except _RateLimited as exc2:  # still busy: let another key take it
                raise _KeyUnavailable(
                    "is rate-limited (HTTP 429)",
                    exc2.retry_after or REST_RATE_LIMITED_S,
                    "The AI is busy right now — try again in a minute",
                ) from exc2
            except _Retryable as exc2:
                raise ProviderError(f"harnessrouter: {exc2}") from exc2

    @staticmethod
    def _check(resp: httpx.Response) -> None:
        code = resp.status_code
        if code == 429:
            raise _RateLimited(_retry_after(resp))
        if code in (502, 503, 504):
            raise _Retryable(f"HTTP {code}")
        if code in (401, 403):
            raise _KeyUnavailable(f"was refused (HTTP {code})", REST_REFUSED_S, SET_UP_WRONG)
        if code == 402:
            raise _KeyUnavailable("is out of credit (HTTP 402)", REST_NO_CREDIT_S, NO_CREDIT)
        if code >= 400:
            raise ProviderError(f"harnessrouter HTTP {code}: {resp.text[:300]}")

    async def _upload(self, client: httpx.AsyncClient, image: bytes, filename: str) -> str:
        try:
            resp = await client.post(
                "/v1/files",
                files={"file": (filename, image, "image/jpeg")},
                data={"purpose": "user_data"},
            )
        except httpx.TransportError as exc:
            raise _Retryable(type(exc).__name__) from exc
        self._check(resp)
        file_id = (resp.json() or {}).get("id")
        if not file_id:
            raise ProviderError("harnessrouter: upload returned no id")
        return file_id

    async def _run(
        self, client: httpx.AsyncClient, body: dict, harness: str, keys: tuple[str, str]
    ) -> tuple[str, dict]:
        """One task. `keys` = Idempotency-Keys for the path form and the metadata form; a retry
        reuses them, so the server replays a task it already ran instead of billing it twice."""
        headers = {"Idempotency-Key": keys[0], "Accept": "text/event-stream"}
        try:
            text, response = await self._stream(client, f"/{harness}/v1/responses", body, headers)
            if response is None:  # path form not found → documented alternative
                alt = {**body, "metadata": {"harness_id": harness}}
                headers["Idempotency-Key"] = keys[1]  # a different body needs its own key
                text, response = await self._stream(client, "/v1/responses", alt, headers)
        except httpx.TransportError as exc:
            raise _Retryable(type(exc).__name__) from exc
        if response is None:
            raise ProviderError("harnessrouter: responses endpoint not found")
        status = response.get("status")
        reason = (response.get("incomplete_details") or {}).get("reason")
        if status == "incomplete" and reason == "balance_exhausted":
            raise _KeyUnavailable("ran out of credit mid-task", REST_NO_CREDIT_S, NO_CREDIT)
        if status == "failed":
            raise ProviderError(f"harnessrouter: task failed {str(response.get('error'))[:300]}")
        return text, response

    async def _stream(
        self, client: httpx.AsyncClient, path: str, body: dict, headers: dict
    ) -> tuple[str, dict | None]:
        """POST and read SSE frames. Returns (text, final response) or ("", None) on 404."""
        chunks: list[str] = []
        final: dict[str, Any] = {}
        terminal: str | None = None
        async with client.stream("POST", path, json=body, headers=headers) as resp:
            if resp.status_code == 404:
                return "", None
            if resp.status_code >= 400:
                await resp.aread()
                self._check(resp)
            ctype = resp.headers.get("content-type", "")
            if "text/event-stream" not in ctype:  # server ignored stream=true → plain JSON
                data = json.loads(await resp.aread() or b"{}")
                return _final_text(data), data
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                etype = event.get("type")
                if etype == "response.output_text.delta":
                    chunks.append(str(event.get("delta") or ""))
                elif etype == "response.created":
                    final = event.get("response") or final
                elif etype in TERMINAL:
                    terminal = etype
                    final = event.get("response") or final
                    break
        if terminal is None:
            raise _Retryable("stream ended without a terminal event")
        if terminal == "response.failed":
            final = {**final, "status": "failed"}
        text = "".join(chunks) or _final_text(final)
        return text, final
