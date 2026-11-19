"""One photo → normalized detections, through ai_cache and the configured provider."""

import hashlib
import io
import logging

from PIL import Image
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.ai.normalize import normalize_items
from app.ai.prompts import prompt_version
from app.ai.providers import VisionProvider
from app.ai.schemas import DetectedItemRaw, ProviderResult
from app.models import AICache

log = logging.getLogger(__name__)
MAX_SIDE_PX = 1568  # what vision models handle without internal resizing


def downscale(jpeg: bytes, max_side: int = MAX_SIDE_PX) -> bytes:
    img = Image.open(io.BytesIO(jpeg))
    if max(img.size) <= max_side and img.format == "JPEG":
        return jpeg
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


def cache_key(image: bytes, provider: VisionProvider) -> str:
    digest = hashlib.sha256(image).hexdigest()
    return f"{digest}:{prompt_version()}:{provider.name}:{provider.model}"


def cache_get(db: Session, key: str) -> list[DetectedItemRaw] | None:
    row = db.get(AICache, key)
    if row is None or not isinstance(row.value, dict):
        return None
    return normalize_items(row.value.get("items"))


def cache_put(db: Session, key: str, result: ProviderResult) -> None:
    value = {"items": [i.model_dump() for i in result.items]}
    db.execute(insert(AICache).values(key=key, value=value).on_conflict_do_nothing())
    db.commit()


async def detect(provider: VisionProvider, image: bytes, filename: str) -> ProviderResult:
    """Call the provider and normalize again (defense in depth: providers may skip it)."""
    result = await provider.detect(image, filename)
    result.items = normalize_items([i.model_dump() for i in result.items])
    return result
