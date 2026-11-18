"""Casual date phrases → campus-local dates (CAMPUS_TZ). Shared by search and request parsing.

"<weekday>" / "this <weekday>" = the next occurrence (today counts); "next <weekday>" = that
weekday in next calendar week (Mon–Sun); "this weekend" = the coming Sat–Sun.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_WD = {d: i for i, d in enumerate(WEEKDAYS)}
_WD.update({d[:3]: i for i, d in enumerate(WEEKDAYS)})
_WD.update({"tues": 1, "weds": 2, "thur": 3, "thurs": 3})
_WD_RE = "|".join(sorted(_WD, key=len, reverse=True))
MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}


@dataclass
class DateHit:
    start: date
    end: date
    label: str
    span: tuple[int, int]  # where in the text it matched, to strip it


def _fmt(d: date) -> str:
    return f"{d:%a} {d:%b} {d.day}"


def find_dates(text: str, today: date) -> DateHit | None:
    t = text.lower()
    m = re.search(r"\b(tonight|today|this evening|this afternoon|asap|right now)\b", t)
    if m:
        return DateHit(today, today, "Today", m.span())
    m = re.search(r"\b(tomorrow|tmrw|tmr)\b( night| morning| evening)?", t)
    if m:
        d = today + timedelta(days=1)
        return DateHit(d, d, "Tomorrow", m.span())
    m = re.search(r"\b(this |the )?weekend\b", t)
    if m and "next weekend" not in t:
        sat = today + timedelta(days=(5 - today.weekday()) % 7)
        if today.weekday() == 6:  # Sunday: the weekend is today
            sat = today
        sun = sat + timedelta(days=(6 - sat.weekday()))
        return DateHit(sat, sun, "This weekend", m.span())
    m = re.search(r"\bnext weekend\b", t)
    if m:
        sat = today + timedelta(days=(5 - today.weekday()) % 7 or 7)
        if today.weekday() >= 5:
            sat = today + timedelta(days=(5 - today.weekday()) % 7 + 7)
        return DateHit(sat, sat + timedelta(days=1), "Next weekend", m.span())
    m = re.search(rf"\bnext ({_WD_RE})\b", t)
    if m:
        target = _WD[m.group(1)]
        monday_next = today + timedelta(days=7 - today.weekday())
        d = monday_next + timedelta(days=target)
        return DateHit(d, d, _fmt(d), m.span())
    full = "|".join(WEEKDAYS + ["tues", "weds", "thurs"])
    m = re.search(rf"\b(?:this |on |by )?({full})\b", t) or re.search(
        rf"\b(?:this|on|by|until|till) ({_WD_RE})\b", t
    )
    if m and m.group(1) in _WD:
        target = _WD[m.group(1)]
        d = today + timedelta(days=(target - today.weekday()) % 7)
        return DateHit(d, d, _fmt(d), m.span())
    m = re.search(r"\bnext week\b", t)
    if m:
        mon = today + timedelta(days=7 - today.weekday())
        return DateHit(mon, mon + timedelta(days=6), "Next week", m.span())
    m = re.search(r"\bthis week\b", t)
    if m:
        sun = today + timedelta(days=6 - today.weekday())
        return DateHit(today, sun, "This week", m.span())
    m = re.search(rf"\b({'|'.join(MONTHS)})[a-z]*\.? (\d{{1,2}})(?:st|nd|rd|th)?\b", t)
    if m:
        try:
            d = date(today.year, MONTHS[m.group(1)[:3]], int(m.group(2)))
        except ValueError:
            return None
        if d < today - timedelta(days=30):
            d = d.replace(year=today.year + 1)
        return DateHit(d, d, _fmt(d), m.span())
    m = re.search(r"\b(\d{1,2})/(\d{1,2})\b", t)
    if m:
        try:
            d = date(today.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
        if d < today - timedelta(days=30):
            d = d.replace(year=today.year + 1)
        return DateHit(d, d, _fmt(d), m.span())
    return None


_WORD_NUM = {
    "a": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "a couple": 2,
    "couple": 2,
    "few": 3,
    "a few": 3,
    "ten": 10,
    "fourteen": 14,
}


def find_duration(text: str) -> tuple[int, tuple[int, int]] | None:
    t = text.lower()
    m = re.search(r"\bovernight\b", t)
    if m:
        return 1, m.span()
    m = re.search(
        r"\bfor (?:the |a )?(\d+|a couple(?: of)?|couple(?: of)?|a few|few|a|one|two|three|"
        r"four|five|six|seven|ten|fourteen) (day|night|week|month)s?\b",
        t,
    )
    if m:
        raw = m.group(1).replace(" of", "")
        n = int(raw) if raw.isdigit() else _WORD_NUM.get(raw, 1)
        unit = {"day": 1, "night": 1, "week": 7, "month": 30}[m.group(2)]
        return min(max(n * unit, 1), 365), m.span()
    m = re.search(r"\bfor (?:the |a )?(week|month|day|night)\b", t)
    if m:
        return {"day": 1, "night": 1, "week": 7, "month": 30}[m.group(1)], m.span()
    return None
