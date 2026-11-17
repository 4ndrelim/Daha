from fastapi import APIRouter, HTTPException, UploadFile

from app import schemas
from app.api.deps import DB, CurrentUser
from app.core import storage

router = APIRouter(tags=["uploads"])


@router.post("/uploads", response_model=schemas.Upload, status_code=201)
def create_upload(file: UploadFile, user: CurrentUser, db: DB):
    """jpeg/png/webp/heic ≤ 15 MB → re-encoded JPEG ≤ 1600 px with all metadata stripped."""
    data = file.file.read(storage.MAX_UPLOAD_BYTES + 1)
    try:
        upload = storage.save_image_bytes(db, user.id, data)
    except storage.InvalidImage as exc:
        raise HTTPException(400, str(exc)) from exc
    db.commit()
    return upload
