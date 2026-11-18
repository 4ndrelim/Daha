"""The text recipes we embed (PLAN.md C2)."""

from app.discovery.config import CATEGORY_LABELS
from app.models import Item, ItemRequest


def item_text(item: Item) -> str:
    label = CATEGORY_LABELS.get(item.category, item.category)
    return f"{item.name}. {label}. {item.description or ''}".strip()


def request_text(req: ItemRequest) -> str:
    attrs = ", ".join(f"{v}" for v in (req.attributes or {}).values())
    parts = [req.title, req.item_name or "", attrs, req.raw_text]
    return ". ".join(p for p in parts if p).strip()
