"""Value exchange (VALUE_EXCHANGE_ENABLED, which also needs ITEM_VALUE_ENABLED). Off by default.

Shows the estimated value of goods and of what people exchanged. **No money moves in DAHA**:
every number is an estimate in whole US dollars, and the wording always says "about".

- Starting estimate for the Value field: a cached store price (the C6 lookup, only when the real
  provider already fetched it, so it costs nothing), else the scan's AI estimate, else empty.
  Never invented.
- Snapshot: a transaction stores the item's value when it's created and again when it completes
  (edits are locked in between). Swaps also store what the borrower gave (`swap_value_usd`).
- Totals: "Value shared" / "Value received" per person and "<dorm> shared about $X this month",
  counting only completed exchanges between two different people.
- Value bonus: 1 point per $20 (1 per $10 at $100+, "High value"), at most 30 per exchange and
  100 per person per 7 days. None for self-exchanges, flagged items, or a pair that already
  completed an exchange in the last 7 days.
- High value lends need the 3-photo condition check confirmed before hand-off (when the
  condition check is on).
- A value far above the typical price is flagged for review: it shows, but earns no bonus.
"""

import logging
import statistics
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import settings
from app.core.geo import campus_today
from app.models import (
    Event,
    Item,
    Membership,
    PointsLedger,
    Transaction,
)
from app.services import points

log = logging.getLogger(__name__)

MAX_VALUE_USD = 10000
HIGH_VALUE_USD = 100
USD_PER_POINT = 20
USD_PER_POINT_HIGH = 10
BONUS_CAP_PER_EXCHANGE = 30
BONUS_CAP_PER_WEEK = 100
REPEAT_WINDOW = timedelta(days=7)
BONUS_REASON = "value_bonus"
FLAG_EVENT = "value_flagged"
ACTIVE = ("requested", "offered", "accepted", "handed_off")
# A value is "far above typical" when it is over 3x the typical price and at least $50 more.
FLAG_RATIO = 3
FLAG_MIN_GAP_USD = 50
# With no typical price to compare to, a coarse per-category ceiling for one everyday item.
CATEGORY_CEILING_USD = {
    "academic": 1000,
    "tech": 4000,
    "clothing": 1500,
    "dorm": 2000,
    "consumables": 200,
    "sports": 3000,
    "moving": 1000,
    "events": 3000,
    "services": 500,
    "other": 3000,
}


def enabled() -> bool:
    return settings.item_value_enabled and settings.value_exchange_enabled


def _now() -> datetime:
    return datetime.now(UTC)


def is_high_value(value: int | None) -> bool:
    return value is not None and value >= HIGH_VALUE_USD


# ---------------------------------------------------------------- starting estimate
def cached_store_price(db: Session, name: str) -> int | None:
    """The median USD 'buy' price from an already-cached real store lookup, else None.

    Never makes a web call. Mock store results are made up, so they never count.
    """
    if settings.commercial_provider.strip().lower() != "exa":
        return None
    from app.discovery import commercial  # local: commercial imports a lot

    words, _ = commercial.search_words(name)
    if len(words) < 2:
        return None
    near = commercial._geo(
        settings.commercial_default_label,
        "campus",
        settings.commercial_default_lat,
        settings.commercial_default_lng,
    )
    hit = commercial.cache_get(db, commercial.cache_key("exa", words, near))
    if not hit:
        return None
    prices = [
        o.price
        for o in hit[0]
        if o.offer_type == "buy"
        and o.price is not None
        and (o.currency or "USD").upper() == "USD"
        and o.price_unit in (None, "each")
    ]
    if not prices:
        return None
    return max(0, min(MAX_VALUE_USD, round(statistics.median(prices))))


def suggest(db: Session, name: str, ai_estimate: int | None = None) -> schemas.ValueEstimate:
    """Store price first, else the AI's estimate, else nothing."""
    if not enabled():
        return schemas.ValueEstimate(value_usd=None, source=None)
    store = cached_store_price(db, name) if name.strip() else None
    if store is not None:
        return schemas.ValueEstimate(value_usd=store, source="store")
    if ai_estimate is not None:
        return schemas.ValueEstimate(value_usd=ai_estimate, source="ai")
    return schemas.ValueEstimate(value_usd=None, source=None)


