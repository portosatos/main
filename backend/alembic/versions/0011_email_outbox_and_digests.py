"""email_outbox and email_digests: the digest of opened recommendations (SPEC F10, §7.1)

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-11

At most one sent digest per user and local date (uq_email_digests_sent) and at most one planned,
not yet sent, per user (uq_email_digests_planned, ADR-050).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLAN_REASON = postgresql.ENUM(
    "window",
    "max_delay",
    "daily_limit",
    "quiet_hours",
    name="digest_plan_reason",
    create_type=False,
)
OUTBOX_STATUS = postgresql.ENUM(
    "pending", "sent", "skipped", name="email_outbox_status", create_type=False
)


def upgrade() -> None:
    PLAN_REASON.create(op.get_bind())
    OUTBOX_STATUS.create(op.get_bind())
    op.create_table(
        "email_digests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("to_email", sa.Text(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("plan_reason", PLAN_REASON, nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="email_digests_user_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="email_digests_pkey"),
    )
    op.create_index(
        "ix_email_digests_user_id_planned_at", "email_digests", ["user_id", "planned_at"]
    )
    op.create_index(
        "uq_email_digests_planned",
        "email_digests",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("sent_at IS NULL"),
    )
    op.create_index(
        "uq_email_digests_sent",
        "email_digests",
        ["user_id", "local_date"],
        unique=True,
        postgresql_where=sa.text("sent_at IS NOT NULL"),
    )

    op.create_table(
        "email_outbox",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", OUTBOX_STATUS, nullable=False),
        sa.Column("digest_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["digest_id"],
            ["email_digests.id"],
            name="email_outbox_digest_id_fkey",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["recommendations.id"],
            name="email_outbox_recommendation_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="email_outbox_user_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="email_outbox_pkey"),
        sa.UniqueConstraint("recommendation_id", name="email_outbox_recommendation_id_key"),
    )
    op.create_index(
        "ix_email_outbox_pending",
        "email_outbox",
        ["user_id"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("ix_email_outbox_pending", table_name="email_outbox")
    op.drop_table("email_outbox")
    op.drop_index("uq_email_digests_sent", table_name="email_digests")
    op.drop_index("uq_email_digests_planned", table_name="email_digests")
    op.drop_index("ix_email_digests_user_id_planned_at", table_name="email_digests")
    op.drop_table("email_digests")
    OUTBOX_STATUS.drop(op.get_bind())
    PLAN_REASON.drop(op.get_bind())
