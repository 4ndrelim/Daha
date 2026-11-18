"""Discovery weights and thresholds (PLAN.md C2/C3). Tune here, log changes in docs/decisions.md."""

# --- search score = Σ weight·signal, then × availability factor
SEARCH_WEIGHTS = {"semantic": 0.55, "keyword": 0.25, "proximity": 0.15, "freshness": 0.05}
NEAR_ME_PROXIMITY_WEIGHT = 0.35  # replaces proximity when the query says "near me"; renormalized
PARSED_CATEGORY_BOOST = 0.12  # parsed (not explicit) category is a soft boost, never a hard filter
PARSED_TYPE_BOOST = 0.05
AVAILABILITY_FACTOR = {"available": 1.0, "reserved": 0.5, "borrowed": 0.3}
PROXIMITY_DECAY_MIN = 12.0  # e^(-walk/12)
FRESHNESS_DECAY_DAYS = 30.0
UNKNOWN_DISTANCE_PROXIMITY = 0.2

# A candidate with no keyword overlap is shown only if it is semantically close enough:
# ≥ the absolute floor AND within the margin of the best candidate. bge-small packs relevant
# items (0.67–0.82) close to noise (0.60–0.70), so a relative floor works better than a fixed one.
SEMANTIC_FLOOR = {"fastembed": 0.62, "hash": 0.30}
SEMANTIC_MARGIN = {"fastembed": 0.07, "hash": 0.25}

CANDIDATES_VECTOR = 200
CANDIDATES_FTS = 100
CANDIDATES_TRGM = 100
TRGM_MIN = 0.6  # word_similarity; typo tolerance, not fuzzy topic match
BROWSE_POOL = 400

# --- request ↔ item matching (C3)
MATCH_WEIGHTS = {"semantic": 0.65, "keyword": 0.15, "proximity": 0.20}
# Relevance = (0.65·semantic + 0.15·keyword) / 0.80 must clear this before proximity counts,
# so a same-dorm item never "matches" just for being close. Calibrated on seed (see decisions).
MATCH_MIN_RELEVANCE = {"fastembed": 0.60, "hash": 0.35}
MATCH_TOP_N = 10  # shown in GET /requests/{id}/matches
MATCH_STORE_N = 50  # stored per request, so more owners see it in "You could help"
MATCH_PER_OWNER = 3
MATCH_NOTIFY_OWNERS = 5
PRIVATE_PINGS_PER_DAY = 3
FULFILLABLE_DAYS = 21
FULFILLABLE_MAX = 20

CATEGORY_LABELS = {
    "academic": "Academic",
    "tech": "Tech",
    "clothing": "Clothing",
    "dorm": "Dorm essentials",
    "consumables": "Consumables",
    "sports": "Sports & outdoors",
    "moving": "Moving",
    "events": "Events",
    "services": "Services",
    "other": "Other",
}
