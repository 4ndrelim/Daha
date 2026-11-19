"""Handoff coordinator endpoints (HANDOFF_COORDINATOR_ENABLED; 404 while off).

The rules live in services/handoff.
"""

from fastapi import APIRouter, BackgroundTasks

from app import schemas
from app.api.deps import DB, CurrentUser, Viewer
from app.services import handoff, transactions

router = APIRouter(tags=["transactions"])


def _out(db, tx, viewer):
    db.commit()
    db.refresh(tx)
    return transactions.transaction_out(db, tx, viewer)


@router.post("/transactions/{transaction_id}/handoff/suggest", response_model=schemas.Transaction)
def suggest_handoff(
    transaction_id: int, user: CurrentUser, viewer: Viewer, db: DB, background: BackgroundTasks
):
    """The "Suggest a time & place" tap: the only thing that starts the agent (3 a day)."""
    handoff.require_enabled()
    tx = transactions.get_for_party(db, transaction_id, user.id, lock=True)
    handoff.start_suggest(db, tx, user, background)
    return _out(db, tx, viewer)


@router.post("/transactions/{transaction_id}/handoff/send", response_model=schemas.Transaction)
def send_handoff(
    transaction_id: int, body: schemas.HandoffSendBody, user: CurrentUser, viewer: Viewer, db: DB
):
    """Send my draft as it is (empty body), or a time and place I picked ("Change")."""
    handoff.require_enabled()
    tx = transactions.get_for_party(db, transaction_id, user.id, lock=True)
    handoff.send(db, tx, user, body)
    return _out(db, tx, viewer)


@router.post("/transactions/{transaction_id}/handoff/accept", response_model=schemas.Transaction)
def accept_handoff(transaction_id: int, user: CurrentUser, viewer: Viewer, db: DB):
    """The other person's one tap: it becomes the transaction's pickup place and time."""
    handoff.require_enabled()
    tx = transactions.get_for_party(db, transaction_id, user.id, lock=True)
    handoff.accept(db, tx, user)
    return _out(db, tx, viewer)


@router.delete("/transactions/{transaction_id}/handoff", response_model=schemas.Transaction)
def dismiss_handoff(transaction_id: int, user: CurrentUser, viewer: Viewer, db: DB):
    """Drop my own draft."""
    handoff.require_enabled()
    tx = transactions.get_for_party(db, transaction_id, user.id, lock=True)
    handoff.dismiss(tx, user)
    return _out(db, tx, viewer)
