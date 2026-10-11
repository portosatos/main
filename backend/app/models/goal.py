"""goals: the user's daily targets with history; goal_achievements: the dates a goal was met
(SPEC F8, §7.1).

A goals row is a version of one kind's target, in effect from `valid_from` on; without a row the
defaults of services/goals.py apply. Rows are only added, never changed.

An achievement is recorded once per kind and date, when a recompute first finds the goal met:
its primary key keeps a re-upload or a repeated recompute from notifying again.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import REAL, BigInteger, Date, DateTime, Enum, ForeignKey, Identity, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

GOAL_KIND = Enum("steps", "sleep", name="goal_kind")


class Goal(Base):
    __tablename__ = "goals"
    __table_args__ = (Index("ix_goals_user_id_kind_valid_from", "user_id", "kind", "valid_from"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(GOAL_KIND, nullable=False)
    # Steps a day, or hours of sleep.
    target: Mapped[float] = mapped_column(REAL, nullable=False)
    # From Clock: the moment of the change.
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GoalAchievement(Base):
    __tablename__ = "goal_achievements"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(GOAL_KIND, primary_key=True)
    local_date: Mapped[date] = mapped_column(Date, primary_key=True)
    # From Clock: when the recompute found it.
    achieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
