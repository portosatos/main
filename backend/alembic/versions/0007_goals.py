"""goals: daily targets with history

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GOAL_KIND = postgresql.ENUM("steps", "sleep", name="goal_kind", create_type=False)


def upgrade() -> None:
    GOAL_KIND.create(op.get_bind())
    op.create_table(
        "goals",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", GOAL_KIND, nullable=False),
        sa.Column("target", sa.REAL(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="goals_user_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="goals_pkey"),
    )
    op.create_index("ix_goals_user_id_kind_valid_from", "goals", ["user_id", "kind", "valid_from"])


def downgrade() -> None:
    op.drop_index("ix_goals_user_id_kind_valid_from", table_name="goals")
    op.drop_table("goals")
    GOAL_KIND.drop(op.get_bind())
