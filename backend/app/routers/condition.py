"""Condition check endpoints (CONDITION_CHECK_ENABLED; 404 while off). See services/condition."""

from fastapi import APIRouter, BackgroundTasks, UploadFile

from app import schemas
from app.api.deps import DB, CurrentUser, Viewer
from app.core import storage
from app.services import condition, transactions

router = APIRouter(tags=["transactions"])


@router.put(
    "/transactions/{transaction_id}/condition/{stage}/{slot}", response_model=schemas.Transaction
)
def put_condition_photo(
    transaction_id: int,
    stage: schemas.ConditionStage,
    slot: schemas.ConditionSlot,
    file: UploadFile,
    user: CurrentUser,
    viewer: Viewer,
    db: DB,
    background: BackgroundTasks,
):
    """One guided photo (front | back | marks) for the handoff or the return. Item only."""
    condition.require_enabled()
    tx = transactions.get_for_party(db, transaction_id, user.id, lock=True)
    data = file.file.read(storage.MAX_UPLOAD_BYTES + 1)
    condition.save_photo(db, tx, user.id, stage, slot, data, background)
    db.commit()
    db.refresh(tx)
    return transactions.transaction_out(db, tx, viewer)


@router.post("/transactions/{transaction_id}/condition/confirm", response_model=schemas.Transaction)
def confirm_condition(transaction_id: int, user: CurrentUser, viewer: Viewer, db: DB):
    """The borrower taps "This looks right" on the 3 handoff photos."""
    condition.require_enabled()
    tx = transactions.get_for_party(db, transaction_id, user.id, lock=True)
    condition.confirm(db, tx, user.id)
    db.commit()
    db.refresh(tx)
    return transactions.transaction_out(db, tx, viewer)


@router.post("/transactions/{transaction_id}/condition/compare", response_model=schemas.Transaction)
def compare_condition(
    transaction_id: int, user: CurrentUser, viewer: Viewer, db: DB, background: BackgroundTasks
):
    """Run the comparison (it also starts by itself after the 3rd return photo). Idempotent."""
    condition.require_enabled()
    tx = transactions.get_for_party(db, transaction_id, user.id, lock=True)
    condition.start_compare(db, tx, background)
    db.commit()
    db.refresh(tx)
    return transactions.transaction_out(db, tx, viewer)
