"""Scan pipeline (PLAN.md C1.4): create → process in the background → poll → publish."""

import asyncio
import io
import logging
import time
from datetime import UTC, datetime, timedelta

from fastapi import BackgroundTasks, HTTPException
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas
from app.ai import vision
from app.ai.prompts import PROMPT_VERSION
from app.ai.providers import ProviderError, get_vision_provider
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.storage import InvalidImage, read_upload_bytes, save_image_bytes
from app.models import Scan, ScanDetection, ScanImage, Upload, User
from app.services import items as items_service
from app.services import points, serializers
from app.services.viewer import build_viewer

log = logging.getLogger(__name__)

SHARE_MIN_CONFIDENCE = 0.35
STUCK_AFTER = timedelta(minutes=10)
MAX_PUBLISH_ITEMS = 120  # 6 photos × 20 detections
CROP_PADDING = 0.08
GENERIC_ERROR = "We couldn't read this photo. Try another angle."


# ---------------------------------------------------------------- limits
def _paid_estimate() -> float:
    if settings.ai_provider == "harnessrouter":
        return settings.harnessrouter_est_cost_per_image
    if settings.ai_provider == "anthropic":
        return 0.05
    return 0.0


def check_limits(db: Session, user_id: int, n_images: int) -> None:
    since = datetime.now(UTC) - timedelta(hours=24)
    today = db.scalar(
        select(func.count())
        .select_from(Scan)
        .where(Scan.user_id == user_id, Scan.created_at >= since)
    )
    if (today or 0) >= settings.ai_daily_scans_per_user:
        raise HTTPException(429, "You've hit today's scan limit — list items manually for now")
    est = _paid_estimate()
    if est <= 0:
        return
    spent = db.scalar(select(func.coalesce(func.sum(ScanImage.cost_usd), 0.0))) or 0.0
    in_flight = db.scalar(
        select(func.count())
        .select_from(ScanImage)
        .where(ScanImage.status.in_(("pending", "processing")))
    )
    if float(spent) + ((in_flight or 0) + n_images) * est >= settings.ai_budget_usd:
        raise HTTPException(429, "AI scanning paused — list items manually")


# ---------------------------------------------------------------- serializers
def scan_out(db: Session, scan: Scan) -> schemas.Scan:
    images = db.execute(
        select(ScanImage, Upload.url)
        .join(Upload, Upload.id == ScanImage.upload_id)
        .where(ScanImage.scan_id == scan.id)
        .order_by(ScanImage.position)
    ).all()
    dets = db.scalars(
        select(ScanDetection)
        .where(ScanDetection.scan_id == scan.id)
        .order_by(ScanDetection.image_index, ScanDetection.id)
    ).all()
    return schemas.Scan(
        id=scan.id,
        status=scan.status,
        images=[
            schemas.ScanImage(upload_id=img.upload_id, url=url, status=img.status, error=img.error)
            for img, url in images
        ],
        detections=[
            schemas.Detection(
                id=d.id,
                image_index=d.image_index,
                name=d.name,
                category=d.category,
                description=d.description,
                quantity=d.quantity,
                condition_guess=d.condition_guess,
                confidence=d.confidence,
                bbox=tuple(d.bbox) if isinstance(d.bbox, list) and len(d.bbox) == 4 else None,
                suggested_share=d.suggested_share,
                sensitive_reason=d.sensitive_reason,
                suggested_transaction_type=d.suggested_transaction_type,
                status=d.status,
            )
            for d in dets
        ],
        provider=scan.provider,
        created_at=scan.created_at,
    )


# ---------------------------------------------------------------- create / get
def create_scan(
    db: Session, user: User, body: schemas.ScanCreate, background: BackgroundTasks
) -> Scan:
    ids = list(dict.fromkeys(body.upload_ids))
    if not ids:
        raise HTTPException(400, "Add at least one photo")
    if len(ids) > settings.ai_max_images_per_scan:
        raise HTTPException(400, f"At most {settings.ai_max_images_per_scan} photos per scan")
    owned = set(db.scalars(select(Upload.id).where(Upload.id.in_(ids), Upload.owner_id == user.id)))
    if owned != set(ids):
        raise HTTPException(400, "Upload the photos first")
    check_limits(db, user.id, len(ids))

    provider = get_vision_provider()
    scan = Scan(
        user_id=user.id,
        status="processing",
        provider=provider.name,
        model=provider.model,
        prompt_version=PROMPT_VERSION,
    )
    db.add(scan)
    db.flush()
    db.add_all(
        ScanImage(scan_id=scan.id, upload_id=uid, position=pos, status="pending")
        for pos, uid in enumerate(ids)
    )
    db.commit()
    background.add_task(process_scan, scan.id)
    return scan


