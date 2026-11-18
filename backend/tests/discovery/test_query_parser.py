from datetime import date

import pytest

from app.discovery.query_parser import parse_query

TODAY = date(2026, 11, 17)  # a Tuesday
SAT, SUN = date(2026, 11, 21), date(2026, 11, 22)

CASES = [
    # query, text, category, scope, near_me, from, until, type
    (
        "graphing calculator near me",
        "graphing calculator",
        "academic",
        None,
        True,
        None,
        None,
        None,
    ),
    ("anyone have a vacuum in my dorm?", "vacuum", "dorm", "dorm", False, None, None, None),
    (
        "formal clothes for an interview",
        "formal clothes interview",
        "clothing",
        None,
        False,
        None,
        None,
        None,
    ),
    ("moving boxes available this weekend", "moving boxes", "moving", None, False, SAT, SUN, None),
    (
        "someone who can help repair my bike",
        "repair bike",
        "services",
        None,
        False,
        None,
        None,
        None,
    ),
    ("black binder", "black binder", "academic", None, False, None, None, None),
    ("usb-c charger tonight", "usb-c charger", "tech", None, False, TODAY, TODAY, None),
    ("phone charger today", "phone charger", "tech", None, False, TODAY, TODAY, None),
    ("tent tomorrow", "tent", "sports", None, False, date(2026, 11, 18), date(2026, 11, 18), None),
    ("free stuff", "", None, None, False, None, None, "give"),
    ("giveaway textbooks", "textbooks", "academic", None, False, None, None, "give"),
    ("can I borrow a suit", "suit", "clothing", None, False, None, None, "lend"),
    ("swap board games", "board games", "events", None, False, None, None, "exchange"),
    ("trade my skateboard", "skateboard", "sports", None, False, None, None, "exchange"),
    ("math tutor", "math tutor", "services", None, False, None, None, None),
    ("guitar lessons", "guitar lessons", "services", None, False, None, None, None),
    ("help with moving a couch", "moving couch", "services", None, False, None, None, None),
    ("kettle nearby", "kettle", "dorm", None, True, None, None, None),
    (
        "projector on friday",
        "projector",
        "events",
        None,
        False,
        date(2026, 11, 20),
        date(2026, 11, 20),
        None,
    ),
    ("lamp wednesday", "lamp", "dorm", None, False, date(2026, 11, 18), date(2026, 11, 18), None),
    (
        "drill next wednesday",
        "drill",
        "moving",
        None,
        False,
        date(2026, 11, 25),
        date(2026, 11, 25),
        None,
    ),
    ("spices for curry", "spices curry", "consumables", None, False, None, None, None),
    ("anyone have a hdmi cable?", "hdmi cable", "tech", None, False, None, None, None),
    ("looking for a yoga mat on campus", "yoga mat", "sports", "campus", False, None, None, None),
    ("SAT prep book", "SAT prep book", "academic", None, False, None, None, None),
    ("sun hat", "sun hat", None, None, False, None, None, None),
    ("", "", None, None, False, None, None, None),
    ("xylophone", "xylophone", None, None, False, None, None, None),
    (
        "is there anybody with a bike pump near me?",
        "bike pump",
        "sports",
        None,
        True,
        None,
        None,
        None,
    ),
    ("need a lab coat for the week", "lab coat week", "academic", None, False, None, None, None),
    ("costume this weekend please", "costume", "clothing", None, False, SAT, SUN, None),
]


@pytest.mark.parametrize("q,text,category,scope,near,start,end,tx", CASES)
def test_parse_query(q, text, category, scope, near, start, end, tx):
    p = parse_query(q, TODAY)
    assert p.text == text
    assert p.category == category
    assert p.scope == scope
    assert p.near_me is near
    assert (p.available_from, p.available_until) == (start, end)
    assert p.transaction_type == tx


def test_chips_are_plain_english():
    p = parse_query("graphing calculator near me this weekend", TODAY)
    assert p.chips == ["Academic", "Near you", "This weekend"]


def test_sunday_weekend_is_today():
    p = parse_query("tent this weekend", date(2026, 11, 22))
    assert p.available_from == date(2026, 11, 22) and p.available_until == date(2026, 11, 22)


def test_long_query_is_truncated_and_fast():
    import time

    t = time.perf_counter()
    for _ in range(200):
        parse_query("anyone have " + "a really long query " * 50)
    assert (time.perf_counter() - t) / 200 < 0.005
