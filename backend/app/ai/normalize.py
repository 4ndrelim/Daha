"""Turn whatever a vision model said into safe, contract-valid detections.

The prompt asks for clean JSON, but we never trust it: models return fences, prose, wrong
enums, out-of-range numbers, or items that must never be listed (IDs, keys, cash…).
"""

import json
import re
from typing import Any

from app.ai.schemas import DetectedItemRaw, DetectionPayload

MAX_ITEMS = 20
MAX_NAME = 120
MAX_DESCRIPTION = 280
CATEGORIES = {
    "academic",
    "tech",
    "clothing",
    "dorm",
    "consumables",
    "sports",
    "moving",
    "events",
    "services",
    "other",
}
CONDITIONS = {"new", "like_new", "good", "fair", "worn"}
TX_TYPES = {"lend", "give", "exchange"}
_CONDITION_ALIASES = {"like new": "like_new", "likenew": "like_new", "used": "good", "poor": "worn"}
_TX_ALIASES = {
    "free": "give",
    "giveaway": "give",
    "swap": "exchange",
    "trade": "exchange",
    "borrow": "lend",
    "loan": "lend",
}

# Never list these, whatever the model says (PLAN.md C1.3 "Never" rule, enforced server-side).
_FORBIDDEN = re.compile(
    r"\b(passport|driver'?s? licen[cs]e|student id|id card|identity card|credit card|debit card|"
    r"bank card|cash|money|banknotes?|wallet|key ?ring|keychain|prescription|medication|"
    r"pills?|documents?|letters?|mail|envelopes?|bank statement|ssn|social security|tax form|"
    r"photo of|photograph of|selfie)\b",
    re.I,
)
_KEYS = re.compile(r"(?<!allen )(?<!hex )(?<!piano )\bkeys?\b(?!\s*(board|lime|chain))", re.I)
_PEOPLE = re.compile(
    r"^(a |the )?(person|people|man|woman|child|kid|baby|student|pet|dog|cat)s?$", re.I
)
# Pre-unticked with a reason, even if the model forgot to flag them.
_SENSITIVE: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(tooth ?brush|razor|deodorant|retainer|hairbrush|comb|loofah|tweezers)\b", re.I
        ),
        "Personal hygiene item",
    ),
    (re.compile(r"\b(underwear|boxers|briefs|bra|lingerie|socks)\b", re.I), "Underwear"),
    (
        re.compile(r"\b(lipstick|mascara|eyeliner|foundation|concealer|makeup)\b", re.I),
        "Opened cosmetics",
    ),
    (
        re.compile(
            r"\b(jewel(le)?ry|necklace|bracelet|earrings?|wrist ?watch)\b"
            r"|(?<![-\w])rings?\b(?!\s*(binder|light|stand))",
            re.I,
        ),
        "Valuable",
    ),
]


def extract_json(text: str) -> dict:
    """Parse a model reply: strip code fences, take the outermost {...}. Raises ValueError."""
    if not text or not text.strip():
        raise ValueError("empty reply")
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", s, re.S | re.I)
    if fence:
        s = fence.group(1).strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in reply")
    try:
        data = json.loads(s[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("JSON is not an object")
    return data


def _clean_str(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        value = "" if value is None else str(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit].rstrip()


def _num(value: Any, default: float) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return default if f != f else f  # NaN


def _bbox(value: Any) -> list[float] | None:
    if not isinstance(value, list | tuple) or len(value) != 4:
        return None
    try:
        x, y, w, h = (float(v) for v in value)
    except (TypeError, ValueError):
        return None
    if any(v != v for v in (x, y, w, h)):
        return None
    if max(x, y, w, h) > 1.5:  # pixel coords slipped through; can't normalize without size
        return None
    x, y = min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)
    w, h = min(max(w, 0.0), 1.0 - x), min(max(h, 0.0), 1.0 - y)
    if w < 0.01 or h < 0.01:
        return None
    return [round(x, 4), round(y, 4), round(w, 4), round(h, 4)]


MAX_VALUE_USD = 10000


def _value(raw: Any) -> int | None:
    """The model's value estimate → whole dollars in 0..10000, else None. Never made up here."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, str):
        raw = raw.strip().replace("$", "").replace(",", "").replace("USD", "").strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value != value or value < 0 or value > MAX_VALUE_USD:  # NaN or out of range
        return None
    return round(value)


def coerce_item(raw: Any) -> DetectedItemRaw | None:
    """One model item → a valid DetectedItemRaw, or None to drop it."""
    if not isinstance(raw, dict):
        return None
    name = _clean_str(raw.get("name"), MAX_NAME)
    if len(name) < 2 or _FORBIDDEN.search(name) or _PEOPLE.match(name) or _KEYS.search(name):
        return None
    category = str(raw.get("category") or "other").strip().lower()
    category = category if category in CATEGORIES else "other"
    cond = raw.get("condition_guess")
    cond = str(cond).strip().lower() if cond is not None else None
    cond = _CONDITION_ALIASES.get(cond or "", cond)
    cond = cond if cond in CONDITIONS else None
    tx = str(raw.get("suggested_transaction_type") or "").strip().lower()
    tx = _TX_ALIASES.get(tx, tx)
    if tx not in TX_TYPES:
        tx = "give" if category == "consumables" else "lend"
    if category == "services" and tx == "lend":
        tx = "give"  # services can't be lent (items service rejects it)
    try:
        qty = int(_num(raw.get("quantity"), 1))
    except (OverflowError, ValueError):
        qty = 1
    share = raw.get("suggested_share")
    share = share if isinstance(share, bool) else str(share).lower() not in ("false", "0", "no")
    reason = _clean_str(raw.get("sensitive_reason"), 120) or None
    for pattern, why in _SENSITIVE:
        if pattern.search(name):
            share, reason = False, reason or why
            break
    if not share and not reason:
        reason = "Looks personal"
    return DetectedItemRaw(
        name=name,
        category=category,
        description=_clean_str(raw.get("description"), MAX_DESCRIPTION),
        quantity=min(max(qty, 1), 999),
        condition_guess=cond,
        confidence=round(min(max(_num(raw.get("confidence"), 0.5), 0.0), 1.0), 3),
        bbox=_bbox(raw.get("bbox")),
        suggested_share=share,
        sensitive_reason=None if share else reason,
        suggested_transaction_type=tx,
        value_usd=_value(raw.get("value_usd")),
    )


def normalize_items(raw_items: Any) -> list[DetectedItemRaw]:
    """Coerce, drop forbidden, dedupe by name within the photo (summing quantity), cap at 20."""
    if not isinstance(raw_items, list):
        return []
    out: dict[str, DetectedItemRaw] = {}
    for raw in raw_items:
        if isinstance(raw, DetectedItemRaw):
            raw = raw.model_dump()
        item = coerce_item(raw)
        if item is None:
            continue
        key = re.sub(r"[^a-z0-9]+", " ", item.name.lower()).strip()
        if key in out:
            prev = out[key]
            prev.quantity = min(prev.quantity + item.quantity, 999)
            prev.confidence = max(prev.confidence, item.confidence)
            continue
        out[key] = item
        if len(out) >= MAX_ITEMS:
            break
    return list(out.values())


def payload_from_text(text: str) -> DetectionPayload:
    """Model text → normalized payload. Raises ValueError if there's no usable JSON."""
    data = extract_json(text)
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("JSON has no items list")
    return DetectionPayload(items=normalize_items(items))