# ---------------------------------------------------------------- anti-gaming on items
def value_locked(db: Session, item: Item) -> bool:
    """Someone has asked for this item and the exchange isn't over: the value can't change."""
    if not enabled() or item.id is None:
        return False
    return bool(
        db.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.item_id == item.id, Transaction.status.in_(ACTIVE))
        )
    )


def typical_price(db: Session, item: Item) -> int | None:
    """A cached real store price. (The scan's estimate isn't used: the owner can edit it.)"""
    return cached_store_price(db, item.name)


def far_above_typical(value: int, typical: int | None, category: str) -> bool:
    if typical is not None:
        return value > typical * FLAG_RATIO and value - typical >= FLAG_MIN_GAP_USD
    return value > CATEGORY_CEILING_USD.get(category, CATEGORY_CEILING_USD["other"])


def check_flag(db: Session, item: Item) -> None:
    """Flag (or clear) a value that looks far above the typical price. Call after a change."""
    if not enabled():
        return
    if item.value_usd is None:
        item.value_flagged_at = None
        return
    typical = typical_price(db, item)
    if far_above_typical(item.value_usd, typical, item.category):
        if item.value_flagged_at is None:
            item.value_flagged_at = _now()
            db.add(
                Event(
                    user_id=item.owner_id,
                    type=FLAG_EVENT,
                    payload={"item_id": item.id, "value_usd": item.value_usd, "typical": typical},
                )
            )
            log.info("value: item %s flagged for review", item.id)
    else:
        item.value_flagged_at = None


def guard_value_edit(db: Session, item: Item, new_value: int | None) -> None:
    if new_value != item.value_usd and value_locked(db, item):
        raise HTTPException(
            409, "The value is locked while someone has asked for this item. Try after it's done."
        )


# ---------------------------------------------------------------- transactions
def snapshot(tx: Transaction, item: Item) -> None:
    if enabled():
        tx.value_usd = item.value_usd


def needs_condition_check(tx: Transaction) -> bool:
    """A High value lend can't be handed off until the borrower confirms the 3 handoff photos."""
    return (
        enabled()
        and settings.condition_check_enabled
        and tx.kind == "lend"
        and tx.status in ("requested", "offered", "accepted")
        and is_high_value(tx.value_usd)
        and tx.condition_handoff_confirmed_at is None
    )


def set_swap_value(tx: Transaction, user_id: int, value: int | None) -> None:
    if not enabled():
        raise HTTPException(404, "Not found")
    if tx.kind != "exchange":
        raise HTTPException(409, "Only swaps have a second item")
    if tx.borrower_id != user_id:
        raise HTTPException(403, "Only the person swapping their own thing in can set this")
    if tx.status not in ACTIVE:
        raise HTTPException(409, "This swap is finished, so its values are locked")
    tx.swap_value_usd = value


def _week_bonus(db: Session, user_id: int) -> int:
    since = _now() - REPEAT_WINDOW
    total = db.scalar(
        select(func.coalesce(func.sum(PointsLedger.delta), 0)).where(
            PointsLedger.user_id == user_id,
            PointsLedger.reason == BONUS_REASON,
            PointsLedger.created_at >= since,
        )
    )
    return int(total or 0)


def _repeat_pair(db: Session, tx: Transaction) -> bool:
    since = _now() - REPEAT_WINDOW
    a, b = tx.owner_id, tx.borrower_id
    return bool(
        db.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(
                Transaction.id != tx.id,
                Transaction.status == "completed",
                Transaction.completed_at >= since,
                or_(
                    and_(Transaction.owner_id == a, Transaction.borrower_id == b),
                    and_(Transaction.owner_id == b, Transaction.borrower_id == a),
                ),
            )
        )
    )


