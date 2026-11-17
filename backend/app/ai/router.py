"""AI endpoints (PLAN.md §7.3). P0-A ships 501 stubs; Person C owns this file from now on."""

from fastapi import APIRouter, HTTPException

from app import schemas

router = APIRouter(tags=["ai"])


@router.post("/ai/parse-request", response_model=schemas.ParsedRequest)
def parse_request(body: schemas.ParseRequestBody):
    raise HTTPException(501, "not implemented")


@router.post("/scans", response_model=schemas.Scan, status_code=201)
def create_scan(body: schemas.ScanCreate):
    raise HTTPException(501, "not implemented")


@router.get("/scans/{scan_id}", response_model=schemas.Scan)
def get_scan(scan_id: int):
    raise HTTPException(501, "not implemented")


@router.post("/scans/{scan_id}/publish", response_model=schemas.ScanPublishResponse)
def publish_scan(scan_id: int, body: schemas.ScanPublishBody):
    raise HTTPException(501, "not implemented")
