from fastapi import APIRouter, UploadFile

from app import schemas
from app.routers._stub import not_implemented

router = APIRouter(tags=["uploads"])


@router.post("/uploads", response_model=schemas.Upload, status_code=201)
def create_upload(file: UploadFile):
    not_implemented()
