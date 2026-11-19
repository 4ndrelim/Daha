"""Condition check on loans (CONDITION_CHECK_ENABLED, off by default).

Flow (lend only):
1. At handoff the OWNER snaps 3 guided photos: front, back, a close-up of any existing marks.
2. The BORROWER taps "This looks right" to confirm the starting condition.
3. After handoff, the BORROWER snaps the same 3 at return. The 3rd photo starts the comparison
   (app/ai/condition.py) in the background; both people see one result card.
4. When the exchange ends (completed, cancelled or declined) the photos are deleted and only the
   result text is kept. If a comparison is still running, it deletes them when it finishes.

Never touches points, karma, badges or reviews. Wording is always "possible changes".
"""

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas
from app.ai import condition as ai_condition
from app.ai.providers.base import ProviderError
from app.core import storage
from app.core.config import settings
from app.core.db import SessionLocal
from app.models import Event, Transaction, Upload

log = logging.getLogger(__name__)

SLOTS = ai_condition.SLOTS
ENDED = ("completed", "cancelled", "declined")
EVENT_TYPE = "condition_check_run"
FAILED_NOTE = "We couldn't compare the photos this time. Try again in a minute."
PAUSED_NOTE = "Condition checks are paused for now. Compare the photos together."


def _now() -> datetime:
    return datetime.now(UTC)


def enabled() -> bool:
    return settings.condition_check_enabled


def require_enabled() -> None:
    if not enabled():
        raise HTTPException(404, "Not found")


def _photos(value: dict | None) -> dict[str, int]:
    return {k: int(v) for k, v in (value or {}).items() if k in SLOTS and v}


def _complete(value: dict | None) -> bool:
    return len(_photos(value)) == len(SLOTS)


# ---------------------------------------------------------------- permissions
def can_add_handoff(tx: Transaction, user_id: int) -> bool:
    return (
        tx.owner_id == user_id
        and tx.status in ("accepted", "handed_off")
        and tx.condition_handoff_confirmed_at is None
    )


def can_confirm(tx: Transaction, user_id: int) -> bool:
    return (
        tx.borrower_id == user_id
        and tx.status in ("accepted", "handed_off")
        and tx.condition_handoff_confirmed_at is None
        and _complete(tx.condition_handoff_photos)
    )


def can_add_return(tx: Transaction, user_id: int) -> bool:
    return (
        tx.borrower_id == user_id
        and tx.status == "handed_off"
        and _complete(tx.condition_handoff_photos)
        and tx.condition_status not in ("checking", "done")
    )


# ---------------------------------------------------------------- serializer
def condition_out(db: Session, tx: Transaction, user_id: int) -> schemas.ConditionCheck | None:
    if not enabled() or tx.kind != "lend":
        return None
    ids = [
        *_photos(tx.condition_handoff_photos).values(),
        *_photos(tx.condition_return_photos).values(),
    ]
    urls = (
        {u.id: u.url for u in db.execute(select(Upload).where(Upload.id.in_(ids))).scalars()}
        if ids
        else {}
    )

    def photos(value: dict | None) -> schemas.ConditionPhotos:
        got = _photos(value)
        return schemas.ConditionPhotos(**{slot: urls.get(got.get(slot, -1)) for slot in SLOTS})

    return schemas.ConditionCheck(
        handoff_photos=photos(tx.condition_handoff_photos),
        handoff_confirmed_at=tx.condition_handoff_confirmed_at,
        return_photos=photos(tx.condition_return_photos),
        status=tx.condition_status or "waiting",
        result=tx.condition_result,
        note=tx.condition_note,
        sample=bool(tx.condition_sample),
        checked_at=tx.condition_checked_at,
        photos_deleted=tx.condition_photos_deleted_at is not None,
        can_add_handoff_photos=can_add_handoff(tx, user_id),
        can_confirm=can_confirm(tx, user_id),
        can_add_return_photos=can_add_return(tx, user_id),
    )


# ---------------------------------------------------------------- actions
def _check_lend(tx: Transaction) -> None:
    if tx.kind != "lend":
        raise HTTPException(409, "Condition check is only for things that come back")


def _delete_uploads(db: Session, ids: list[int]) -> None:
    for upload in db.execute(select(Upload).where(Upload.id.in_(ids))).scalars().all():
        try:
            (settings.upload_path / upload.path).unlink(missing_ok=True)
        except OSError:
            log.warning("condition: couldn't delete upload file %s", upload.id)
        db.delete(upload)


