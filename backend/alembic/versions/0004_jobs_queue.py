"""jobs queue, worker heartbeat, ingest progress and checkpoint

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_STATUS = postgresql.ENUM(
    "queued", "running", "done", "failed", name="job_status", create_type=False
)
QUEUED = sa.text("status = 'queued'")


def upgrade() -> None:
    JOB_STATUS.create(op.get_bind())
    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", JOB_STATUS, server_default=sa.text("'queued'"), nullable=False),
        sa.Column("dedup_key", sa.Text(), nullable=True),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="jobs_user_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="jobs_pkey"),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_queued", "jobs", ["id"], postgresql_where=QUEUED)
    op.create_index(
        "jobs_dedup_key_queued_key", "jobs", ["dedup_key"], unique=True, postgresql_where=QUEUED
    )
    op.create_table(
        "worker_heartbeat",
        sa.Column("worker_id", sa.Text(), nullable=False),
        sa.Column("beat_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("worker_id", name="worker_heartbeat_pkey"),
    )

    op.add_column("ingest_jobs", sa.Column("file_path", sa.Text(), nullable=True))
    for column in ("bytes_total", "bytes_done"):
        op.add_column(
            "ingest_jobs",
            sa.Column(column, sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        )
    op.add_column(
        "ingest_jobs",
        sa.Column("lines_done", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "ingest_jobs",
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    for column in ("warnings", "lines_done", "bytes_done", "bytes_total", "file_path"):
        op.drop_column("ingest_jobs", column)
    op.drop_table("worker_heartbeat")
    op.drop_index("jobs_dedup_key_queued_key", table_name="jobs")
    op.drop_index("ix_jobs_queued", table_name="jobs")
    op.drop_index("ix_jobs_user_id", table_name="jobs")
    op.drop_table("jobs")
    JOB_STATUS.drop(op.get_bind())
