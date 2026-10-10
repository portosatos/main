"""Derived minute tables of a device (SPEC F4.3). A cache of the raw records: services/minutes.py
deletes and recomputes any minute range of them; `htadmin rebuild` recomputes them all.

`minute_utc` is the start of a UTC minute; the primary key (device_id, minute_utc) is the index
SPEC §4 asks for.
"""

import uuid
from datetime import datetime

from sqlalchemy import REAL, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class _DeviceMinute:
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    minute_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)


class StepsMinute(_DeviceMinute, Base):
    """Sum of the contributions of the device's step intervals to the minute: count × seconds of
    the overlap / seconds of the interval."""

    __tablename__ = "steps_minute"

    steps: Mapped[float] = mapped_column(REAL, nullable=False)


class SleepMinute(_DeviceMinute, Base):
    """The device's sleep intervals (as a union) cover at least 30 seconds of the minute."""

    __tablename__ = "sleep_minute"


class CoverageMinute(_DeviceMinute, Base):
    """Some raw record of the device (steps, sleep, pulse) overlaps the minute."""

    __tablename__ = "coverage_minute"
