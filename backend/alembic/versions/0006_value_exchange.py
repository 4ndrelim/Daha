"""Value exchange: value snapshots on transactions, and a review flag on items. Additive only.

All columns are nullable, so existing rows and the demo seed are unchanged. Used only when
VALUE_EXCHANGE_ENABLED (and ITEM_VALUE_ENABLED) are on. Values are estimates; no money moves.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("value_usd", sa.Integer(), nullable=True))
    op.add_column("transactions", sa.Column("swap_value_usd", sa.Integer(), nullable=True))
    op.add_column(
        "items", sa.Column("value_flagged_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("items", "value_flagged_at")
    op.drop_column("transactions", "swap_value_usd")
    op.drop_column("transactions", "value_usd")
