"""Model → schema converters, batched (never N+1). Stubs in P0-A; implemented in A1."""

from sqlalchemy.orm import Session

from app import schemas
from app.models import Community, Item, ItemRequest, User
from app.services.viewer import ViewerContext


def item_cards(
    db: Session,
    items: list[Item],
    viewer: ViewerContext,
    scores: dict[int, tuple[float, str]] | None = None,
) -> list[schemas.ItemCard]:
    raise NotImplementedError("item_cards arrives in A1")


def item_detail(db: Session, item: Item, viewer: ViewerContext) -> schemas.ItemDetail:
    raise NotImplementedError("item_detail arrives in A1")


def request_cards(
    db: Session, reqs: list[ItemRequest], viewer: ViewerContext
) -> list[schemas.RequestCard]:
    raise NotImplementedError("request_cards arrives in A1")


def community_out(db: Session, c: Community, viewer: ViewerContext) -> schemas.Community:
    raise NotImplementedError("community_out arrives in A1")


def user_ref(db: Session, user: User) -> schemas.UserRef:
    raise NotImplementedError("user_ref arrives in A1")
