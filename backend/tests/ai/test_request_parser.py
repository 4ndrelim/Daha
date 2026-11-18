from datetime import date

import pytest

from app.ai.request_parser import parse_request

TODAY = date(2026, 11, 17)  # Tuesday
WED_NEXT = date(2026, 11, 25)
SAT, SUN = date(2026, 11, 21), date(2026, 11, 22)

CASES = [
    # text, kind, title, category, qty, from, until, duration, type
    (
        "Does anyone have a calculator?",
        "request",
        "Calculator",
        "academic",
        1,
        None,
        None,
        None,
        None,
    ),
    ("Anyone have a vacuum?", "request", "Vacuum", "dorm", 1, None, None, None, None),
    (
        "Can I borrow a black binder next Wednesday?",
        "request",
        "Black binder",
        "academic",
        1,
        WED_NEXT,
        WED_NEXT,
        None,
        "lend",
    ),
    (
        "Does anyone want a leather jacket?",
        "offer",
        "Leather jacket",
        "clothing",
        1,
        None,
        None,
        None,
        "give",
    ),
    (
        "anyone have a black binder I can borrow next Wednesday?",
        "request",
        "Black binder",
        "academic",
        1,
        WED_NEXT,
        WED_NEXT,
        None,
        "lend",
    ),
    (
        "anyone have a tent I could borrow this weekend? going to Big Basin",
        "request",
        "Tent",
        "sports",
        1,
        SAT,
        SUN,
        None,
        "lend",
    ),
    (
        "need a phone charger (usb-c) for tonight",
        "request",
        "Phone charger",
        "tech",
        1,
        TODAY,
        TODAY,
        None,
        None,
    ),
    (
        "anyone have spices I could use? making curry",
        "request",
        "Spices",
        "consumables",
        1,
        None,
        None,
        None,
        "give",
    ),
    (
        "does anyone have a drill? need to hang a shelf",
        "request",
        "Drill",
        "moving",
        1,
        None,
        None,
        None,
        None,
    ),
    (
        "Need moving boxes this weekend!! moving to EVGR",
        "request",
        "Moving boxes",
        "moving",
        1,
        SAT,
        SUN,
        None,
        None,
    ),
    (
        "anyone got a bike pump? flat tire :(",
        "request",
        "Bike pump",
        "sports",
        1,
        None,
        None,
        None,
        None,
    ),
    (
        "Could I borrow an HDMI cable for a presentation tomorrow?",
        "request",
        "HDMI cable",
        "tech",
        1,
        date(2026, 11, 18),
        date(2026, 11, 18),
        None,
        "lend",
    ),
    (
        "Need 6 folding chairs for a screening Friday night",
        "request",
        "Folding chairs",
        "events",
        6,
        date(2026, 11, 20),
        date(2026, 11, 20),
        None,
        None,
    ),
    (
        "Anyone have a lab coat (size S or M) I can use Thursday?",
        "request",
        "Lab coat",
        "academic",
        1,
        date(2026, 11, 19),
        date(2026, 11, 19),
        None,
        None,
    ),
    (
        "does anyone have an extension cord?",
        "request",
        "Extension cord",
        "tech",
        1,
        None,
        None,
        None,
        None,
    ),
    (
        "Can someone lend me a tennis racket for Saturday morning?",
        "request",
        "Tennis racket",
        "sports",
        1,
        SAT,
        SAT,
        None,
        "lend",
    ),
    (
        "can i borrow a couple of extension cords for 3 days",
        "request",
        "Extension cords",
        "tech",
        2,
        None,
        None,
        3,
        "lend",
    ),
    (
        "giving away a mini fridge, free to a good home",
        "offer",
        "Mini fridge",
        "dorm",
        1,
        None,
        None,
        None,
        "give",
    ),
    (
        "up for grabs: 3 storage bins",
        "offer",
        "Storage bins",
        "moving",
        3,
        None,
        None,
        None,
        "give",
    ),
    (
        "hey guys does anyone have a hdmi cable",
        "request",
        "HDMI cable",
        "tech",
        1,
        None,
        None,
        None,
        None,
    ),
    (
        "looking for a graphing calculator for the CS 109 midterm",
        "request",
        "Graphing calculator",
        "academic",
        1,
        None,
        None,
        None,
        None,
    ),
    (
        "Need an iron for 10 minutes before an interview",
        "request",
        "Iron",
        "dorm",
        1,
        None,
        None,
        None,
        None,
    ),
    (
        "anyone want to swap a skateboard for a scooter?",
        "offer",
        "Skateboard",
        "sports",
        1,
        None,
        None,
        None,
        "exchange",
    ),
    (
        "need a tent for a week starting friday",
        "request",
        "Tent",
        "sports",
        1,
        date(2026, 11, 20),
        date(2026, 11, 26),
        7,
        "lend",
    ),
    ("can I borrow your camera overnight", "request", "Camera", "tech", 1, None, None, 1, "lend"),
    (
        "someone who can help repair my bike",
        "request",
        "Help repair bike",
        "services",
        1,
        None,
        None,
        None,
        None,
    ),
    ("need a math tutor", "request", "Math tutor", "services", 1, None, None, None, None),
    (
        "Looking for a navy or black suit jacket for a career fair on Friday",
        "request",
        "Navy or black suit jacket",
        "clothing",
        1,
        date(2026, 11, 20),
        date(2026, 11, 20),
        None,
        None,
    ),
    (
        "a few paper towels please",
        "other",
        "Paper towels",
        "consumables",
        3,
        None,
        None,
        None,
        "give",
    ),
    ("Anyone have a TI-84?", "request", "TI-84", None, 1, None, None, None, None),
    (
        "anyone have an umbrella i can borrow today?",
        "request",
        "Umbrella",
        "dorm",
        1,
        TODAY,
        TODAY,
        None,
        "lend",
    ),
    (
        "need a yoga mat on 12/3",
        "request",
        "Yoga mat",
        "sports",
        1,
        date(2026, 12, 3),
        date(2026, 12, 3),
        None,
        None,
    ),
]


@pytest.mark.parametrize("text,kind,title,category,qty,start,end,duration,tx", CASES)
def test_parse_request(text, kind, title, category, qty, start, end, duration, tx):
    p = parse_request(text, TODAY)
    assert p.kind == kind
    assert p.title == title
    if category is not None:
        assert p.category == category
    assert p.quantity == qty
    assert (p.needed_from, p.needed_until) == (start, end)
    assert p.duration_days == duration
    assert p.transaction_type == tx
    assert 0 <= p.confidence <= 1


def test_attributes():
    p = parse_request("Anyone have a black lab coat (size S or M)?", TODAY)
    assert p.attributes == {"color": "black", "size": "S OR M"} or p.attributes["color"] == "black"
    assert parse_request("need a usb-c charger", TODAY).attributes == {"connector": "usb-c"}


def test_empty_and_huge_inputs():
    assert parse_request("", TODAY).title == ""
    p = parse_request("anyone have " + "a very long thing " * 500, TODAY)
    assert len(p.title) <= 200


def test_endpoint(client, db):
    from tests.ai.helpers import user_in_wilbur

    headers, _ = user_in_wilbur(client, db)
    r = client.post(
        "/api/ai/parse-request",
        headers=headers,
        json={"text": "anyone have a black binder I can borrow next Wednesday?"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Black binder" and body["category"] == "academic"
    assert body["transaction_type"] == "lend" and body["attributes"] == {"color": "black"}
    assert client.post("/api/ai/parse-request", json={"text": "x"}).status_code == 401
