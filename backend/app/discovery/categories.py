"""Nearest-category fallback by embedding (used when no keyword matches)."""

from functools import lru_cache

from app.discovery.embeddings import embed_passages, embed_query

DESCRIPTIONS = {
    "academic": "school supplies, textbooks, calculators, notebooks, lab equipment, stationery",
    "tech": "electronics, chargers, cables, adapters, computer accessories, gadgets, cameras",
    "clothing": "clothes, suits, dresses, jackets, costumes, shoes, formalwear, accessories",
    "dorm": "dorm and kitchen essentials, appliances, cookware, cleaning, furniture, bedding",
    "consumables": "food, spices, snacks, drinks, toiletries, detergent, things that get used up",
    "sports": "sports equipment, bikes, outdoor and camping gear, fitness, games and balls",
    "moving": "moving supplies, boxes, carts, tools, storage, hardware",
    "events": "party and event supplies, speakers, projectors, decorations, music instruments",
    "services": "help from a person: tutoring, lessons, repairs, rides, photography",
    "other": "miscellaneous things",
}


@lru_cache(maxsize=1)
def _vectors() -> tuple[list[str], list[list[float]]]:
    keys = list(DESCRIPTIONS)
    return keys, embed_passages([DESCRIPTIONS[k] for k in keys])


def nearest_category(text: str) -> str | None:
    keys, vecs = _vectors()
    q = embed_query(text)
    scores = [sum(a * b for a, b in zip(q, v, strict=True)) for v in vecs]
    best = max(range(len(keys)), key=lambda i: scores[i])
    other = scores[keys.index("other")]
    # Only trust a clear winner; gibberish is about as close to "other" as to anything.
    if keys[best] == "other" or scores[best] - other < 0.04:
        return None
    return keys[best]
