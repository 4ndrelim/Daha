"""Image storage (PLAN.md §7.10). Signatures only in P0-A; implemented in A1."""

from sqlalchemy.orm import Session

from app.models import Upload


def save_image_bytes(db: Session, owner_id: int, data: bytes) -> Upload:
    """Same pipeline as POST /uploads: re-encode as JPEG ≤ 1600 px with metadata stripped."""
    raise NotImplementedError("save_image_bytes arrives in A1")


def read_upload_bytes(db: Session, upload_id: int) -> bytes:
    raise NotImplementedError("read_upload_bytes arrives in A1")
