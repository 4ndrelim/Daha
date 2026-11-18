"""Recompute every embedding (make reindex; the seed calls it)."""

import logging

from sqlalchemy import select

from app.core.db import SessionLocal
from app.discovery.embeddings import embed_passages
from app.discovery.texts import item_text, request_text
from app.models import Item, ItemRequest

log = logging.getLogger(__name__)
BATCH = 64


def reindex_all() -> int:
    total = 0
    with SessionLocal() as db:
        for model, recipe in ((Item, item_text), (ItemRequest, request_text)):
            last_id = 0
            while True:
                rows = db.scalars(
                    select(model).where(model.id > last_id).order_by(model.id).limit(BATCH)
                ).all()
                if not rows:
                    break
                for row, vec in zip(rows, embed_passages([recipe(r) for r in rows]), strict=True):
                    row.embedding = vec
                db.commit()
                total += len(rows)
                last_id = rows[-1].id
    return total
