"""devices, ingest_jobs, steps_raw, sleep_raw, hr_point: raw telemetry and its origin

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEVICE_KIND = postgresql.ENUM("watch", "phone", name="device_kind", create_type=False)
INGEST_SOURCE = postgresql.ENUM("file", "stream", name="ingest_source", create_type=False)
INGEST_STATUS = postgresql.ENUM(
    "queued", "processing", "done", "failed", name="ingest_status", create_type=False
)
ENUMS = (DEVICE_KIND, INGEST_SOURCE, INGEST_STATUS)


def origin_columns(table: str) -> list[sa.Column | sa.ForeignKeyConstraint]:
    """ingest_job_id and ingested_at of a raw table (SPEC F4.1)."""
    return [
        sa.Column("ingest_job_id", sa.Uuid(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ingest_job_id"], ["ingest_jobs.id"], name=f"{table}_ingest_job_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], name=f"{table}_device_id_fkey", ondelete="CASCADE"
        ),
    ]


def upgrade() -> None:
    # btree_gist: `device_id WITH =` inside the GiST exclusion constraint of steps_raw (SPEC F4.1).
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    bind = op.get_bind()
    for enum in ENUMS:
        enum.create(bind)

    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("kind", DEVICE_KIND, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="devices_user_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="devices_pkey"),
        sa.UniqueConstraint("user_id", "external_id", name="devices_user_id_external_id_key"),
    )
    op.create_table(
        "ingest_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source", INGEST_SOURCE, nullable=False),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("status", INGEST_STATUS, server_default=sa.text("'queued'"), nullable=False),
        sa.Column("records_total", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("records_new", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("records_duplicate", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("records_conflict", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("records_invalid", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "errors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="ingest_jobs_user_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="ingest_jobs_pkey"),
    )
    op.create_index("ix_ingest_jobs_user_id", "ingest_jobs", ["user_id"])

    op.create_table(
        "steps_raw",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        *origin_columns("steps_raw"),
        sa.PrimaryKeyConstraint("device_id", "start_utc", "end_utc", name="steps_raw_pkey"),
        sa.CheckConstraint("end_utc > start_utc", name="steps_raw_positive_interval"),
        sa.CheckConstraint("count >= 0", name="steps_raw_count_not_negative"),
        postgresql.ExcludeConstraint(
            ("device_id", "="),
            (sa.text("tstzrange(start_utc, end_utc, '[)')"), "&&"),
            using="gist",
            name="steps_raw_no_overlap",
        ),
    )
    op.create_table(
        "sleep_raw",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_utc", sa.DateTime(timezone=True), nullable=False),
        *origin_columns("sleep_raw"),
        sa.PrimaryKeyConstraint("device_id", "start_utc", "end_utc", name="sleep_raw_pkey"),
        sa.CheckConstraint("end_utc > start_utc", name="sleep_raw_positive_interval"),
    )
    op.create_table(
        "hr_point",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("ts_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bpm", sa.SmallInteger(), nullable=False),
        *origin_columns("hr_point"),
        sa.PrimaryKeyConstraint("device_id", "ts_utc", name="hr_point_pkey"),
        sa.CheckConstraint("bpm BETWEEN 30 AND 230", name="hr_point_bpm_range"),
    )


def downgrade() -> None:
    op.drop_table("hr_point")
    op.drop_table("sleep_raw")
    op.drop_table("steps_raw")
    op.drop_index("ix_ingest_jobs_user_id", table_name="ingest_jobs")
    op.drop_table("ingest_jobs")
    op.drop_table("devices")
    bind = op.get_bind()
    for enum in reversed(ENUMS):
        enum.drop(bind)
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
