# ruff: noqa: E501
"""Deterministic fake vision: same photo → same items. No network, no cost."""

import asyncio
import hashlib
import random
import time

from app.ai.normalize import normalize_items
from app.ai.schemas import ProviderResult
from app.core.config import settings

# (name, category, description, condition, transaction type)
POOL: list[tuple[str, str, str, str, str]] = [
    (
        "Graphing calculator (TI-84)",
        "academic",
        "Silver TI-84 Plus with a slide-on cover.",
        "good",
        "lend",
    ),
    ("Black 3-ring binder", "academic", "1.5-inch binder with clear front pocket.", "good", "lend"),
    (
        "Intro to Psychology textbook",
        "academic",
        "Hardcover, 12th edition, light highlighting.",
        "fair",
        "lend",
    ),
    ("Lab goggles", "academic", "Clear anti-fog safety goggles.", "like_new", "lend"),
    ("Spiral notebooks (pack)", "academic", "Three unused college-ruled notebooks.", "new", "give"),
    ("Desk organizer", "academic", "Black mesh organizer with three compartments.", "good", "lend"),
    ("Highlighter set", "academic", "Six pastel highlighters in a pouch.", "good", "give"),
    (
        "Scientific calculator",
        "academic",
        "Casio scientific calculator, works great.",
        "good",
        "lend",
    ),
    ("USB-C phone charger", "tech", "20W USB-C wall charger with a 1 m cable.", "good", "lend"),
    ("HDMI cable", "tech", "2 m HDMI cable, gold connectors.", "good", "lend"),
    ("Wireless mouse", "tech", "Compact gray Bluetooth mouse.", "good", "lend"),
    ("Mechanical keyboard", "tech", "Full-size keyboard with brown switches.", "like_new", "lend"),
    ("27-inch monitor", "tech", "1080p monitor with an HDMI input and stand.", "good", "lend"),
    ("Laptop stand", "tech", "Foldable aluminum stand, adjustable height.", "like_new", "lend"),
    ("Power strip", "tech", "Six-outlet power strip with surge protection.", "good", "lend"),
    (
        "Bluetooth speaker",
        "events",
        "Portable waterproof speaker, about 10 hours battery.",
        "good",
        "lend",
    ),
    ("Over-ear headphones", "tech", "Black wired headphones with a padded band.", "good", "lend"),
    ("Webcam", "tech", "1080p USB webcam with a clip mount.", "like_new", "lend"),
    ("Desk lamp", "dorm", "White LED desk lamp with three brightness levels.", "good", "lend"),
    ("Electric kettle", "dorm", "1 L stainless kettle with auto shut-off.", "good", "lend"),
    ("Handheld vacuum", "dorm", "Cordless handheld vacuum with charger.", "good", "lend"),
    ("Box fan", "dorm", "20-inch box fan, three speeds.", "fair", "lend"),
    ("Mini fridge", "dorm", "Compact 3 cu ft fridge.", "good", "lend"),
    ("Cooking pot", "dorm", "Medium nonstick pot with a glass lid.", "good", "lend"),
    ("Frying pan", "dorm", "10-inch nonstick skillet.", "fair", "lend"),
    ("Clothes drying rack", "dorm", "Foldable rack, fits in a closet.", "good", "lend"),
    ("Throw blanket", "dorm", "Soft gray fleece blanket.", "good", "lend"),
    ("Iron", "dorm", "Steam iron with a ceramic plate.", "good", "lend"),
    ("Extension cord", "dorm", "3 m white extension cord.", "good", "lend"),
    ("Umbrella", "other", "Compact black travel umbrella.", "good", "lend"),
    ("Navy suit jacket", "clothing", "Slim-fit navy blazer, size M.", "like_new", "lend"),
    ("Black dress", "clothing", "Knee-length black cocktail dress, size S.", "like_new", "lend"),
    ("Rain jacket", "clothing", "Packable yellow rain jacket, size L.", "good", "lend"),
    ("Winter beanie", "clothing", "Knit gray beanie.", "good", "give"),
    ("Halloween costume", "events", "Astronaut costume with helmet, adult M.", "good", "lend"),
    ("Tennis racket", "sports", "Wilson racket with a carry bag.", "good", "lend"),
    ("Yoga mat", "sports", "Purple 6 mm yoga mat.", "good", "lend"),
    ("Bike helmet", "sports", "Black adjustable helmet, size M.", "good", "lend"),
    ("Bike pump", "sports", "Floor pump with a pressure gauge.", "good", "lend"),
    ("Camping tent", "sports", "Two-person dome tent with rain fly.", "good", "lend"),
    ("Sleeping bag", "sports", "Rated to 40°F, with a stuff sack.", "good", "lend"),
    ("Basketball", "sports", "Indoor/outdoor size 7 ball.", "fair", "lend"),
    ("Moving boxes", "moving", "Flat-packed medium cardboard boxes.", "good", "give"),
    ("Packing tape", "moving", "Two rolls of clear packing tape.", "new", "give"),
    ("Tool kit", "moving", "Small kit with screwdrivers, pliers, and a hammer.", "good", "lend"),
    ("Storage bin", "moving", "Clear 50 L plastic bin with lid.", "good", "lend"),
    ("Hand truck", "moving", "Folding dolly, holds about 70 kg.", "good", "lend"),
    ("String lights", "events", "Warm white fairy lights, 10 m.", "good", "lend"),
    ("Mini projector", "events", "Portable projector with HDMI input.", "good", "lend"),
    ("Board game (Catan)", "events", "Complete set, all pieces included.", "good", "lend"),
    ("Curry spice set", "consumables", "Cumin, turmeric, and garam masala jars.", "good", "give"),
    ("Olive oil", "consumables", "Half-full 500 ml bottle.", "good", "give"),
    ("Instant ramen (pack)", "consumables", "Five packs of instant noodles.", "new", "give"),
    ("Laundry detergent", "consumables", "Pods, about 20 left.", "good", "give"),
    ("Granola bars", "consumables", "Box of oat granola bars.", "new", "give"),
    ("Coffee beans", "consumables", "Unopened 12 oz bag, medium roast.", "new", "give"),
    ("Paper towels", "consumables", "Two rolls.", "new", "give"),
    ("Hair dryer", "dorm", "1800W dryer with a diffuser.", "good", "lend"),
    ("Full-length mirror", "dorm", "Over-the-door mirror.", "good", "lend"),
]
SENSITIVE: list[tuple[str, str, str]] = [
    ("Toothbrush", "consumables", "Personal hygiene item"),
    ("Opened lipstick", "consumables", "Opened cosmetics"),
    ("Silver necklace", "other", "Valuable"),
]


