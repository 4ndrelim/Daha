"""In-app notifications (PLAN.md §7.5). Stub in P0-A; implemented in A3."""

from sqlalchemy.orm import Session


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
    raise NotImplementedError("notify arrives in A3")
