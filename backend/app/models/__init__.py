"""SQLAlchemy models for every table in PLAN.md §6 (names from §7.1).

Enum-like columns are VARCHAR(20) validated in code (Pydantic Literals), never native PG enums.
Columns marked "C" in the plan are written only by Person C's code (app/ai, app/discovery).
"""

from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

EMBEDDING_DIM = 384


def _enum(**kw: Any) -> Mapped[str]:
    return mapped_column(String(20), **kw)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _updated() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def _ts_null() -> Mapped[datetime | None]:
    return mapped_column(DateTime(timezone=True), nullable=True)


def _jsonb_obj() -> Mapped[dict[str, Any]]:
    return mapped_column(JSONB, server_default=text("'{}'::jsonb"), default=dict, nullable=False)


class IdMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = _created()


# ---------------------------------------------------------------- users & communities
class User(IdMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)  # lowercase
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    walking_radius_min: Mapped[int] = mapped_column(Integer, server_default="10", default=10)
    onboarded: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    # Opt-in to mutual matching (docs/plans/mutual-matching.md): a pair needs both people on.
    match_suggestions: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    referred_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    seed_key: Mapped[str | None] = mapped_column(Text, unique=True)


class Community(IdMixin, Base):
    __tablename__ = "communities"

    kind: Mapped[str] = _enum(nullable=False)  # campus | dorm | group
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    emoji: Mapped[str | None] = mapped_column(Text)
    group_type: Mapped[str | None] = _enum()  # club | class | research | team | org | other
    is_private: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    join_code: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    seed_key: Mapped[str | None] = mapped_column(Text, unique=True)


class Membership(Base):
    __tablename__ = "memberships"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"), primary_key=True)
    role: Mapped[str] = _enum(server_default="member", default="member", nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (Index("ix_memberships_community_id", "community_id"),)


class Place(IdMixin, Base):
    __tablename__ = "places"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class Upload(IdMixin, Base):
    __tablename__ = "uploads"

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)


# ---------------------------------------------------------------- scans (C)
class Scan(IdMixin, Base):
    __tablename__ = "scans"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = _enum(nullable=False)  # processing | done | failed
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    finished_at: Mapped[datetime | None] = _ts_null()


class ScanImage(IdMixin, Base):
    __tablename__ = "scan_images"

    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), nullable=False, index=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = _enum(nullable=False)  # pending | processing | done | failed
    error: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    raw_response: Mapped[Any | None] = mapped_column(JSONB)


class ScanDetection(IdMixin, Base):
    __tablename__ = "scan_detections"

    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), nullable=False, index=True)
    scan_image_id: Mapped[int] = mapped_column(ForeignKey("scan_images.id"), nullable=False)
    image_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = _enum(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    condition_guess: Mapped[str | None] = _enum()
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bbox: Mapped[Any | None] = mapped_column(JSONB)
    suggested_share: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sensitive_reason: Mapped[str | None] = mapped_column(Text)
    suggested_transaction_type: Mapped[str] = _enum(nullable=False)
    status: Mapped[str] = _enum(nullable=False)  # pending | published | discarded
    published_item_id: Mapped[int | None] = mapped_column(Integer)
    edits: Mapped[Any | None] = mapped_column(JSONB)  # what the user changed: future training data


# ---------------------------------------------------------------- items
class Item(IdMixin, Base):
    __tablename__ = "items"

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = _enum(nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, server_default="1", default=1, nullable=False)
    condition: Mapped[str | None] = _enum()
    transaction_type: Mapped[str] = _enum(nullable=False)  # lend | give | exchange
    max_lend_days: Mapped[int | None] = mapped_column(Integer)
    available_from: Mapped[date | None] = mapped_column(Date)
    available_until: Mapped[date | None] = mapped_column(Date)
    visibility: Mapped[str] = _enum(nullable=False)  # campus | dorm | groups | private
    pings_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default="true", default=True, nullable=False
    )
    status: Mapped[str] = _enum(server_default="available", default="available", nullable=False)
    archived: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    pickup_place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"))
    pickup_note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = _enum(server_default="manual", default="manual", nullable=False)
    scan_detection_id: Mapped[int | None] = mapped_column(ForeignKey("scan_detections.id"))
    seed_key: Mapped[str | None] = mapped_column(Text, unique=True)
    # --- C ---
    embedding: Mapped[Any | None] = mapped_column(Vector(EMBEDDING_DIM))
    search_tsv: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(name, '')), 'A') || "
            "setweight(to_tsvector('english', coalesce(description, '')), 'B')",
            persisted=True,
        ),
    )
    updated_at: Mapped[datetime] = _updated()

    __table_args__ = (
        Index("ix_items_search_tsv", "search_tsv", postgresql_using="gin"),
        Index(
            "ix_items_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index(
            "ix_items_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_items_owner_id", "owner_id"),
        Index("ix_items_status_active", "status", postgresql_where=text("NOT archived")),
    )


