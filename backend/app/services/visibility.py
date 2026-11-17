"""The one visibility rule (PLAN.md §7.4). Stubs in P0-A; implemented in A1."""

from sqlalchemy.orm import Session

from app.services.viewer import ViewerContext


def item_visible_clause(viewer: ViewerContext):
    """SQLAlchemy boolean clause for .where(): owner OR audience match; excludes archived."""
    raise NotImplementedError("item_visible_clause arrives in A1")


def request_visible_clause(viewer: ViewerContext):
    raise NotImplementedError("request_visible_clause arrives in A1")


def user_can_view_request(db: Session, user_id: int, request_id: int) -> bool:
    raise NotImplementedError("user_can_view_request arrives in A1")
