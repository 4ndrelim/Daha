"""HarnessRouter vision: upload → run a harness task (SSE stream) → JSON (PLAN.md C0/C1.2).

HarnessRouter runs full agent harnesses, so a "task" can take tens of seconds. Guard rails:
- a process-wide semaphore (HARNESSROUTER_MAX_CONCURRENCY; the free plan allows 2 tasks);
- an overall timeout per photo (HARNESSROUTER_TIMEOUT_S);
- one retry on network errors and 5xx; one "repair" turn if the reply isn't valid JSON.
The API key is only ever sent in the Authorization header and never logged.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any

import httpx

from app.ai.normalize import payload_from_text
from app.ai.prompts import REPAIR_TURN, vision_task
from app.ai.providers.base import ProviderError
from app.ai.schemas import ProviderResult
from app.core.config import settings

log = logging.getLogger(__name__)
TERMINAL = {"response.completed", "response.incomplete", "response.failed"}
_semaphore: asyncio.Semaphore | None = None


def _sem() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(max(1, settings.harnessrouter_max_concurrency))
    return _semaphore


class _Retryable(Exception):
    pass


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


class HarnessRouterVisionProvider:
    name = "harnessrouter"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self.model = settings.harnessrouter_model or settings.harnessrouter_base
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        if not settings.harnessrouter_api_key or not settings.harnessrouter_vision_harness_id:
            raise ProviderError(
                "HARNESSROUTER_API_KEY / HARNESSROUTER_VISION_HARNESS_ID not set",
                "AI scanning isn't set up yet — list items manually",
            )
        return httpx.AsyncClient(
            base_url=settings.harnessrouter_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.harnessrouter_api_key}"},
            timeout=httpx.Timeout(30.0, read=float(settings.harnessrouter_timeout_s)),
            transport=self._transport,
        )

    async def detect(self, image_jpeg: bytes, filename: str) -> ProviderResult:
        start = time.monotonic()
        async with _sem():
            try:
                return await asyncio.wait_for(
                    self._detect(image_jpeg, filename, start), settings.harnessrouter_timeout_s
                )
            except TimeoutError as exc:
                raise ProviderError(
                    "harnessrouter timeout", "The AI took too long on this photo"
                ) from exc

    async def _detect(self, image: bytes, filename: str, start: float) -> ProviderResult:
        async with self._client() as client:
            file_id = await self._with_retry(lambda: self._upload(client, image, filename))
            content = [
                {"type": "input_file", "file_id": file_id},
                {"type": "input_text", "text": vision_task(filename)},
            ]
            body: dict[str, Any] = {"input": [{"role": "user", "content": content}], "stream": True}
            text, response = await self._with_retry(lambda: self._run(client, body))
            raw: dict[str, Any] = {"response_id": response.get("id"), "text": text[:20000]}
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
                text, response = await self._with_retry(lambda: self._run(client, repair))
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
            except _Retryable as exc2:
                raise ProviderError(f"harnessrouter: {exc2}") from exc2

    @staticmethod
    def _check(resp: httpx.Response) -> None:
        if resp.status_code >= 500 or resp.status_code == 429:
            raise _Retryable(f"HTTP {resp.status_code}")
        if resp.status_code >= 400:
            raise ProviderError(f"harnessrouter HTTP {resp.status_code}: {resp.text[:300]}")

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

    async def _run(self, client: httpx.AsyncClient, body: dict) -> tuple[str, dict]:
        harness = settings.harnessrouter_vision_harness_id
        headers = {"Idempotency-Key": str(uuid.uuid4()), "Accept": "text/event-stream"}
        try:
            text, response = await self._stream(client, f"/{harness}/v1/responses", body, headers)
            if response is None:  # path form not found → documented alternative
                alt = {**body, "metadata": {"harness_id": harness}}
                headers["Idempotency-Key"] = str(uuid.uuid4())
                text, response = await self._stream(client, "/v1/responses", alt, headers)
        except httpx.TransportError as exc:
            raise _Retryable(type(exc).__name__) from exc
        if response is None:
            raise ProviderError("harnessrouter: responses endpoint not found")
        status = response.get("status")
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
