"""Walking-time estimates (PLAN.md §7.9)."""

from datetime import date, datetime
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo

from app.core.config import settings

EARTH_RADIUS_M = 6_371_000
WALK_M_PER_MIN = 80
DETOUR_FACTOR = 1.3


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


def walking_minutes(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    return max(1, round(haversine_m(lat1, lng1, lat2, lng2) * DETOUR_FACTOR / WALK_M_PER_MIN))


def distance_min(
    lat1: float | None, lng1: float | None, lat2: float | None, lng2: float | None
) -> int | None:
    """Walking minutes, or None when either point is unknown."""
    if lat1 is None or lng1 is None or lat2 is None or lng2 is None:
        return None
    return walking_minutes(lat1, lng1, lat2, lng2)


def campus_today() -> date:
    """Today's date in campus local time (CAMPUS_TZ)."""
    return datetime.now(ZoneInfo(settings.campus_tz)).date()