class ItemImage(IdMixin, Base):
    __tablename__ = "item_images"

    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False, index=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ItemAudience(Base):
    __tablename__ = "item_audiences"

    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"), primary_key=True)

    __table_args__ = (Index("ix_item_audiences_community_id", "community_id"),)


# ---------------------------------------------------------------- requests
class ItemRequest(IdMixin, Base):
    """Table `requests` (named ItemRequest to avoid clashing with FastAPI's Request)."""

    __tablename__ = "requests"

    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    item_name: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = _enum()
    attributes: Mapped[dict[str, Any]] = _jsonb_obj()
    quantity: Mapped[int] = mapped_column(Integer, server_default="1", default=1, nullable=False)
    needed_from: Mapped[date | None] = mapped_column(Date)
    needed_until: Mapped[date | None] = mapped_column(Date)
    duration_days: Mapped[int | None] = mapped_column(Integer)
    transaction_type: Mapped[str | None] = _enum()
    visibility: Mapped[str] = _enum(nullable=False)
    status: Mapped[str] = _enum(server_default="open", default="open", nullable=False)
    pickup_place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"))
    seed_key: Mapped[str | None] = mapped_column(Text, unique=True)
    # --- C ---
    matching_status: Mapped[str] = _enum(
        server_default="pending", default="pending", nullable=False
    )
    ai_enriched: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    embedding: Mapped[Any | None] = mapped_column(Vector(EMBEDDING_DIM))
    search_tsv: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(title, '') || ' ' || "
            "coalesce(item_name, '') || ' ' || coalesce(raw_text, ''))",
            persisted=True,
        ),
    )
    updated_at: Mapped[datetime] = _updated()
    fulfilled_at: Mapped[datetime | None] = _ts_null()

    __table_args__ = (
        Index("ix_requests_search_tsv", "search_tsv", postgresql_using="gin"),
        Index(
            "ix_requests_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_requests_status", "status"),
    )


class RequestAudience(Base):
    __tablename__ = "request_audiences"

    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"), primary_key=True)

    __table_args__ = (Index("ix_request_audiences_community_id", "community_id"),)


class RequestMatch(Base):
    """Written by C's matching."""

    __tablename__ = "request_matches"

    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    notified: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    # a match on a private item; never shown to the requester
    anonymous: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    created_at: Mapped[datetime] = _created()

    __table_args__ = (Index("ix_request_matches_item_id", "item_id"),)


# ---------------------------------------------------------------- transactions & chat
class Conversation(IdMixin, Base):
    __tablename__ = "conversations"

    kind: Mapped[str] = _enum(nullable=False)  # direct | transaction
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", use_alter=True, name="fk_conversations_transaction_id"),
        unique=True,
    )
    last_message_at: Mapped[datetime | None] = _ts_null()


