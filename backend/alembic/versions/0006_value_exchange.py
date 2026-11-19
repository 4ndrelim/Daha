"""Value exchange: the item's estimated value stored on completed transactions. Additive only.

The column is nullable, so existing rows and the demo seed are unchanged. Used only when
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


def downgrade() -> None:
    op.drop_column("transactions", "value_usd")
