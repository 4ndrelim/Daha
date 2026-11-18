"""Rule-based search query parsing (PLAN.md C2). No LLM; well under 5 ms."""

import re
from datetime import date

from app import schemas
from app.core.geo import campus_today
from app.discovery.config import CATEGORY_LABELS
from app.discovery.dates import find_dates
from app.discovery.keywords import category_for

MAX_QUERY = 200
_NEAR = re.compile(r"\b(near me|nearby|close by|close to me|around me|near here|closest)\b", re.I)
_DORM = re.compile(r"\b(in|from|at) (my|our) (dorm|hall|building|house)\b|\bmy dorm\b", re.I)
_CAMPUS = re.compile(r"\b(on|across|anywhere on) campus\b", re.I)
_TYPES = [
    (
        re.compile(
            r"\b(free|for free|giveaway|give ?away|giving away|up for grabs|to keep)\b", re.I
        ),
        "give",
        "Free",
    ),
    (re.compile(r"\b(swap|trade|exchange)\b", re.I), "exchange", "Swap"),
    (re.compile(r"\b(borrow|lend|loan|rent)\b", re.I), "lend", "Borrow"),
]
_FILLER = re.compile(
    r"\b(does |do |is there |are there )?(anyone|anybody|someone|somebody|any ?one)( here)?"
    r"( (have|has|got|own|with))?\b|\bi('m| am)? (need|want|looking for|searching for)\b|"
    r"\b(looking for|searching for|can i (borrow|get|use)|could i (borrow|get|use)|"
    r"i could (borrow|use)|available|please|pls|plz|thanks|thank you|who can|that i can|"
    r"i can|for me|to me|lend me|let me)\b",
    re.I,
)
_STOP = {
    "a",
    "an",
    "the",
    "some",
    "any",
    "for",
    "to",
    "of",
    "me",
    "my",
    "i",
    "is",
    "are",
    "have",
    "has",
    "with",
    "and",
    "or",
    "on",
    "in",
    "at",
    "it",
    "that",
    "this",
    "can",
    "could",
    "would",
    "will",
    "you",
    "your",
    "one",
    "who",
    "help",
    "need",
    "want",
    "get",
    "use",
    "maybe",
    "like",
    "just",
    "really",
    "be",
    "so",
    "if",
    "by",
    "stuff",
    "things",
    "thing",
    "something",
    "anything",
    "items",
    "item",
    "what",
    "whats",
    "everything",
}


def parse_query(q: str, today: date | None = None) -> schemas.ParsedQuery:
    raw = (q or "")[:MAX_QUERY]
    today = today or campus_today()
    text = raw
    chips: list[str] = []

    category = category_for(raw)
    near_me = bool(_NEAR.search(raw))
    scope = "dorm" if _DORM.search(raw) else ("campus" if _CAMPUS.search(raw) else None)
    tx_type = None
    for pattern, value, _label in _TYPES:
        if pattern.search(raw):
            tx_type = value
            break

    hit = find_dates(raw, today)
    available_from = available_until = None
    if hit:
        available_from, available_until = hit.start, hit.end
        text = text[: hit.span[0]] + " " + text[hit.span[1] :]

    for pattern in (_NEAR, _DORM, _CAMPUS, _FILLER, *(p for p, _, _ in _TYPES)):
        text = pattern.sub(" ", text)
    text = re.sub(r"\b(near|nearby)\b", " ", text, flags=re.I)
    words = [w for w in re.findall(r"[\w'+-]+", text) if w.lower() not in _STOP]
    text = " ".join(words).strip(" -'")

    if category:
        chips.append(CATEGORY_LABELS[category])
    if near_me:
        chips.append("Near you")
    if scope == "dorm":
        chips.append("In your dorm")
    if hit:
        chips.append(hit.label)
    if tx_type:
        chips.append(next(label for _, v, label in _TYPES if v == tx_type))

    return schemas.ParsedQuery(
        text=text,
        category=category,
        scope=scope,
        near_me=near_me,
        available_from=available_from,
        available_until=available_until,
        transaction_type=tx_type,
        chips=chips,
    )
