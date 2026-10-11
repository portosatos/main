"""daily_summaries; ingest_jobs.dirty_dates: dates waiting for their summaries

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DAY_STATUS = postgresql.ENUM("no_data", "partial", "complete", name="day_status", create_type=False)


def upgrade() -> None:
    DAY_STATUS.create(op.get_bind())
    op.create_table(
        "daily_summaries",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("status", DAY_STATUS, nullable=False),
        sa.Column("wear_minutes", sa.Integer(), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.Column("active_minutes", sa.Integer(), nullable=True),
        sa.Column("sleep_minutes", sa.Integer(), nullable=True),
        sa.Column("sleep_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sleep_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("night_valid", sa.Boolean(), nullable=False),
        sa.Column("resting_hr", sa.REAL(), nullable=True),
        sa.Column("peak_hr", sa.REAL(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="daily_summaries_user_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "local_date", name="daily_summaries_pkey"),
    )
    op.add_column(
        "ingest_jobs",
        sa.Column(
            "dirty_dates",
            postgresql.ARRAY(sa.Date()),
            server_default=sa.text("'{}'::date[]"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("ingest_jobs", "dirty_dates")
    op.drop_table("daily_summaries")
    DAY_STATUS.drop(op.get_bind())
