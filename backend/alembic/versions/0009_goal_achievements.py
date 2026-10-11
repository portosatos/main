"""goal_achievements: the dates a goal was met

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GOAL_KIND = postgresql.ENUM("steps", "sleep", name="goal_kind", create_type=False)


def upgrade() -> None:
    op.create_table(
        "goal_achievements",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", GOAL_KIND, nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="goal_achievements_user_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "kind", "local_date", name="goal_achievements_pkey"),
    )


def downgrade() -> None:
    op.drop_table("goal_achievements")