class Transaction(IdMixin, Base):
    __tablename__ = "transactions"

    kind: Mapped[str] = _enum(nullable=False)  # lend | give | exchange
    status: Mapped[str] = _enum(nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("requests.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    borrower_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    initiated_by: Mapped[str] = _enum(nullable=False)  # owner | borrower
    message: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    pickup_place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"))
    pickup_note: Mapped[str | None] = mapped_column(Text)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    accepted_at: Mapped[datetime | None] = _ts_null()
    handed_off_at: Mapped[datetime | None] = _ts_null()
    completed_at: Mapped[datetime | None] = _ts_null()
    declined_at: Mapped[datetime | None] = _ts_null()
    cancelled_at: Mapped[datetime | None] = _ts_null()
    updated_at: Mapped[datetime] = _updated()
    # Condition check (CONDITION_CHECK_ENABLED; app/services/condition.py). Photo maps are
    # {"front"|"back"|"marks": upload_id}; they are emptied when the exchange ends.
    condition_handoff_photos: Mapped[dict[str, int] | None] = mapped_column(JSONB)
    condition_handoff_confirmed_at: Mapped[datetime | None] = _ts_null()
    condition_return_photos: Mapped[dict[str, int] | None] = mapped_column(JSONB)
    condition_status: Mapped[str | None] = mapped_column(Text)  # checking | done | failed
    condition_result: Mapped[str | None] = mapped_column(Text)  # no_changes | possible_changes
    condition_note: Mapped[str | None] = mapped_column(Text)
    condition_sample: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    condition_checked_at: Mapped[datetime | None] = _ts_null()
    condition_photos_deleted_at: Mapped[datetime | None] = _ts_null()
    # Handoff coordinator (HANDOFF_COORDINATOR_ENABLED; app/services/handoff.py).
    pickup_at: Mapped[datetime | None] = _ts_null()  # the agreed handoff time
    handoff_suggestion: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # the current proposal

    __table_args__ = (
        Index("ix_transactions_owner_id", "owner_id"),
        Index("ix_transactions_borrower_id", "borrower_id"),
        Index("ix_transactions_item_id", "item_id"),
        Index("ix_transactions_request_id", "request_id"),
    )


class TransactionEvent(IdMixin, Base):
    __tablename__ = "transaction_events"

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id"), nullable=False, index=True
    )
    status: Mapped[str] = _enum(nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"

    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    last_read_message_id: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (Index("ix_conversation_participants_user_id", "user_id"),)


class Message(IdMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = _enum(nullable=False)  # text | system
    body: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (Index("ix_messages_conversation_id_id", "conversation_id", "id"),)


class Review(IdMixin, Base):
    __tablename__ = "reviews"

    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1–5
    body: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("transaction_id", "reviewer_id", name="uq_reviews_tx_reviewer"),
    )


# ---------------------------------------------------------------- reputation & notifications
class PointsLedger(IdMixin, Base):
    __tablename__ = "points_ledger"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    ref_type: Mapped[str | None] = mapped_column(Text)
    ref_id: Mapped[int | None] = mapped_column(Integer)


class UserBadge(Base):
    __tablename__ = "user_badges"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    earned_at: Mapped[datetime] = _created()


class Notification(IdMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = _enum(nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    data: Mapped[dict[str, Any]] = _jsonb_obj()
    read_at: Mapped[datetime | None] = _ts_null()

    __table_args__ = (Index("ix_notifications_user_id_read_at", "user_id", "read_at"),)


# ---------------------------------------------------------------- logging (future ML)
class SearchLog(IdMixin, Base):
    __tablename__ = "search_logs"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    raw_query: Mapped[str] = mapped_column(Text, nullable=False)
    parsed: Mapped[Any] = mapped_column(JSONB, nullable=False)
    filters: Mapped[Any] = mapped_column(JSONB, nullable=False)
    result_item_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)


class Event(IdMixin, Base):
    __tablename__ = "events"

    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = _jsonb_obj()


class AICache(Base):
    __tablename__ = "ai_cache"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created()


__all__ = [
    "AICache",
    "Base",
    "Community",
    "Conversation",
    "ConversationParticipant",
    "Event",
    "Item",
    "ItemAudience",
    "ItemImage",
    "ItemRequest",
    "Membership",
    "Message",
    "Notification",
    "Place",
    "PointsLedger",
    "RequestAudience",
    "RequestMatch",
    "Review",
    "Scan",
    "ScanDetection",
    "ScanImage",
    "SearchLog",
    "Transaction",
    "TransactionEvent",
    "Upload",
    "User",
    "UserBadge",
]
