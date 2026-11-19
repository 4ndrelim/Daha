"""What a vision provider returns (before normalization). PLAN.md C1.1."""

from typing import Literal

from pydantic import BaseModel, Field

CategoryLit = Literal[
    "academic",
    "tech",
    "clothing",
    "dorm",
    "consumables",
    "sports",
    "moving",
    "events",
    "services",
    "other",
]
ConditionLit = Literal["new", "like_new", "good", "fair", "worn"]
TxTypeLit = Literal["lend", "give", "exchange"]


class DetectedItemRaw(BaseModel):
    name: str
    category: CategoryLit = "other"
    description: str = ""
    quantity: int = 1
    condition_guess: ConditionLit | None = None
    confidence: float = 0.5
    bbox: list[float] | None = None  # [x, y, w, h] normalized 0..1
    suggested_share: bool = True
    sensitive_reason: str | None = None
    suggested_transaction_type: TxTypeLit = "lend"
    value_usd: int | None = None  # the AI's estimated new price in whole US dollars, or null


class DetectionPayload(BaseModel):
    items: list[DetectedItemRaw] = Field(default_factory=list)


class ProviderResult(BaseModel):
    items: list[DetectedItemRaw]
    latency_ms: int
    cost_usd: float | None
    raw: dict