def get_own_scan(db: Session, user: User, scan_id: int, *, lock: bool = False) -> Scan:
    q = select(Scan).where(Scan.id == scan_id, Scan.user_id == user.id)
    if lock:
        q = q.with_for_update()
    scan = db.scalar(q)
    if scan is None:
        raise HTTPException(404, "Scan not found")
    return scan


def expire_if_stuck(db: Session, scan: Scan) -> None:
    """A scan still processing after 10 minutes (e.g. the server restarted) is closed out."""
    if scan.status != "processing" or scan.created_at > datetime.now(UTC) - STUCK_AFTER:
        return
    for img in db.scalars(select(ScanImage).where(ScanImage.scan_id == scan.id)):
        if img.status in ("pending", "processing"):
            img.status, img.error = "failed", "This photo timed out. Try again."
    db.flush()
    _finish(db, scan)
    db.commit()


def _finish(db: Session, scan: Scan) -> None:
    statuses = list(db.scalars(select(ScanImage.status).where(ScanImage.scan_id == scan.id)))
    if any(s in ("pending", "processing") for s in statuses):
        return
    scan.status = "done" if "done" in statuses else "failed"
    scan.finished_at = datetime.now(UTC)


# ---------------------------------------------------------------- background processing
async def process_scan(scan_id: int) -> None:
    """Runs after the response. Opens its own sessions; never raises."""
    try:
        image_ids = await asyncio.to_thread(_image_ids, scan_id)
        await asyncio.gather(*(_process_image(scan_id, iid) for iid in image_ids))
    except Exception:  # noqa: BLE001 — a background task must never crash the worker
        log.exception("process_scan %s crashed", scan_id)
    finally:
        await asyncio.to_thread(_finalize, scan_id)


def _image_ids(scan_id: int) -> list[int]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(ScanImage.id)
                .where(ScanImage.scan_id == scan_id, ScanImage.status == "pending")
                .order_by(ScanImage.position)
            )
        )


def _finalize(scan_id: int) -> None:
    with SessionLocal() as db:
        scan = db.get(Scan, scan_id)
        if scan is None:
            return
        for img in db.scalars(select(ScanImage).where(ScanImage.scan_id == scan_id)):
            if img.status in ("pending", "processing"):  # something crashed mid-way
                img.status, img.error = "failed", GENERIC_ERROR
        db.flush()
        _finish(db, scan)
        db.commit()


def _start_image(image_id: int) -> tuple[bytes, int, str] | None:
    with SessionLocal() as db:
        img = db.get(ScanImage, image_id)
        if img is None or img.status != "pending":
            return None
        img.status = "processing"
        db.commit()
        data = vision.downscale(read_upload_bytes(db, img.upload_id))
        return data, img.position, f"photo_{img.position + 1}.jpg"


def _cached(key: str):
    with SessionLocal() as db:
        return vision.cache_get(db, key)


def _save_image_result(
    image_id: int, items, latency_ms: int, cost: float | None, raw: dict
) -> None:
    with SessionLocal() as db:
        img = db.get(ScanImage, image_id)
        if img is None:
            return
        db.add_all(
            ScanDetection(
                scan_id=img.scan_id,
                scan_image_id=img.id,
                image_index=img.position,
                name=it.name,
                category=it.category,
                description=it.description,
                quantity=it.quantity,
                condition_guess=it.condition_guess,
                confidence=it.confidence,
                bbox=it.bbox,
                suggested_share=it.suggested_share and it.confidence >= SHARE_MIN_CONFIDENCE,
                sensitive_reason=it.sensitive_reason,
                suggested_transaction_type=it.suggested_transaction_type,
                status="pending",
            )
            for it in items
        )
        img.status, img.error = "done", None
        img.latency_ms, img.cost_usd, img.raw_response = latency_ms, cost, raw
        db.commit()


def _fail_image(image_id: int, message: str, raw: dict | None = None) -> None:
    with SessionLocal() as db:
        img = db.get(ScanImage, image_id)
        if img is not None:
            img.status, img.error, img.raw_response = "failed", message[:200], raw
            db.commit()


async def _process_image(scan_id: int, image_id: int) -> None:
    start = time.monotonic()
    try:
        started = await asyncio.to_thread(_start_image, image_id)
        if started is None:
            return
        data, _pos, filename = started
        provider = get_vision_provider()
        key = vision.cache_key(data, provider)
        cached = await asyncio.to_thread(_cached, key)
        if cached is not None:
            latency = int((time.monotonic() - start) * 1000)
            await asyncio.to_thread(
                _save_image_result, image_id, cached, latency, 0.0, {"cache": key}
            )
            return
        result = await vision.detect(provider, data, filename)
        await asyncio.to_thread(
            _save_image_result,
            image_id,
            result.items,
            result.latency_ms,
            result.cost_usd,
            result.raw,
        )
        await asyncio.to_thread(_cache_result, key, result)
    except ProviderError as exc:
        log.warning("scan %s image %s: %s", scan_id, image_id, exc)
        await asyncio.to_thread(_fail_image, image_id, exc.user_message, {"error": str(exc)[:500]})
    except Exception as exc:  # noqa: BLE001
        log.exception("scan %s image %s crashed", scan_id, image_id)
        await asyncio.to_thread(_fail_image, image_id, GENERIC_ERROR, {"error": type(exc).__name__})


