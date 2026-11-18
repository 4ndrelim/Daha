"""Hooks A calls after writes (PLAN.md §7.10). Sync; each opens its own SessionLocal().

They run in FastAPI background tasks, so they must never raise: a failure is logged, and a
request still ends with matching_status='done' so the UI never spins forever.
"""

import logging

from app.core.db import SessionLocal
from app.discovery import reindex
from app.discovery.embeddings import embed_passages
from app.discovery.texts import item_text
from app.models import Item, ItemRequest

log = logging.getLogger(__name__)


def on_item_saved(item_id: int) -> None:
    try:
        with SessionLocal() as db:
            item = db.get(Item, item_id)
            if item is None:
                return
            item.embedding = embed_passages([item_text(item)])[0]
            db.commit()
    except Exception:  # noqa: BLE001
        log.exception("on_item_saved(%s): embedding failed", item_id)
    try:
        from app.discovery.matching import reverse_match_item

        reverse_match_item(item_id)
    except Exception:  # noqa: BLE001
        log.exception("on_item_saved(%s): reverse matching failed", item_id)


def on_request_created(request_id: int) -> None:
    try:
        from app.discovery.matching import match_request

        match_request(request_id, notify_new_only=False)
    except Exception:  # noqa: BLE001
        log.exception("on_request_created(%s) failed", request_id)
        _mark_done(request_id)


def on_request_updated(request_id: int) -> None:
    try:
        from app.discovery.matching import match_request

        match_request(request_id, notify_new_only=True)
    except Exception:  # noqa: BLE001
        log.exception("on_request_updated(%s) failed", request_id)
        _mark_done(request_id)


def _mark_done(request_id: int) -> None:
    try:
        with SessionLocal() as db:
            req = db.get(ItemRequest, request_id)
            if req is not None and req.matching_status != "done":
                req.matching_status = "done"
                db.commit()
    except Exception:  # noqa: BLE001
        log.exception("could not mark request %s done", request_id)


def reindex_all() -> int:
    return reindex.reindex_all()
