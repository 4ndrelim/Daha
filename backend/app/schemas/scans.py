from typing import Literal

from app.schemas.common import ID, Category, Condition, ISODateTime, Schema, TransactionType
from app.schemas.items import ItemCreate, ItemDetail


class ScanImage(Schema):
    upload_id: ID
    url: str
    status: Literal["pending", "processing", "done", "failed"]
    error: str | None


class Detection(Schema):
    id: ID
    image_index: int
    name: str
    category: Category
    description: str
    quantity: int
    condition_guess: Condition | None
    confidence: float
    bbox: tuple[float, float, float, float] | None  # normalized x, y, w, h (0..1), approximate
    suggested_share: bool
    sensitive_reason: str | None
    suggested_transaction_type: TransactionType
    status: Literal["pending", "published", "discarded"]


class Scan(Schema):
    id: ID
    status: Literal["processing", "done", "failed"]
    images: list[ScanImage]
    detections: list[Detection]
    provider: str
    created_at: ISODateTime


class ScanCreate(Schema):
    upload_ids: list[ID]


class ScanPublishItem(ItemCreate):
    # empty image_upload_ids → server uses the source photo (cropped to bbox if available)
    detection_id: ID | None = None


class ScanPublishBody(Schema):
    items: list[ScanPublishItem]


class ScanPublishResponse(Schema):
    items: list[ItemDetail]
    points_awarded: int