def bonus_points(value: int | None) -> int:
    if not value or value <= 0:
        return 0
    per = USD_PER_POINT_HIGH if is_high_value(value) else USD_PER_POINT
    return min(BONUS_CAP_PER_EXCHANGE, value // per)


def no_bonus_reason(db: Session, tx: Transaction, item: Item) -> str | None:
    if tx.owner_id == tx.borrower_id:
        return "self"
    if not tx.value_usd:
        return "no_value"
    if item.value_flagged_at is not None:
        return "under_review"
    if _repeat_pair(db, tx):
        return "repeat"
    return None


def on_complete(db: Session, tx: Transaction, item: Item) -> None:
    """Freeze the value and award the value bonus. Called by transactions._complete."""
    if not enabled():
        return
    snapshot(tx, item)
    if no_bonus_reason(db, tx, item) is not None:
        return
    base = bonus_points(tx.value_usd)
    receivers = [tx.owner_id, tx.borrower_id] if tx.kind == "exchange" else [tx.owner_id]
    for user_id in receivers:
        give = min(base, max(0, BONUS_CAP_PER_WEEK - _week_bonus(db, user_id)))
        if give > 0:
            points.award(db, user_id, give, BONUS_REASON, "transaction", tx.id)


def _bonus_by_tx(db: Session, tx_ids: list[int], user_id: int) -> dict[int, int]:
    if not tx_ids:
        return {}
    rows = db.execute(
        select(PointsLedger.ref_id, func.sum(PointsLedger.delta))
        .where(
            PointsLedger.user_id == user_id,
            PointsLedger.reason == BONUS_REASON,
            PointsLedger.ref_type == "transaction",
            PointsLedger.ref_id.in_(tx_ids),
        )
        .group_by(PointsLedger.ref_id)
    ).all()
    return {int(r): int(v) for r, v in rows}


def tx_values_out(
    db: Session, txs: list[Transaction], items: dict[int, Item], user_id: int
) -> dict[int, schemas.TxValue | None]:
    if not enabled():
        return {t.id: None for t in txs}
    bonus = _bonus_by_tx(db, [t.id for t in txs if t.status == "completed"], user_id)
    out: dict[int, schemas.TxValue | None] = {}
    for t in txs:
        item = items.get(t.item_id)
        value = t.value_usd if t.status == "completed" else (item.value_usd if item else None)
        swap = t.swap_value_usd if t.kind == "exchange" else None
        out[t.id] = schemas.TxValue(
            value_usd=value,
            swap_value_usd=swap,
            difference_usd=abs(value - swap) if value is not None and swap is not None else None,
            high_value=is_high_value(value),
            needs_condition_check=needs_condition_check(t),
            bonus_points=bonus.get(t.id, 0) if t.status == "completed" else None,
            no_bonus_reason=(
                no_bonus_reason(db, t, item) if t.status == "completed" and item else None
            ),
            can_set_swap_value=t.kind == "exchange"
            and t.borrower_id == user_id
            and t.status in ACTIVE,
        )
    return out


# ---------------------------------------------------------------- totals
def _completed_between_people():
    return and_(Transaction.status == "completed", Transaction.owner_id != Transaction.borrower_id)


def totals(db: Session, user_id: int) -> tuple[int, int]:
    """(value shared, value received) in whole dollars, from completed exchanges only."""
    done = _completed_between_people()

    def total(col, who):
        return int(
            db.scalar(select(func.coalesce(func.sum(col), 0)).where(done, who == user_id)) or 0
        )

    swap_given = db.scalar(
        select(func.coalesce(func.sum(Transaction.swap_value_usd), 0)).where(
            done, Transaction.kind == "exchange", Transaction.borrower_id == user_id
        )
    )
    swap_got = db.scalar(
        select(func.coalesce(func.sum(Transaction.swap_value_usd), 0)).where(
            done, Transaction.kind == "exchange", Transaction.owner_id == user_id
        )
    )
    shared = total(Transaction.value_usd, Transaction.owner_id) + int(swap_given or 0)
    received = total(Transaction.value_usd, Transaction.borrower_id) + int(swap_got or 0)
    return shared, received


def dorm_shared_this_month(db: Session, dorm_id: int | None) -> int | None:
    """What people in this dorm shared (as owners) this campus calendar month."""
    if not enabled() or dorm_id is None:
        return None
    tz = ZoneInfo(settings.campus_tz)
    start = datetime.combine(campus_today().replace(day=1), time.min, tzinfo=tz)
    in_dorm = select(Membership.user_id).where(Membership.community_id == dorm_id)
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.value_usd), 0)).where(
            _completed_between_people(),
            Transaction.completed_at >= start,
            Transaction.owner_id.in_(in_dorm),
        )
    )
    swaps = db.scalar(
        select(func.coalesce(func.sum(Transaction.swap_value_usd), 0)).where(
            _completed_between_people(),
            Transaction.kind == "exchange",
            Transaction.completed_at >= start,
            Transaction.borrower_id.in_(in_dorm),
        )
    )
    return int(total or 0) + int(swaps or 0)
