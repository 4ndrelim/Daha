"""Shared scoring helpers for search, matching, and feeds."""

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.core.geo import distance_min
from app.discovery.config import (
    FRESHNESS_DECAY_DAYS,
    PROXIMITY_DECAY_MIN,
    UNKNOWN_DISTANCE_PROXIMITY,
)
from app.models import Community, Membership, Place
from app.services.viewer import ViewerContext

_WORD = re.compile(r"[a-z0-9]+")


def tsquery_or(text: str):
    """OR of the words, so 'formal clothes interview' matches items with any of them."""
    words = list(dict.fromkeys(w for w in _WORD.findall((text or "").lower()) if len(w) > 1))[:12]
    if not words:
        return None
    return func.to_tsquery("english", literal(" | ".join(words)))


@dataclass
class Loc:
    dorm_id: int | None
    distance: int | None


def locations(
    db: Session, owner_ids: set[int], place_ids: set[int | None]
) -> tuple[dict[int, Community], dict[int, Place]]:
    dorms: dict[int, Community] = {}
    if owner_ids:
        for uid, dorm in db.execute(
            select(Membership.user_id, Community)
            .join(Community, Community.id == Membership.community_id)
            .where(Membership.user_id.in_(owner_ids), Community.kind == "dorm")
        ).all():
            dorms[uid] = dorm
    ids = {p for p in place_ids if p is not None}
    places = {p.id: p for p in db.scalars(select(Place).where(Place.id.in_(ids)))} if ids else {}
    return dorms, places


def loc_for(viewer: ViewerContext, owner_id: int, place_id: int | None, dorms, places) -> Loc:
    dorm = dorms.get(owner_id)
    spot = places.get(place_id) if place_id else None
    spot = spot or dorm
    dist = distance_min(viewer.lat, viewer.lng, spot.lat, spot.lng) if spot else None
    return Loc(dorm_id=dorm.id if dorm else None, distance=dist)


def proximity(viewer: ViewerContext, loc: Loc) -> float:
    if viewer.dorm_id is not None and loc.dorm_id == viewer.dorm_id:
        return 1.0
    if loc.distance is None:
        return UNKNOWN_DISTANCE_PROXIMITY
    return math.exp(-loc.distance / PROXIMITY_DECAY_MIN)


def freshness(created_at: datetime) -> float:
    age = (datetime.now(UTC) - created_at).total_seconds() / 86400
    return math.exp(-max(age, 0) / FRESHNESS_DECAY_DAYS)


STATUS_LABEL = {"available": "Available", "reserved": "Reserved", "borrowed": "Borrowed now"}


def reason(viewer: ViewerContext, loc: Loc, status: str | None = None) -> str:
    parts = []
    if viewer.dorm_id is not None and loc.dorm_id == viewer.dorm_id:
        parts.append("Same dorm")
    if loc.distance is not None:
        parts.append(f"{loc.distance} min walk")
    if status:
        parts.append(STATUS_LABEL.get(status, status.title()))
    return " · ".join(parts) or "On campus"
