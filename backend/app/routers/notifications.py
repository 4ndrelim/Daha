from fastapi import APIRouter

from app import schemas
from app.routers._stub import not_implemented

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=list[schemas.Notification])
def list_notifications(unread_only: bool = False, limit: int = 50):
    not_implemented()


@router.get("/notifications/unread-count", response_model=schemas.UnreadCounts)
def unread_count():
    not_implemented()


@router.post("/notifications/read", status_code=204)
def mark_notifications_read(body: schemas.MarkReadBody):
    not_implemented()


@router.post("/events", status_code=204)
def post_events(body: schemas.EventsBody):
    not_implemented()
