"""Image storage (PLAN.md §7.10): local disk, re-encoded JPEGs with all metadata removed."""

import hashlib
import io
import uuid

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Upload

register_heif_opener()

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_SIDE_PX = 1600
JPEG_QUALITY = 85
ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP", "HEIF"}


class InvalidImage(ValueError):
    """The bytes are not an image we accept. The message is safe to show to the user."""


def process_image(data: bytes) -> tuple[bytes, int, int]:
    """Re-encode as an RGB JPEG ≤ 1600 px on the long side, with no EXIF/GPS/ICC metadata."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise InvalidImage("Image is too large (max 15 MB)")
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ALLOWED_FORMATS:
            raise InvalidImage("Use a JPEG, PNG, WebP, or HEIC photo")
        img = ImageOps.exif_transpose(img)  # apply the camera rotation before dropping EXIF
        img = img.convert("RGB")
    except InvalidImage:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidImage("That file isn't a readable image") from exc
    img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX), Image.Resampling.LANCZOS)
    # Copy the pixels into a brand-new image so nothing from img.info can leak into the file.
    clean = Image.new("RGB", img.size)
    clean.paste(img)
    out = io.BytesIO()
    clean.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue(), clean.width, clean.height


def save_image_bytes(db: Session, owner_id: int, data: bytes) -> Upload:
    """Same pipeline as POST /uploads. Raises InvalidImage. The caller commits."""
    jpeg, width, height = process_image(data)
    name = f"{uuid.uuid4().hex}.jpg"
    directory = settings.upload_path
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(jpeg)
    upload = Upload(
        owner_id=owner_id,
        path=name,
        url=f"/uploads/{name}",
        width=width,
        height=height,
        sha256=hashlib.sha256(jpeg).hexdigest(),
    )
    db.add(upload)
    db.flush()
    return upload


def read_upload_bytes(db: Session, upload_id: int) -> bytes:
    upload = db.get(Upload, upload_id)
    if upload is None:
        raise FileNotFoundError(f"upload {upload_id} not found")
    return (settings.upload_path / upload.path).read_bytes()
