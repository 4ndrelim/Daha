"""Item creation shared by POST /items, offers, and C's scan publish. Stub; implemented in A2."""

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app import schemas
from app.models import Item, User


def create_item(
    db: Session,
    owner: User,
    data: schemas.ItemCreate,
    *,
    source: str = "manual",
    scan_detection_id: int | None = None,
    background: BackgroundTasks | None = None,
) -> Item:
    """Validates, writes audiences + images, awards points/badges, schedules hooks.on_item_saved."""
    raise NotImplementedError("create_item arrives in A2")
