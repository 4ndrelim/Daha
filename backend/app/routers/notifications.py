import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select, update

from app import schemas
from app.api.deps import DB, CurrentUser
from app.core.security import decode_token
from app.models import Event, Notification, User
from app.services import serializers

router = APIRouter(tags=["notifications"])
log = logging.getLogger(__name__)
_optional_bearer = HTTPBearer(auto_error=False)
MAX_EVENTS_PER_CALL = 100


@router.get("/notifications", response_model=list[schemas.Notification])
def list_notifications(
    user: CurrentUser,
    db: DB,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    rows = (
        db.execute(
            query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
        )
        .scalars()
        .all()
    )
    refs = serializers.user_refs(db, {n.actor_id for n in rows if n.actor_id is not None})
    return [
        schemas.Notification(
            id=n.id,
            type=n.type,
            title=n.title,
            body=n.body,
            link=n.link,
            actor=refs.get(n.actor_id) if n.actor_id is not None else None,
            read=n.read_at is not None,
            created_at=n.created_at,
        )
        for n in rows
    ]


@router.get("/notifications/unread-count", response_model=schemas.UnreadCounts)
def unread_count(user: CurrentUser, db: DB):
    return serializers.unread_counts(db, user.id)


@router.post("/notifications/read", status_code=204)
def mark_notifications_read(body: schemas.MarkReadBody, user: CurrentUser, db: DB):
    stmt = (
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=func.now())
    )
    if not body.all:
        if not body.ids:
            return Response(status_code=204)
        stmt = stmt.where(Notification.id.in_(body.ids))
    db.execute(stmt)
    db.commit()
    return Response(status_code=204)


@router.post("/events", status_code=204)
def post_events(
    body: schemas.EventsBody,
    db: DB,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_optional_bearer)] = None,
):
    """Product analytics. Never fails the client: bad tokens and DB errors are swallowed."""
    try:
        user_id = decode_token(creds.credentials) if creds else None
        if user_id is not None and db.get(User, user_id) is None:
            user_id = None
        for e in body.events[:MAX_EVENTS_PER_CALL]:
            payload = dict(e.payload or {})
            if e.ts is not None:
                payload["client_ts"] = e.ts.isoformat()
            db.add(Event(user_id=user_id, type=e.type[:80], payload=payload))
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        log.warning("dropping analytics events", exc_info=True)
    return Response(status_code=204)
