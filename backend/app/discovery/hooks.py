"""Hooks A calls after writes (PLAN.md §7.10). Person C owns this file from now on.

Each hook is sync and opens its own SessionLocal(). P0-A ships them as no-ops.
"""

from app.core.db import SessionLocal
from app.models import ItemRequest


def on_item_saved(item_id: int) -> None:
    pass


def on_request_created(request_id: int) -> None:
    with SessionLocal() as db:
        req = db.get(ItemRequest, request_id)
        if req is not None:
            req.matching_status = "done"
            db.commit()


def on_request_updated(request_id: int) -> None:
    pass


def reindex_all() -> int:
    return 0
