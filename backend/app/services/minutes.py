"""Derived minute tables of a device: steps_minute, sleep_minute, coverage_minute (SPEC F4.3).

They are a cache of the raw records: the rows of a minute range are deleted and computed again
from steps_raw, sleep_raw and hr_point, so a recompute is idempotent and a full rebuild equals
the incremental result.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession


class DirtyMinutes:
    """Minute ranges [start, end) of each device whose derived rows are stale."""

    def add(self, device_id: uuid.UUID, start: datetime, end: datetime) -> None:
        """Mark the minutes that the record span [start, end) touches."""
        raise NotImplementedError("step 3.3")

    def add_point(self, device_id: uuid.UUID, ts: datetime) -> None:
        """Mark the minute of the instant `ts`."""
        raise NotImplementedError("step 3.3")

    def ranges(self) -> list[tuple[uuid.UUID, datetime, datetime]]:
        """Merged ranges, sorted by device and start."""
        raise NotImplementedError("step 3.3")


@dataclass(frozen=True, slots=True)
class RebuildResult:
    devices: int
    steps_minutes: int
    sleep_minutes: int
    coverage_minutes: int


async def recompute(session: AsyncSession, dirty: DirtyMinutes) -> None:
    """Delete the derived rows of the dirty ranges and insert them computed from raw records."""
    raise NotImplementedError("step 3.3")


async def rebuild_user(session: AsyncSession, user_id: uuid.UUID) -> RebuildResult:
    """Drop every derived minute row of the user's devices and compute them from raw records."""
    raise NotImplementedError("step 3.3")
