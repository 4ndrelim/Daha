"""items + scan detections: an optional estimated value in whole US dollars. Additive only.

Both columns are nullable, so existing items, scans and the demo seed are unchanged. The value
is for display (ITEM_VALUE_ENABLED); it is never used for points, karma or payments.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("items", sa.Column("value_usd", sa.Integer(), nullable=True))
    op.add_column("scan_detections", sa.Column("value_estimate_usd", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("scan_detections", "value_estimate_usd")
    op.drop_column("items", "value_usd")
