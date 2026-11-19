"""transactions: condition check (handoff + return photos, the AI's result). Additive only.

Every new column is nullable (or has a default), so existing transactions and the demo seed are
unchanged. Photos are upload ids; they are deleted when the exchange ends and only the result
text is kept.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("transactions", sa.Column("condition_handoff_photos", JSONB(), nullable=True))
    op.add_column("transactions", sa.Column("condition_handoff_confirmed_at", TS, nullable=True))
    op.add_column("transactions", sa.Column("condition_return_photos", JSONB(), nullable=True))
    op.add_column("transactions", sa.Column("condition_status", sa.Text(), nullable=True))
    op.add_column("transactions", sa.Column("condition_result", sa.Text(), nullable=True))
    op.add_column("transactions", sa.Column("condition_note", sa.Text(), nullable=True))
    op.add_column(
        "transactions",
        sa.Column("condition_sample", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("transactions", sa.Column("condition_checked_at", TS, nullable=True))
    op.add_column("transactions", sa.Column("condition_photos_deleted_at", TS, nullable=True))


def downgrade() -> None:
    for column in (
        "condition_photos_deleted_at",
        "condition_checked_at",
        "condition_sample",
        "condition_note",
        "condition_result",
        "condition_status",
        "condition_return_photos",
        "condition_handoff_confirmed_at",
        "condition_handoff_photos",
    ):
        op.drop_column("transactions", column)