def save_photo(
    db: Session,
    tx: Transaction,
    user_id: int,
    stage: str,
    slot: str,
    data: bytes,
    background: BackgroundTasks,
) -> None:
    """Store one guided photo (same pipeline as POST /uploads: EXIF stripped, re-encoded)."""
    _check_lend(tx)
    if slot not in SLOTS:
        raise HTTPException(422, "Use front, back or marks")
    if stage == "handoff":
        if not can_add_handoff(tx, user_id):
            raise HTTPException(
                409, "Only the lender adds handoff photos, before they're confirmed"
            )
        column = "condition_handoff_photos"
    else:
        if not can_add_return(tx, user_id):
            raise HTTPException(
                409, "Return photos come from the borrower, after the handoff photos"
            )
        column = "condition_return_photos"
    try:
        upload = storage.save_image_bytes(db, user_id, data)
    except storage.InvalidImage as exc:
        raise HTTPException(400, str(exc)) from exc
    photos = _photos(getattr(tx, column))
    old = photos.get(slot)
    photos[slot] = upload.id
    setattr(tx, column, photos)  # a new dict, so SQLAlchemy sees the change
    if old:
        _delete_uploads(db, [old])
    if stage == "return" and _complete(photos):
        start_compare(db, tx, background)


def confirm(db: Session, tx: Transaction, user_id: int) -> None:
    _check_lend(tx)
    if not can_confirm(tx, user_id):
        raise HTTPException(409, "The lender's 3 handoff photos need to be in first")
    tx.condition_handoff_confirmed_at = _now()


def start_compare(db: Session, tx: Transaction, background: BackgroundTasks) -> None:
    """Start (or restart after a failure) the comparison; idempotent while one runs or is done."""
    _check_lend(tx)
    if not (_complete(tx.condition_handoff_photos) and _complete(tx.condition_return_photos)):
        raise HTTPException(409, "Both sets of 3 photos are needed first")
    if tx.condition_status in ("checking", "done"):
        return
    tx.condition_status = "checking"
    tx.condition_result = tx.condition_note = None
    db.flush()
    background.add_task(run_compare, tx.id)


def _spent(db: Session) -> float:
    total = db.scalar(
        select(func.coalesce(func.sum(Event.payload["cost_usd"].as_float()), 0.0)).where(
            Event.type == EVENT_TYPE
        )
    )
    return float(total or 0.0)


def _paid() -> bool:
    return settings.ai_provider.strip().lower() == "harnessrouter" and ai_condition.is_set_up()


def run_compare(transaction_id: int) -> None:
    """Background job. Never raises: a failure becomes status=failed with a friendly note."""
    try:
        with SessionLocal() as db:
            tx = db.get(Transaction, transaction_id)
            if tx is None or tx.condition_status != "checking":
                return
            before = [_read(db, _photos(tx.condition_handoff_photos)[s]) for s in SLOTS]
            after = [_read(db, _photos(tx.condition_return_photos)[s]) for s in SLOTS]
            paid = _paid()
            if (
                paid
                and _spent(db) + settings.condition_est_cost_per_check
                > settings.condition_budget_usd
            ):
                tx.condition_status, tx.condition_note = "failed", PAUSED_NOTE
                db.commit()
                return
            verdict, ok = None, False
            try:
                verdict = asyncio.run(
                    asyncio.wait_for(
                        ai_condition.compare(before, after), settings.harnessrouter_timeout_s
                    )
                )
                ok = True
            except (ProviderError, TimeoutError, OSError, ValueError) as exc:
                log.warning("condition check for transaction %s failed: %s", transaction_id, exc)
            if paid:  # a failed task may still have been billed, so it counts too
                cost = verdict.cost_usd if verdict and verdict.cost_usd is not None else None
                db.add(
                    Event(
                        user_id=None,
                        type=EVENT_TYPE,
                        payload={
                            "ok": ok,
                            "cost_usd": round(
                                cost if cost is not None else settings.condition_est_cost_per_check,
                                4,
                            ),
                            "cost_reported": cost is not None,
                            "latency_ms": verdict.latency_ms if verdict else 0,
                            "result": verdict.result if verdict else None,
                        },
                    )
                )
            db.refresh(tx)
            if verdict is not None:
                tx.condition_status, tx.condition_result = "done", verdict.result
                tx.condition_note, tx.condition_sample = verdict.note, verdict.sample
                tx.condition_checked_at = _now()
            else:
                tx.condition_status, tx.condition_note = "failed", FAILED_NOTE
            if tx.status in ENDED:  # the exchange finished while we were comparing
                delete_photos(db, tx)
            db.commit()
    except Exception:  # noqa: BLE001 — a background job must never take anything down
        log.exception("run_compare(%s) failed", transaction_id)


def _read(db: Session, upload_id: int) -> bytes:
    return storage.read_upload_bytes(db, upload_id)


def delete_photos(db: Session, tx: Transaction) -> None:
    ids = [
        *_photos(tx.condition_handoff_photos).values(),
        *_photos(tx.condition_return_photos).values(),
    ]
    if not ids:
        return
    _delete_uploads(db, ids)
    tx.condition_handoff_photos = None
    tx.condition_return_photos = None
    tx.condition_photos_deleted_at = _now()


def on_status_change(db: Session, tx: Transaction) -> None:
    """Called after every transaction action: an ended exchange keeps only the result text."""
    if tx.status in ENDED and tx.condition_status != "checking":
        delete_photos(db, tx)
