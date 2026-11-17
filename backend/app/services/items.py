"""Items: one place for validation, audiences, images, points, and the discovery hook.

Used by POST /items, POST /items/batch, offers (A3), and C's scan publish.
"""

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import schemas
from app.discovery import hooks
from app.models import Item, ItemAudience, ItemImage, Place, PointsLedger, Upload, User
from app.services import points
from app.services.viewer import ViewerContext
from app.services.visibility import item_visible_clause, resolve_audiences

MAX_IMAGES = 6
MAX_BATCH = 30


def _validate_core(category: str, transaction_type: str, available_from, available_until) -> None:
    if category == "services" and transaction_type == "lend":
        raise HTTPException(400, "Services can be free or a swap, but not lent")
    if available_from and available_until and available_from > available_until:
        raise HTTPException(400, "The availability end date is before the start date")


def _validate_place(db: Session, place_id: int | None) -> None:
    if place_id is not None and db.get(Place, place_id) is None:
        raise HTTPException(400, "That pickup spot doesn't exist")


def _validate_images(db: Session, owner_id: int, upload_ids: list[int]) -> list[int]:
    ids = list(dict.fromkeys(upload_ids))
    if len(ids) > MAX_IMAGES:
        raise HTTPException(400, f"An item can have at most {MAX_IMAGES} photos")
    if ids:
        owned = set(
            db.scalars(select(Upload.id).where(Upload.id.in_(ids), Upload.owner_id == owner_id))
        )
        if owned != set(ids):
            raise HTTPException(400, "Upload the photos first")
    return ids


def _write_audiences(db: Session, item: Item, community_ids: list[int]) -> None:
    db.execute(delete(ItemAudience).where(ItemAudience.item_id == item.id))
    db.add_all(ItemAudience(item_id=item.id, community_id=cid) for cid in community_ids)


def _write_images(db: Session, item: Item, upload_ids: list[int]) -> None:
    db.execute(delete(ItemImage).where(ItemImage.item_id == item.id))
    db.add_all(
        ItemImage(item_id=item.id, upload_id=uid, position=pos)
        for pos, uid in enumerate(upload_ids)
    )


def _award_published(db: Session, item: Item) -> int:
    """+2 once per item, when it is first shared with anyone (never for private items)."""
    if item.visibility == "private":
        return 0
    already = db.scalar(
        select(func.count())
        .select_from(PointsLedger)
        .where(
            PointsLedger.reason == "item_published",
            PointsLedger.ref_type == "item",
            PointsLedger.ref_id == item.id,
        )
    )
    earned = 0 if already else points.award_item_published(db, item.owner_id, item.id)
    points.check_badges(db, item.owner_id)
    return earned


def create_item(
    db: Session,
    owner: User,
    data: schemas.ItemCreate,
    *,
    source: str = "manual",
    scan_detection_id: int | None = None,
    background: BackgroundTasks | None = None,
) -> Item:
    """Validate, write the item + audiences + images, award points/badges, schedule the hook.

    Does NOT commit: the caller commits, so several items can share one DB transaction.
    `hooks.on_item_saved` is queued on `background`, which FastAPI runs after the response
    (so after the caller's commit). With `background=None` no hook is scheduled.
    Raises HTTPException(400) on invalid input.
    """
    _validate_core(data.category, data.transaction_type, data.available_from, data.available_until)
    _validate_place(db, data.pickup_place_id)
    upload_ids = _validate_images(db, owner.id, data.image_upload_ids)
    audience = resolve_audiences(db, owner, data.visibility, data.group_ids)

    item = Item(
        owner_id=owner.id,
        name=data.name.strip(),
        description=data.description,
        category=data.category,
        quantity=data.quantity,
        condition=data.condition,
        transaction_type=data.transaction_type,
        max_lend_days=data.max_lend_days,
        available_from=data.available_from,
        available_until=data.available_until,
        visibility=data.visibility,
        pings_enabled=data.pings_enabled,
        pickup_place_id=data.pickup_place_id,
        pickup_note=data.pickup_note,
        source=source,
        scan_detection_id=scan_detection_id,
    )
    db.add(item)
    db.flush()
    _write_audiences(db, item, audience)
    _write_images(db, item, upload_ids)
    db.flush()
    _award_published(db, item)
    if background is not None:
        background.add_task(hooks.on_item_saved, item.id)
    return item


def update_item(
    db: Session,
    item: Item,
    owner: User,
    data: schemas.ItemUpdate,
    background: BackgroundTasks | None = None,
) -> Item:
    """Apply only the fields present in the body. Does not commit."""
    sent = data.model_fields_set
    not_nullable = {"name", "category", "quantity", "transaction_type", "visibility"}
    for field in (
        "name",
        "description",
        "category",
        "quantity",
        "condition",
        "transaction_type",
        "max_lend_days",
        "available_from",
        "available_until",
        "pickup_place_id",
        "pickup_note",
        "pings_enabled",
    ):
        if field not in sent:
            continue
        value = getattr(data, field)
        if value is None and field in not_nullable | {"pings_enabled"}:
            continue
        setattr(item, field, value.strip() if field == "name" else value)

    _validate_core(item.category, item.transaction_type, item.available_from, item.available_until)
    if "pickup_place_id" in sent:
        _validate_place(db, item.pickup_place_id)

    if "status" in sent and data.status is not None and data.status != item.status:
        # Owners may only flip available ↔ unavailable; reserved/borrowed belong to transactions.
        if item.status not in ("available", "unavailable"):
            raise HTTPException(409, "This item is in the middle of a handoff")
        item.status = data.status

    visibility_sent = "visibility" in sent and data.visibility is not None
    if visibility_sent or ("group_ids" in sent and data.group_ids is not None):
        if visibility_sent:
            item.visibility = data.visibility
        group_ids = data.group_ids
        if group_ids is None and item.visibility == "groups":
            group_ids = list(
                db.scalars(select(ItemAudience.community_id).where(ItemAudience.item_id == item.id))
            )
        _write_audiences(db, item, resolve_audiences(db, owner, item.visibility, group_ids))

    if "image_upload_ids" in sent and data.image_upload_ids is not None:
        _write_images(db, item, _validate_images(db, owner.id, data.image_upload_ids))

    db.add(item)
    db.flush()
    _award_published(db, item)
    if background is not None:
        background.add_task(hooks.on_item_saved, item.id)
    return item


def archive_item(db: Session, item: Item) -> None:
    if item.status in ("reserved", "borrowed"):
        raise HTTPException(409, "Finish or cancel the current handoff before removing this item")
    item.archived = True
    db.add(item)
    db.flush()


def get_visible_item(db: Session, item_id: int, viewer: ViewerContext) -> Item:
    """The item if the viewer may see it, else 404 (never 403 — don't reveal it exists)."""
    item = db.execute(
        select(Item).where(Item.id == item_id, item_visible_clause(viewer))
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Item not found")
    return item


def get_own_item(db: Session, item_id: int, viewer: ViewerContext) -> Item:
    item = get_visible_item(db, item_id, viewer)
    if item.owner_id != viewer.user_id:
        raise HTTPException(403, "Only the owner can change this item")
    return item
