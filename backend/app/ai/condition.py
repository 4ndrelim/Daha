"""Condition check: handoff photos vs return photos of one lent item → a neutral result.

A separate HarnessRouter agent with its own harness (HARNESSROUTER_CONDITION_HARNESS_ID, created
by `scripts/setup_harnessrouter.py --condition`). It reuses the scan's pieces: the key pool's
client, upload, task runner with one retry and one repair turn (providers/harnessrouter.py), and
the JSON extraction (normalize.extract_json). The harness has no tools and a per-task cost cap of
a few cents.

Output is always {"result": "no_changes" | "possible_changes", "note": short text}. The reply is
untrusted: anything else becomes "possible_changes" with a neutral note, and a note that blames
or says "damaged" is replaced. Wording is "possible changes", never "damage" or "fault".

With AI_PROVIDER=mock (tests, CI, free demos), or when the condition harness isn't set up yet,
the answer is a clearly labeled SAMPLE result, so the demo never breaks.
"""

import io
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
from PIL import Image

from app.ai import normalize
from app.ai.prompts import REPAIR_TURN
from app.ai.providers.base import ProviderError
from app.ai.providers.harnessrouter import (
    HarnessRouterVisionProvider,
    KeySlot,
    _cost_from,
    _idempotency_keys,
    _KeyUnavailable,
    key_pairs,
)
from app.core.config import settings

log = logging.getLogger(__name__)

CONDITION_PROMPT_VERSION = "condition-v1"
SLOTS = ("front", "back", "marks")
MAX_SIDE_PX = 1024  # enough to see scratches; keeps the task cheap
NOTE_MAX = 160

CONDITION_SYSTEM = """You compare photos of ONE everyday item that a student lent to a neighbor.
You get 3 photos taken at handoff (BEFORE) and 3 taken at return (AFTER), in the same order:
front, back, and a close-up of any marks that were already there.

Decide only one thing: is there a visible physical difference in the ITEM between BEFORE and AFTER?
Count: a new scratch, dent, crack, stain, tear, a missing or broken-off part, a big new mark.
Ignore: lighting, angle, distance, background, the room, blur, reflections, dust, the item being
cleaner or dirtier in a way that wipes off, and anything that is not the item itself.
Marks that are already visible in the BEFORE photos are not changes.
If the photos are too unclear to compare, or seem to show different items, say possible
changes and say the photos were hard to compare.

Be kind and neutral. Never say "damage", "damaged", "broken", "ruined", "fault" or "blame",
and never guess who caused anything. Describe what looks different and where, in plain words.

Reply with ONLY this JSON, nothing else:
{"result": "no_changes" | "possible_changes", "note": "<one short sentence, max 140 chars>"}"""

TASK_TEXT = (
    "Photos 1-3 are BEFORE (front, back, existing marks). Photos 4-6 are AFTER, same order. "
    "Compare the item and reply with the JSON object only."
)

SAMPLE_NOTE = "Sample result: the AI photo check is off on this server, so nothing was compared."
NEUTRAL_NOTE = {
    "no_changes": "The before and after photos look the same.",
    "possible_changes": "Something may look different. Compare the photos together.",
}
_BLAMING = re.compile(
    r"\b(damag\w*|broke\w*|ruin\w*|destroy\w*|fault\w*|blam\w*|careless\w*|neglig\w*)\b", re.I
)
_LINKS = re.compile(r"https?://\S+|www\.\S+", re.I)


@dataclass
class ConditionVerdict:
    result: str  # no_changes | possible_changes
    note: str
    sample: bool = False
    cost_usd: float | None = None
    latency_ms: int = 0


def sample_verdict(reason: str = SAMPLE_NOTE) -> ConditionVerdict:
    return ConditionVerdict(result="no_changes", note=reason, sample=True)


def clean_verdict(data: Any) -> ConditionVerdict:
    """Untrusted model JSON → a safe verdict. Raises ValueError if there is no usable result."""
    if not isinstance(data, dict):
        raise ValueError("reply is not a JSON object")
    raw = str(data.get("result") or "").strip().lower().replace(" ", "_").replace("-", "_")
    if raw not in NEUTRAL_NOTE:
        raise ValueError(f"unknown result {raw!r}")
    note = _LINKS.sub("", str(data.get("note") or "")).replace("\n", " ").strip()
    note = re.sub(r"\s+", " ", note)
    if not note or _BLAMING.search(note):
        note = NEUTRAL_NOTE[raw]
    if len(note) > NOTE_MAX:
        note = note[: NOTE_MAX - 1].rstrip() + "…"
    return ConditionVerdict(result=raw, note=note)


def shrink(jpeg: bytes) -> bytes:
    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=80)
    return out.getvalue()


def is_set_up() -> bool:
    return bool(settings.harnessrouter_api_keys and settings.harnessrouter_condition_harness_ids)


def _slot() -> KeySlot:
    pairs = key_pairs(settings.harnessrouter_api_keys, settings.harnessrouter_condition_harness_ids)
    key, harness = pairs[0]
    return KeySlot(1, key, harness)


async def run_task(
    before: list[bytes], after: list[bytes], transport: httpx.AsyncBaseTransport | None = None
) -> ConditionVerdict:
    """One paid task on the condition harness: 6 photos in, a cleaned verdict out."""
    provider = HarnessRouterVisionProvider(transport=transport)
    slot = _slot()
    start = time.monotonic()
    try:
        async with provider._client(slot) as client:
            content: list[dict[str, Any]] = []
            for n, image in enumerate([*before, *after], 1):
                stage = "before" if n <= 3 else "after"
                name = f"{stage}-{SLOTS[(n - 1) % 3]}.jpg"
                file_id = await provider._with_retry(
                    lambda image=image, name=name: provider._upload(client, shrink(image), name)
                )
                content.append({"type": "input_file", "file_id": file_id})
            content.append({"type": "input_text", "text": TASK_TEXT})
            body: dict[str, Any] = {"input": [{"role": "user", "content": content}], "stream": True}
            keys = _idempotency_keys()
            text, response = await provider._with_retry(
                lambda: provider._run(client, body, slot.harness_id, keys)
            )
            try:
                verdict = clean_verdict(normalize.extract_json(text))
            except ValueError as first:
                log.info("condition: unusable reply (%s); one repair turn", first)
                repair = {
                    "input": [
                        {"role": "user", "content": [{"type": "input_text", "text": REPAIR_TURN}]}
                    ],
                    "previous_response_id": response.get("id"),
                    "stream": True,
                }
                keys = _idempotency_keys()
                text, response = await provider._with_retry(
                    lambda: provider._run(client, repair, slot.harness_id, keys)
                )
                try:
                    verdict = clean_verdict(normalize.extract_json(text))
                except ValueError as exc:
                    raise ProviderError(f"condition: unusable reply ({exc})") from exc
    except _KeyUnavailable as exc:
        raise ProviderError(f"condition: key {exc}", exc.user_message) from exc
    verdict.cost_usd = _cost_from(response)
    verdict.latency_ms = int((time.monotonic() - start) * 1000)
    return verdict


async def compare(
    before: list[bytes], after: list[bytes], transport: httpx.AsyncBaseTransport | None = None
) -> ConditionVerdict:
    """The entry point. Mock or not set up → labeled sample; harnessrouter → the agent."""
    provider = settings.ai_provider.strip().lower()
    if provider != "harnessrouter":
        return sample_verdict()
    if not is_set_up():
        return sample_verdict(
            "Sample result: the condition-check AI isn't set up yet, so nothing was compared."
        )
    return await run_task(before, after, transport)
