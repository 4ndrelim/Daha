"""transactions: the agreed handoff time and the current "time & place" suggestion. Additive.

Both columns are nullable, so existing transactions and the demo seed are unchanged.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions", sa.Column("pickup_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("transactions", sa.Column("handoff_suggestion", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("transactions", "handoff_suggestion")
    op.drop_column("transactions", "pickup_at")
