"""AI endpoints (PLAN.md §7.3): scans and request parsing. Owned by Person C."""

from fastapi import APIRouter, BackgroundTasks

from app import schemas
from app.ai import request_parser, scans
from app.api.deps import DB, CurrentUser

router = APIRouter(tags=["ai"])


@router.post("/ai/parse-request", response_model=schemas.ParsedRequest)
def parse_request(body: schemas.ParseRequestBody, user: CurrentUser):
    return request_parser.parse_request(body.text)


@router.post("/scans", response_model=schemas.Scan, status_code=201)
def create_scan(body: schemas.ScanCreate, user: CurrentUser, db: DB, background: BackgroundTasks):
    scan = scans.create_scan(db, user, body, background)
    return scans.scan_out(db, scan)


@router.get("/scans/{scan_id}", response_model=schemas.Scan)
def get_scan(scan_id: int, user: CurrentUser, db: DB):
    scan = scans.get_own_scan(db, user, scan_id)
    scans.expire_if_stuck(db, scan)
    return scans.scan_out(db, scan)


@router.post("/scans/{scan_id}/publish", response_model=schemas.ScanPublishResponse)
def publish_scan(
    scan_id: int,
    body: schemas.ScanPublishBody,
    user: CurrentUser,
    db: DB,
    background: BackgroundTasks,
):
    return scans.publish_scan(db, user, scan_id, body, background)