def _cache_result(key: str, result) -> None:
    with SessionLocal() as db:
        vision.cache_put(db, key, result)


# ---------------------------------------------------------------- publish
def _crop(db: Session, owner_id: int, upload_id: int, bbox) -> int:
    """Crop the source photo to the bbox (+8% padding) and save it as a new upload."""
    if not (isinstance(bbox, list) and len(bbox) == 4):
        return upload_id
    try:
        img = Image.open(io.BytesIO(read_upload_bytes(db, upload_id))).convert("RGB")
        W, H = img.size
        x, y, w, h = (float(v) for v in bbox)
        px, py = w * CROP_PADDING, h * CROP_PADDING
        left, top = max(0, int((x - px) * W)), max(0, int((y - py) * H))
        right, bottom = min(W, int((x + w + px) * W)), min(H, int((y + h + py) * H))
        if right - left < 48 or bottom - top < 48:
            return upload_id
        out = io.BytesIO()
        img.crop((left, top, right, bottom)).save(out, format="JPEG", quality=88)
        return save_image_bytes(db, owner_id, out.getvalue()).id
    except (OSError, ValueError, InvalidImage):
        log.warning("crop failed for upload %s; using the full photo", upload_id)
        return upload_id


_EDIT_FIELDS = {
    "name": "name",
    "category": "category",
    "quantity": "quantity",
    "transaction_type": "suggested_transaction_type",
    "description": "description",
    "condition": "condition_guess",
}


def _edits(item: schemas.ScanPublishItem, det: ScanDetection) -> dict:
    out = {}
    for field, det_field in _EDIT_FIELDS.items():
        new, old = getattr(item, field), getattr(det, det_field)
        if field in ("name", "description"):
            new, old = (new or "").strip(), (old or "").strip()
        if new != old:
            out[field] = {"from": old, "to": new}
    return out


def publish_scan(
    db: Session,
    user: User,
    scan_id: int,
    body: schemas.ScanPublishBody,
    background: BackgroundTasks,
) -> schemas.ScanPublishResponse:
    scan = get_own_scan(db, user, scan_id, lock=True)
    if scan.status != "done":
        raise HTTPException(409, "This scan isn't ready to share yet")
    if not body.items:
        raise HTTPException(400, "Pick at least one item to share")
    if len(body.items) > MAX_PUBLISH_ITEMS:
        raise HTTPException(400, f"At most {MAX_PUBLISH_ITEMS} items at once")

    dets = {
        d.id: d for d in db.scalars(select(ScanDetection).where(ScanDetection.scan_id == scan.id))
    }
    if any(d.status != "pending" for d in dets.values()):
        raise HTTPException(409, "These items were already shared")
    chosen = [i.detection_id for i in body.items if i.detection_id is not None]
    if len(chosen) != len(set(chosen)):
        raise HTTPException(400, "Each detected item can be shared once")
    if any(did not in dets for did in chosen):
        raise HTTPException(400, "That item isn't part of this scan")
    uploads = dict(
        db.execute(
            select(ScanImage.id, ScanImage.upload_id).where(ScanImage.scan_id == scan.id)
        ).all()
    )

    before = points.user_points(db, user.id)
    created = []
    for entry in body.items:
        det = dets.get(entry.detection_id) if entry.detection_id is not None else None
        data = schemas.ItemCreate.model_validate(entry.model_dump(exclude={"detection_id"}))
        if det is not None and not data.image_upload_ids:
            data.image_upload_ids = [_crop(db, user.id, uploads[det.scan_image_id], det.bbox)]
        item = items_service.create_item(
            db,
            user,
            data,
            source="scan",
            scan_detection_id=det.id if det else None,
            background=background,
        )
        if det is not None:
            det.status, det.published_item_id = "published", item.id
            det.edits = _edits(entry, det)
        created.append(item)
    for det in dets.values():
        if det.status == "pending":
            det.status = "discarded"
    user.onboarded = True
    db.add(user)
    db.flush()
    awarded = points.user_points(db, user.id) - before
    db.commit()
    viewer = build_viewer(db, user)
    return schemas.ScanPublishResponse(
        items=[serializers.item_detail(db, item, viewer) for item in created],
        points_awarded=max(0, awarded),
    )
