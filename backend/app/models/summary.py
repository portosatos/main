"""daily_summaries: metrics of a user's local date (SPEC F6, F7, §7.1).

Derived like the minute tables: services/summaries.py recomputes any date from the raw records'
minutes, and a no_data date has no row.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import REAL, Boolean, Date, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

DAY_STATUS = Enum("no_data", "partial", "complete", name="day_status")


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    local_date: Mapped[date] = mapped_column(Date, primary_key=True)
    status: Mapped[str] = mapped_column(DAY_STATUS, nullable=False)
    wear_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    steps: Mapped[int | None] = mapped_column(Integer)
    active_minutes: Mapped[int | None] = mapped_column(Integer)
    # Sessions that ended on this date (the wake day); start and end of the main session.
    sleep_minutes: Mapped[int | None] = mapped_column(Integer)
    sleep_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sleep_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    night_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    resting_hr: Mapped[float | None] = mapped_column(REAL)
    peak_hr: Mapped[float | None] = mapped_column(REAL)
    # From Clock: when the row was computed.
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