class MockVisionProvider:
    name = "mock"
    model = "mock-v1"

    async def detect(self, image_jpeg: bytes, filename: str) -> ProviderResult:
        start = time.monotonic()
        seed = int(hashlib.sha256(image_jpeg).hexdigest()[:16], 16)
        rng = random.Random(seed)
        picks = rng.sample(POOL, rng.randint(4, 9))
        raw = []
        for idx, (name, category, desc, cond, tx) in enumerate(picks):
            x, y = rng.uniform(0, 0.6), rng.uniform(0, 0.6)
            raw.append(
                {
                    "name": name,
                    "category": category,
                    "description": desc,
                    "quantity": 1 if rng.random() < 0.85 else rng.randint(2, 4),
                    "condition_guess": cond,
                    "confidence": round(rng.uniform(0.3, 0.98) if idx else 0.95, 2),
                    "bbox": [
                        round(x, 3),
                        round(y, 3),
                        round(rng.uniform(0.15, 0.4), 3),
                        round(rng.uniform(0.15, 0.4), 3),
                    ],
                    "suggested_share": True,
                    "sensitive_reason": None,
                    "suggested_transaction_type": tx,
                }
            )
        if rng.random() < 0.3:
            name, category, why = rng.choice(SENSITIVE)
            raw.append(
                {
                    "name": name,
                    "category": category,
                    "description": "",
                    "confidence": 0.8,
                    "suggested_share": False,
                    "sensitive_reason": why,
                    "suggested_transaction_type": "give",
                }
            )
        if settings.ai_mock_latency_ms > 0:
            await asyncio.sleep(settings.ai_mock_latency_ms / 1000)
        return ProviderResult(
            items=normalize_items(raw),
            latency_ms=int((time.monotonic() - start) * 1000),
            cost_usd=0.0,
            raw={"provider": "mock", "items": raw},
        )
