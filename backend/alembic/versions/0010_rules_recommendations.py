"""rules (seed R1–R6), user_rules, recommendations

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-11

The seed is a frozen copy of services/rules/catalog.py as of step 8.1
(test_rules_seeded_r1_to_r6_with_params_from_code keeps them equal); a later change of a title,
a description or a threshold comes with a migration of its own.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RECOMMENDATION_STATUS = postgresql.ENUM(
    "open", "resolved", "closed_rule_disabled", name="recommendation_status", create_type=False
)
RECOMMENDATION_FEEDBACK = postgresql.ENUM(
    "useful", "not_useful", name="recommendation_feedback", create_type=False
)

RULES = [
    {
        "code": "R1",
        "title": "Недосып",
        "description": "Три валидные ночи подряд, в каждой меньше 6 ч сна. Закрывается сама после"
        " валидной ночи с 7 ч сна и больше.",
        "params": {"nights": 3, "short_hours": 6, "close_hours": 7},
        "sort_order": 1,
    },
    {
        "code": "R2",
        "title": "Мало шагов",
        "description": "Три полных дня подряд, в каждый меньше половины цели по шагам. Закрывается"
        " сама после полного дня с выполненной целью.",
        "params": {"days": 3, "goal_share": 0.5},
        "sort_order": 2,
    },
    {
        "code": "R3",
        "title": "Повышенный пульс в покое",
        "description": "Два дня подряд пульс в покое на 7 уд/мин и больше выше базы — среднего за"
        " 14 дней до них (нужно не меньше 7 значений). Закрывается сама, когда пульс в покое ниже"
        " базы + 4.",
        "params": {
            "days": 2,
            "baseline_days": 14,
            "baseline_min_values": 7,
            "rise_bpm": 7,
            "close_bpm": 4,
        },
        "sort_order": 3,
    },
    {
        "code": "R4",
        "title": "Сон хуже, чем на прошлой неделе",
        "description": "Средний сон за прошлую неделю меньше, чем за позапрошлую, на 60 мин и"
        " больше (в каждой неделе не меньше 5 валидных ночей). Закрывается сама, когда разница"
        " меньше 30 мин.",
        "params": {"min_nights": 5, "drop_minutes": 60, "close_minutes": 30},
        "sort_order": 4,
    },
    {
        "code": "R5",
        "title": "Нерегулярный отбой",
        "description": "Стандартное отклонение времени отбоя за последние 7 ночей больше 90 мин"
        " (нужно не меньше 5 валидных ночей из 7). Закрывается сама, когда оно меньше 60 мин.",
        "params": {"nights": 7, "min_nights": 5, "stdev_minutes": 90, "close_minutes": 60},
        "sort_order": 5,
    },
    {
        "code": "R6",
        "title": "Нет активности",
        "description": "Пять полных дней подряд, в каждый меньше 15 активных минут. Закрывается"
        " сама после полного дня с 15 активными минутами и больше.",
        "params": {"days": 5, "active_minutes": 15},
        "sort_order": 6,
    },
]


def upgrade() -> None:
    rules = op.create_table(
        "rules",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("code", name="rules_pkey"),
    )
    op.bulk_insert(rules, RULES)

    op.create_table(
        "user_rules",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rule_code", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="user_rules_user_id_fkey", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["rule_code"], ["rules.code"], name="user_rules_rule_code_fkey"),
        sa.PrimaryKeyConstraint("user_id", "rule_code", name="user_rules_pkey"),
    )

    RECOMMENDATION_STATUS.create(op.get_bind())
    RECOMMENDATION_FEEDBACK.create(op.get_bind())
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rule_code", sa.Text(), nullable=False),
        sa.Column("status", RECOMMENDATION_STATUS, nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anchor_date", sa.Date(), nullable=False),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolve_reason", sa.Text(), nullable=True),
        sa.Column("feedback", RECOMMENDATION_FEEDBACK, nullable=True),
        sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="recommendations_user_id_fkey", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["rule_code"], ["rules.code"], name="recommendations_rule_code_fkey"
        ),
        sa.PrimaryKeyConstraint("id", name="recommendations_pkey"),
    )
    op.create_index(
        "uq_recommendations_open",
        "recommendations",
        ["user_id", "rule_code"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )
    op.create_index(
        "ix_recommendations_user_id_opened_at", "recommendations", ["user_id", "opened_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_recommendations_user_id_opened_at", table_name="recommendations")
    op.drop_index("uq_recommendations_open", table_name="recommendations")
    op.drop_table("recommendations")
    RECOMMENDATION_FEEDBACK.drop(op.get_bind())
    RECOMMENDATION_STATUS.drop(op.get_bind())
    op.drop_table("user_rules")
    op.drop_table("rules")
