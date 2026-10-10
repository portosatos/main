"""steps_minute, sleep_minute, coverage_minute: derived minute tables of a device

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def minute_columns(table: str) -> list[sa.Column | sa.Constraint]:
    return [
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("minute_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], name=f"{table}_device_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("device_id", "minute_utc", name=f"{table}_pkey"),
    ]


def upgrade() -> None:
    op.create_table(
        "steps_minute",
        *minute_columns("steps_minute"),
        sa.Column("steps", sa.REAL(), nullable=False),
    )
    op.create_table("sleep_minute", *minute_columns("sleep_minute"))
    op.create_table("coverage_minute", *minute_columns("coverage_minute"))


def downgrade() -> None:
    op.drop_table("coverage_minute")
    op.drop_table("sleep_minute")
    op.drop_table("steps_minute")
