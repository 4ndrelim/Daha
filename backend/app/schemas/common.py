"""Primitives and enums shared by every schema module (PLAN.md §7.2)."""

from datetime import UTC, datetime
from typing import Annotated, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer

T = TypeVar("T")

ID = int


def _iso_z(dt: datetime) -> str:
    """UTC ISO-8601 with a trailing Z, e.g. 2026-11-16T21:58:00Z."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


ISODateTime = Annotated[datetime, PlainSerializer(_iso_z, return_type=str, when_used="json")]

Category = Literal[
    "academic",
    "tech",
    "clothing",
    "dorm",
    "consumables",
    "sports",
    "moving",
    "events",
    "services",
    "other",
]
Condition = Literal["new", "like_new", "good", "fair", "worn"]
TransactionType = Literal["lend", "give", "exchange"]
Visibility = Literal["campus", "dorm", "groups", "private"]
ItemStatus = Literal["available", "reserved", "borrowed", "unavailable"]
RequestStatus = Literal["open", "in_progress", "fulfilled", "cancelled", "expired"]
TxStatus = Literal[
    "requested", "offered", "accepted", "handed_off", "completed", "declined", "cancelled"
]
TxAction = Literal["accept", "decline", "cancel", "hand_off", "mark_returned"]
CommunityKind = Literal["campus", "dorm", "group"]
GroupType = Literal["club", "class", "research", "team", "org", "other"]
NotificationType = Literal[
    "match", "offer", "borrow_request", "tx_update", "review", "badge", "system", "private_match"
]
ItemSource = Literal["manual", "scan", "offer"]


class Schema(BaseModel):
    """Base for every API model. Responses always include every field (null, never missing)."""

    model_config = ConfigDict(from_attributes=True)


class Page[T](Schema):
    items: list[T]
    next_offset: int | None
