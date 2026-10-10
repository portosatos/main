"""dev_clock: clock offset for APP_ENV=dev

Revision ID: 0001
Revises:
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dev_clock",
        sa.Column("id", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("offset_seconds", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint("id = 1", name="dev_clock_single_row"),
        sa.PrimaryKeyConstraint("id", name="dev_clock_pkey"),
    )


def downgrade() -> None:
    op.drop_table("dev_clock")
