"""Casual request text → editable fields (PLAN.md C3). Rules only, a few ms; no paid AI."""

import logging
import re
from datetime import date, timedelta

from app import schemas
from app.core.geo import campus_today
from app.discovery.dates import find_dates, find_duration
from app.discovery.keywords import category_for

log = logging.getLogger(__name__)
MAX_TEXT = 1000

_OFFER = re.compile(
    r"\b(does anyone want|do you guys want|anyone want|who wants|giving away|give away|"
    r"up for grabs|free to (a )?good home|i have (a |an |some )?(extra|spare)|offering|"
    r"selling|getting rid of)\b",
    re.I,
)
_REQUEST = re.compile(
    r"\b(any ?one|any ?body|some ?one|some ?body) (here )?(have|has|got|own|with|lend)\b|"
    r"\b(can|could|may) (i|we) (borrow|use|get|have)\b|\blooking for\b|\bneed(ed|s)?\b|"
    r"\bin need of\b|\bsearching for\b|\blend me\b|"
    r"\b(some ?one|some ?body|any ?one) (who|that) can\b",
    re.I,
)
_LEADS = [
    r"^(hey|hi|hello|yo|hii+|guys|all|everyone|y'?all|ok|so|um+|pls|please)\b[\s,!.:-]*",
    r"^(does|do|did|would|will|is|are|has)?\s*(any ?one|any ?body|some ?one|some ?body|anyone here|"
    r"y'?all|you guys)\s+(here\s+)?(happen to\s+)?(have|has|got|own|with|wanna|want)\s*",
    r"^(does|do|would)?\s*(any ?one|any ?body|some ?one|some ?body)\s+(want|wanna)\s*",
    r"^(can|could|may|might) (i|we) (please )?(borrow|use|get|have|grab|take)\s*",
    r"^(can|could|would) (some ?one|some ?body|any ?one|you) (please )?"
    r"(lend|give|loan|spot)( me| us)?\s*",
    r"^(i'?m |i am |we'?re |we are )?(looking for|searching for|in need of|hunting for)\s*",
    r"^(i |we )?(really |urgently |desperately )?(need|want|could use)\s*",
    r"^(giving away|give away|up for grabs|offering|selling|getting rid of|free)[:,!]?\s*",
    r"^(who wants|anyone want|i have|i've got|i got)\s*",
    r"^(to borrow|borrow)\s*",
    r"^(to )?(swap|trade|exchange)( (my|a|an|some))?\s+",
]
_LEAD_RES = [re.compile(p, re.I) for p in _LEADS]
_CUT = re.compile(
    r"\s(i|i'?d|i'?m|that|which|so|because|cause|cuz|for|to|this|next|tonight|today|tomorrow|on|by|"
    r"until|till|before|after|in|from|at|near|asap|please|pls|if|anyone|when|while|going|my|we|"
    r"you|thanks|thank|lmk|dm|ty|starting|beginning|around|during|or so|they|they'?re|"
    r"not|anymore)\b|[,.?!;:—–]|\s-\s|\(",
    re.I,
)
_NUM_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_QTY = re.compile(
    r"^(a couple( of)?|couple( of)?|a few|few|several|\d{1,2}|one|two|three|four|five|six|seven|"
    r"eight|nine|ten)\s+",
    re.I,
)
_DET = re.compile(r"^(a|an|the|some|any|my|your|ur|another|extra|spare|pair of|a pair of)\s+", re.I)
COLORS = [
    "black",
    "white",
    "navy",
    "blue",
    "red",
    "green",
    "gray",
    "grey",
    "pink",
    "purple",
    "yellow",
    "orange",
    "brown",
    "beige",
    "silver",
    "gold",
    "tan",
    "maroon",
    "cardinal",
]
_COLOR = re.compile(rf"\b({'|'.join(COLORS)})\b", re.I)
_SIZE = re.compile(
    r"\bsize\s+([a-z0-9.]+(?:\s*(?:or|/|-)\s*[a-z0-9.]+)?)\b|\b(xxs|xs|xxl|xl)\b|"
    r"\b(\d{2}[rls])\b|\b(\d{1,2}(?:\.5)?) ?(?:inch|in|\")",
    re.I,
)
_CONNECTOR = re.compile(r"\b(usb[- ]?c|lightning|micro[- ]?usb|usb[- ]?a|magsafe)\b", re.I)
_LEND = re.compile(r"\b(borrow|lend|loan|use for|for (a|the) (day|night|week|weekend))\b", re.I)
_GIVE = re.compile(
    r"\b(can i have|to keep|keep|giving away|give away|free|up for grabs|use up)\b", re.I
)
_SWAP = re.compile(r"\b(swap|trade|exchange)\b", re.I)


_ACRONYMS = re.compile(
    r"\b(hdmi|usb|usb-c|vga|tv|ps[345]|ti-\d+|ipad|iphone|led|lcd|dvd|cd|hdd|ssd|sd|ac|uv|pc)\b",
    re.I,
)
_HELP = re.compile(
    r"\b(?:help(?: me| us)?(?: with)?|someone (?:who|that) can|somebody (?:who|that) can)\s+(.+)",
    re.I,
)
_CASING = {"ipad": "iPad", "iphone": "iPhone"}


