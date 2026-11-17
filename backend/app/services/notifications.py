"""In-app notifications (PLAN.md §7.5)."""

from sqlalchemy.orm import Session

from app.models import Notification


def notify(
    db: Session,
    user_id: int,
    type: str,
    title: str,
    body: str,
    link: str,
    actor_id: int | None = None,
    data: dict | None = None,
) -> None:
    """Add a notification row. The caller commits."""
    db.add(
        Notification(
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            link=link,
            actor_id=actor_id,
            data=data or {},
        )
    )
    db.flush()
