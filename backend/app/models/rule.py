"""rules: R1–R6 (seeded by migration 0010); user_rules: a user's switch of a rule;
recommendations: what the rules opened and closed (SPEC F9, §7.1).

A user without a user_rules row for a rule has it enabled. A recommendation is never deleted:
resolved and closed ones are the history. At most one recommendation of a (user, rule) pair is
open — the partial unique index keeps it so even if two evaluations race.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

RECOMMENDATION_STATUS = Enum(
    "open", "resolved", "closed_rule_disabled", name="recommendation_status"
)
RECOMMENDATION_FEEDBACK = Enum("useful", "not_useful", name="recommendation_feedback")
OPEN = text("status = 'open'")


class Rule(Base):
    __tablename__ = "rules"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # The thresholds, as in the rule's module (shown to the user, not edited by them).
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class UserRule(Base):
    __tablename__ = "user_rules"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    rule_code: Mapped[str] = mapped_column(ForeignKey("rules.code"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # From Clock.
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        Index(
            "uq_recommendations_open",
            "user_id",
            "rule_code",
            unique=True,
            postgresql_where=OPEN,
        ),
        Index("ix_recommendations_user_id_opened_at", "user_id", "opened_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rule_code: Mapped[str] = mapped_column(ForeignKey("rules.code"), nullable=False)
    status: Mapped[str] = mapped_column(RECOMMENDATION_STATUS, nullable=False)
    # From Clock.
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # The local date the rule was evaluated at when it fired.
    anchor_date: Mapped[date] = mapped_column(Date, nullable=False)
    # A snapshot of the values the rule fired on.
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 'auto' when the rule's close condition held.
    resolve_reason: Mapped[str | None] = mapped_column(Text)
    feedback: Mapped[str | None] = mapped_column(RECOMMENDATION_FEEDBACK)
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