def _case(name: str) -> str:
    name = _ACRONYMS.sub(lambda m: _CASING.get(m.group(1).lower(), m.group(1).upper()), name)
    return name[:1].upper() + name[1:]


def _kind(text: str) -> str:
    if _OFFER.search(text):
        return "offer"
    if _REQUEST.search(text) or "?" in text:
        return "request"
    if re.search(r"\bfree\b", text, re.I):
        return "offer"
    return "other"


def _noun_phrase(text: str, spans: list[tuple[int, int]]) -> tuple[str, int]:
    """Strip lead phrases and dates; cut at the first clause boundary; peel off quantity."""
    for a, b in sorted(spans, reverse=True):
        text = text[:a] + " " + text[b:]
    s = re.sub(r"\s+", " ", text).strip()
    changed = True
    while changed:
        changed = False
        for rx in _LEAD_RES:
            new = rx.sub("", s, count=1).strip()
            if new != s:
                s, changed = new, True
    s = _DET.sub("", s)  # "giving away my old lamp": drop "my" before cutting at it
    m = _CUT.search(" " + s)
    if m:
        s = (" " + s)[: m.start()].strip()
    qty = 1
    for _ in range(3):
        m = _QTY.match(s)
        if m:
            word = m.group(1).lower()
            if word.isdigit():
                qty = int(word)
            elif word in _NUM_WORDS:
                qty = _NUM_WORDS[word]
            elif "couple" in word:
                qty = 2
            else:
                qty = 3
            s = s[m.end() :]
        s = _DET.sub("", s)
    s = s.strip(" -'\"")
    return s[:80].strip(), max(1, min(qty, 99))


def _attributes(text: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    colors = list(dict.fromkeys(c.lower().replace("grey", "gray") for c in _COLOR.findall(text)))
    if colors:
        attrs["color"] = " or ".join(colors[:3])
    m = _SIZE.search(text)
    if m:
        size = next(g for g in m.groups() if g)
        attrs["size"] = re.sub(r"\s+", " ", size).upper() if len(size) <= 3 else size
    m = _CONNECTOR.search(text)
    if m:
        attrs["connector"] = m.group(1).lower().replace(" ", "-").replace("usbc", "usb-c")
    return attrs


def _category_fallback(text: str) -> str | None:
    """Nearest category description by embedding; None if embeddings are unavailable."""
    try:
        from app.discovery.categories import nearest_category

        return nearest_category(text)
    except Exception:  # noqa: BLE001 — parsing must never fail
        log.debug("category fallback unavailable", exc_info=True)
        return None


def parse_request(text: str, today: date | None = None) -> schemas.ParsedRequest:
    raw = (text or "").strip()[:MAX_TEXT]
    today = today or campus_today()
    if not raw:
        return schemas.ParsedRequest(
            kind="other",
            title="",
            item_name=None,
            category=None,
            attributes={},
            quantity=1,
            needed_from=None,
            needed_until=None,
            duration_days=None,
            transaction_type=None,
            confidence=0.0,
        )
    kind = _kind(raw)
    spans: list[tuple[int, int]] = []
    hit = find_dates(raw, today)
    if hit:
        spans.append(hit.span)
    dur = find_duration(raw)
    duration = None
    if dur:
        duration, span = dur
        spans.append(span)
    if hit and dur and (hit.span[0] < dur[1][1] and dur[1][0] < hit.span[1]):
        spans = [hit.span]  # overlapping ("for the weekend") — keep the date
    item_name, quantity = _noun_phrase(raw, spans)
    attrs = _attributes(raw)
    help_m = _HELP.search(raw)
    if help_m and category_for(raw) == "services":
        phrase, _ = _noun_phrase(re.sub(r"\b(my|our|your)\s+", "", help_m.group(1)), [])
        if phrase:
            item_name = "help " + phrase if not phrase.lower().startswith("help") else phrase

    category = category_for(item_name) if item_name else None
    by_keyword = category is not None
    if category is None:
        category = category_for(raw)
        by_keyword = category is not None
    if category is None and item_name:
        category = _category_fallback(item_name)

    if _SWAP.search(raw):
        tx = "exchange"
    elif kind == "offer" or _GIVE.search(raw):
        tx = "give"
    elif _LEND.search(raw):
        tx = "lend"
    elif category == "consumables":
        tx = "give"
    else:
        tx = None
    if category == "services" and tx == "lend":
        tx = "give"

    needed_from = needed_until = None
    if hit:
        needed_from, needed_until = hit.start, hit.end
        if duration and duration > (needed_until - needed_from).days + 1:
            needed_until = needed_from + timedelta(days=duration - 1)

    title = _case(item_name) if item_name else raw[:60].strip()
    confidence = 0.3 + (0.3 if item_name else 0) + (0.2 if by_keyword else 0.1 if category else 0)
    confidence += 0.1 if kind != "other" else 0
    confidence += 0.05 if hit else 0
    return schemas.ParsedRequest(
        kind=kind,
        title=title[:200],
        item_name=item_name or None,
        category=category,
        attributes=attrs,
        quantity=quantity,
        needed_from=needed_from,
        needed_until=needed_until,
        duration_days=duration,
        transaction_type=tx,
        confidence=round(min(confidence, 0.95), 2),
    )
