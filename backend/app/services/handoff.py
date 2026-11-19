"""Handoff coordinator (HANDOFF_COORDINATOR_ENABLED, off by default).

In a transaction's chat, either person can tap "Suggest a time & place". Then:
1. An agent (app/ai/handoff.py) reads the last few messages of THAT chat and proposes a time and
   an exchange spot. It runs only on that tap, never by itself: at most 3 runs per transaction
   per 24 h, and all paid runs stop at HANDOFF_BUDGET_USD.
2. The person who asked sees a draft only they can see: "Send" it, or "Change" the time or place.
3. The other person gets it in the chat and confirms with one tap (or changes it and sends it
   back). Accepting sets the transaction's pickup place and `pickup_at`, adds a timeline row and
   posts a system message.

If the agent can't produce a usable answer, the draft says "Couldn't find a good time — suggest
one yourself" and the person can pick a time and place by hand.

The current proposal lives in `transactions.handoff_suggestion` (JSONB). Runs are counted from
`handoff_coordinator_run` events, which hold counts and costs only, never chat text.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas
from app.ai import handoff as ai_handoff
from app.ai.providers.base import ProviderError
from app.core.config import settings
from app.core.db import SessionLocal
from app.models import Community, Event, Item, Membership, Message, Place, Transaction, User
from app.services import serializers
from app.services.viewer import ViewerContext

log = logging.getLogger(__name__)

EVENT_TYPE = "handoff_coordinator_run"
RUNS_PER_DAY = 3
OPEN = ("requested", "offered", "accepted")  # before the item changes hands
THINKING_TIMEOUT = timedelta(minutes=4)  # a run that never came back counts as failed
MANUAL_MAX_DAYS = 30
FALLBACK = "Couldn't find a good time — suggest one yourself"
PAUSED = "Suggestions are paused for now — suggest a time yourself"


def _now() -> datetime:
    return datetime.now(UTC)


def enabled() -> bool:
    return settings.handoff_coordinator_enabled


def require_enabled() -> None:
    if not enabled():
        raise HTTPException(404, "Not found")


# ---------------------------------------------------------------- limits
def runs_today(db: Session, transaction_id: int) -> int:
    since = _now() - timedelta(hours=24)
    return (
        db.scalar(
            select(func.count())
            .select_from(Event)
            .where(
                Event.type == EVENT_TYPE,
                Event.created_at >= since,
                Event.payload["transaction_id"].as_integer() == transaction_id,
            )
        )
        or 0
    )


def spent(db: Session) -> float:
    total = db.scalar(
        select(func.coalesce(func.sum(Event.payload["cost_usd"].as_float()), 0.0)).where(
            Event.type == EVENT_TYPE
        )
    )
    return float(total or 0.0)


# ---------------------------------------------------------------- the stored proposal
def _state(tx: Transaction) -> dict | None:
    """The current proposal, with a run that never came back turned into a failure."""
    state = tx.handoff_suggestion
    if not state:
        return None
    if state.get("status") == "thinking":
        started = datetime.fromisoformat(state["updated_at"])
        if _now() - started > THINKING_TIMEOUT:
            return {**state, "status": "failed", "message": FALLBACK}
    return state


def _set(tx: Transaction, **fields) -> None:
    tx.handoff_suggestion = {**fields, "updated_at": _now().isoformat()}  # a new dict each time


def _when(start: datetime) -> str:
    """'Thu, Nov 19 at 4:30 PM' in campus time."""
    local = start.astimezone(ZoneInfo(settings.campus_tz))
    return f"{local:%a, %b} {local.day} at {local.hour % 12 or 12}:{local:%M %p}"


def _first(user: User | None) -> str:
    return (user.name.split()[0] if user and user.name else "Someone")[:40]


def can_suggest(tx: Transaction, state: dict | None) -> bool:
    return tx.status in OPEN and (state or {}).get("status") != "thinking"


def handoff_out(db: Session, tx: Transaction, viewer: ViewerContext) -> schemas.HandoffState | None:
    if not enabled() or tx.status not in OPEN:
        return None
    state = _state(tx)
    left = max(RUNS_PER_DAY - runs_today(db, tx.id), 0)
    suggestion = None
    if state:
        mine = state.get("proposed_by") == viewer.user_id
        status = state.get("status")
        if mine or status in ("sent", "accepted"):  # a draft is private to the person who asked
            place = db.get(Place, state["place_id"]) if state.get("place_id") else None
            start = state.get("start_time")
            suggestion = schemas.HandoffSuggestion(
                status=status,
                mine=mine,
                start_time=datetime.fromisoformat(start) if start else None,
                place=serializers.place_out(place, viewer) if place else None,
                reason=state.get("reason"),
                confidence=state.get("confidence"),
                sample=bool(state.get("sample")),
                message=state.get("message"),
                can_send=mine and status == "draft",
                can_accept=(not mine) and status == "sent",
            )
    return schemas.HandoffState(
        can_suggest=can_suggest(tx, state) and left > 0,
        runs_left_today=left,
        suggestion=suggestion,
    )


# ---------------------------------------------------------------- 1. ask the agent
def start_suggest(db: Session, tx: Transaction, user: User, background: BackgroundTasks) -> None:
    """The tap on "Suggest a time & place". Idempotent while a run is in flight."""
    if tx.status not in OPEN:
        raise HTTPException(409, "This is already handed over")
    state = _state(tx)
    if state and state.get("status") == "thinking":
        return
    if runs_today(db, tx.id) >= RUNS_PER_DAY:
        raise HTTPException(
            429, "That's 3 suggestions for this exchange today — pick a time yourself"
        )
    if (
        ai_handoff.is_paid()
        and spent(db) + settings.handoff_est_cost_per_run > settings.handoff_budget_usd
    ):
        _set(tx, status="failed", proposed_by=user.id, message=PAUSED)
        return
    _set(tx, status="thinking", proposed_by=user.id)
    db.flush()
    background.add_task(run_suggest, tx.id)


def gather_input(db: Session, tx: Transaction, now: datetime) -> dict:
    """Exactly what the agent gets for this transaction, and nothing else."""
    rows = db.execute(
        select(Message.sender_id, Message.body)
        .where(
            Message.conversation_id == tx.conversation_id,
            Message.kind == "text",
            Message.sender_id.in_((tx.owner_id, tx.borrower_id)),
        )
        .order_by(Message.id.desc())
        .limit(ai_handoff.MAX_MESSAGES)
    ).all()
    role = {tx.owner_id: "lender", tx.borrower_id: "borrower"}
    people = {u.id: u for u in db.scalars(select(User).where(User.id.in_(role)))}
    dorms = dict(
        db.execute(
            select(Membership.user_id, Community.name)
            .join(Community, Community.id == Membership.community_id)
            .where(Membership.user_id.in_(role), Community.kind == "dorm")
        ).all()
    )
    places = db.execute(select(Place.id, Place.name).order_by(Place.id)).all()
    item = db.get(Item, tx.item_id)
    return ai_handoff.build_input(
        [(role[sender], body) for sender, body in reversed(rows)],
        [(pid, name) for pid, name in places],
        lender_dorm=dorms.get(tx.owner_id),
        borrower_dorm=dorms.get(tx.borrower_id),
        pickup_place_id=tx.pickup_place_id or (item.pickup_place_id if item else None),
        names={r: ai_handoff.name_parts(people[uid].name) for uid, r in role.items()},
        now=now,
    )


def run_suggest(transaction_id: int) -> None:
    """Background job. Never raises: a failure becomes status=failed with a friendly line."""
    try:
        with SessionLocal() as db:
            tx = db.get(Transaction, transaction_id)
            state = tx.handoff_suggestion if tx is not None else None
            if tx is None or not state or state.get("status") != "thinking":
                return
            asker = state.get("proposed_by")
            now = ai_handoff.campus_now()
            payload = gather_input(db, tx, now)
            paid = ai_handoff.is_paid()
            suggestion, ok = None, False
            try:
                suggestion = asyncio.run(
                    asyncio.wait_for(
                        ai_handoff.suggest(payload, now), settings.harnessrouter_timeout_s
                    )
                )
                ok = True
            except (ProviderError, TimeoutError, OSError, ValueError) as exc:
                log.warning("handoff suggestion for transaction %s failed: %s", transaction_id, exc)
            cost = suggestion.cost_usd if suggestion and suggestion.cost_usd is not None else None
            est = settings.handoff_est_cost_per_run if paid else 0.0
            db.add(
                Event(  # counts and costs only: never chat text, never who
                    user_id=None,
                    type=EVENT_TYPE,
                    payload={
                        "transaction_id": tx.id,
                        "ok": ok,
                        "sample": bool(suggestion.sample) if suggestion else not paid,
                        "cost_usd": round(cost if cost is not None else est, 4),
                        "cost_reported": cost is not None,
                        "latency_ms": suggestion.latency_ms if suggestion else 0,
                    },
                )
            )
            db.refresh(tx)
            current = tx.handoff_suggestion or {}
            if current.get("status") != "thinking":
                db.commit()  # someone sent their own time meanwhile: keep theirs
                return
            if suggestion is not None and tx.status in OPEN:
                _set(
                    tx,
                    status="draft",
                    proposed_by=asker,
                    start_time=suggestion.start_time.isoformat(),
                    place_id=suggestion.place_id,
                    reason=suggestion.reason,
                    confidence=suggestion.confidence,
                    sample=suggestion.sample,
                    source="ai",
                )
            else:
                _set(tx, status="failed", proposed_by=asker, message=FALLBACK)
            db.commit()
    except Exception:  # noqa: BLE001 — a background job must never take anything down
        log.exception("run_suggest(%s) failed", transaction_id)


# ---------------------------------------------------------------- 2. send it (or my own)
def send(db: Session, tx: Transaction, user: User, body: schemas.HandoffSendBody) -> None:
    from app.services.transactions import post_message

    if tx.status not in OPEN:
        raise HTTPException(409, "This is already handed over")
    state = _state(tx) or {}
    if (body.start_time is None) != (body.place_id is None):
        raise HTTPException(422, "Pick both a time and a place")
    if body.start_time is None:  # "Send": my draft, unchanged
        if state.get("status") != "draft" or state.get("proposed_by") != user.id:
            raise HTTPException(409, "There's no suggestion of yours to send")
        start = datetime.fromisoformat(state["start_time"])
        place_id = int(state["place_id"])
        extra = {k: state.get(k) for k in ("reason", "confidence", "sample", "source")}
    else:  # "Change": a time and place picked by hand
        start, place_id = body.start_time, body.place_id
        if start.tzinfo is None:
            start = start.replace(tzinfo=ZoneInfo(settings.campus_tz))
        extra = {"reason": None, "confidence": None, "sample": False, "source": "manual"}
    place = db.get(Place, place_id)
    if place is None:
        raise HTTPException(400, "That pickup spot doesn't exist")
    if start <= _now():
        raise HTTPException(400, "Pick a time in the future")
    if start > _now() + timedelta(days=MANUAL_MAX_DAYS):
        raise HTTPException(400, "Pick a time in the next few weeks")
    _set(
        tx,
        status="sent",
        proposed_by=user.id,
        start_time=start.isoformat(),
        place_id=place_id,
        **extra,
    )
    post_message(
        db,
        tx.conversation_id,
        None,
        f"{_first(user)} suggested meeting {_when(start)} at {place.name}.",
        read_by=user.id,
    )


# ---------------------------------------------------------------- 3. the other person's tap
def accept(db: Session, tx: Transaction, user: User) -> None:
    from app.services.transactions import _notify_update, _other_party, _record

    if tx.status not in OPEN:
        raise HTTPException(409, "This is already handed over")
    state = _state(tx) or {}
    if state.get("status") != "sent" or state.get("proposed_by") == user.id:
        raise HTTPException(409, "There's no suggestion waiting for you")
    start = datetime.fromisoformat(state["start_time"])
    place = db.get(Place, int(state["place_id"]))
    if place is None or start <= _now():
        raise HTTPException(409, "That time has passed — suggest a new one")
    tx.pickup_place_id, tx.pickup_at = place.id, start
    _set(tx, **{k: v for k, v in state.items() if k != "updated_at"} | {"status": "accepted"})
    # The same timeline + system message every other step of the transaction uses.
    _record(db, tx, user, f"Handoff set: {_when(start)} at {place.name}.")
    _notify_update(db, tx, _other_party(tx, user.id), f"{_first(user)} confirmed the time", user)


def dismiss(tx: Transaction, user: User) -> None:
    """Drop my own draft (or a failed run). A suggestion that was sent stays until answered."""
    state = _state(tx) or {}
    if state.get("proposed_by") == user.id and state.get("status") in ("draft", "failed"):
        tx.handoff_suggestion = None
