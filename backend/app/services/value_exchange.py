"""Value exchange (VALUE_EXCHANGE_ENABLED, which also needs ITEM_VALUE_ENABLED). Off by default.

Shows the estimated value of goods and of what people exchanged. **No money moves in DAHA**:
every number is an estimate in whole US dollars, and the wording always says "about".

- Starting estimate for the Value field: a cached store price (the C6 lookup, only when the real
  provider already fetched it, so it costs nothing), else the scan's AI estimate, else empty.
  Never invented.
- Snapshot: when an exchange completes, the transaction stores the item's value.
- Totals: "Value shared" per person and "<dorm> shared about $X this month", counting only
  completed exchanges between two different people.
- Karma bonus: 1 point per $20 of estimated value, at most 30 per exchange, none for an exchange
  with yourself. Lends and gives: the owner gets it; swaps: both people.

Ideas for later (spending karma, a photo rule for pricey items, more anti-gaming) are in
docs/proposals/value-next.md and are not built.
"""

import statistics
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import settings
from app.core.geo import campus_today
from app.models import Item, Membership, PointsLedger, Transaction
from app.services import points

MAX_VALUE_USD = 10000
USD_PER_POINT = 20
BONUS_CAP_PER_EXCHANGE = 30
BONUS_REASON = "value_bonus"


def enabled() -> bool:
    return settings.item_value_enabled and settings.value_exchange_enabled


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


# ---------------------------------------------------------------- completion
def bonus_points(value: int | None) -> int:
    if not value or value <= 0:
        return 0
    return min(BONUS_CAP_PER_EXCHANGE, value // USD_PER_POINT)


def no_bonus_reason(tx: Transaction) -> str | None:
    if tx.owner_id == tx.borrower_id:
        return "self"
    if not tx.value_usd:
        return "no_value"
    return None


def on_complete(db: Session, tx: Transaction, item: Item) -> None:
    """Store the item's value on the transaction and award the karma bonus."""
    if not enabled():
        return
    tx.value_usd = item.value_usd
    if no_bonus_reason(tx) is not None:
        return
    give = bonus_points(tx.value_usd)
    receivers = [tx.owner_id, tx.borrower_id] if tx.kind == "exchange" else [tx.owner_id]
    for user_id in receivers:
        if give > 0:
            points.award(db, user_id, give, BONUS_REASON, "transaction", tx.id)


def tx_values_out(
    db: Session, txs: list[Transaction], user_id: int
) -> dict[int, schemas.TxValue | None]:
    """Only completed exchanges get a value receipt."""
    done = [t for t in txs if t.status == "completed"]
    if not enabled() or not done:
        return {t.id: None for t in txs}
    rows = db.execute(
        select(PointsLedger.ref_id, func.sum(PointsLedger.delta))
        .where(
            PointsLedger.user_id == user_id,
            PointsLedger.reason == BONUS_REASON,
            PointsLedger.ref_type == "transaction",
            PointsLedger.ref_id.in_([t.id for t in done]),
        )
        .group_by(PointsLedger.ref_id)
    ).all()
    bonus = {int(r): int(v) for r, v in rows}
    out: dict[int, schemas.TxValue | None] = {t.id: None for t in txs}
    for t in done:
        out[t.id] = schemas.TxValue(
            value_usd=t.value_usd,
            bonus_points=bonus.get(t.id, 0),
            no_bonus_reason=no_bonus_reason(t),
        )
    return out


# ---------------------------------------------------------------- totals
def _completed_between_people():
    return and_(Transaction.status == "completed", Transaction.owner_id != Transaction.borrower_id)


def value_shared(db: Session, user_id: int) -> int:
    """What this person shared (as the owner) in completed exchanges, in whole dollars."""
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.value_usd), 0)).where(
            _completed_between_people(), Transaction.owner_id == user_id
        )
    )
    return int(total or 0)


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
    return int(total or 0)
