"""goals: the user's daily targets with history (SPEC F8, §7.1).

A row is a version of one kind's target, in effect from `valid_from` on; without a row the
defaults of services/goals.py apply. Rows are only added, never changed.
"""

import uuid
from datetime import datetime

from sqlalchemy import REAL, BigInteger, DateTime, Enum, ForeignKey, Identity, Index
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
