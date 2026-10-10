"""Local dates by the user's time zone history (SPEC F5, ADR-009).

The only place that turns UTC instants into local dates and back. An instant belongs to the local
date of the zone in effect at that instant, so every instant has exactly one date: on the day of a
move nothing is lost or counted twice, and a day may last 17 or 31 hours or come in two pieces.
"""

from collections.abc import Iterable
from datetime import date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

UtcRange = tuple[datetime, datetime]


class TzRecord(Protocol):
    """A history entry: `tz` (IANA) is in effect from `valid_from` on. UserTimezone rows fit."""

    @property
    def tz(self) -> str: ...

    @property
    def valid_from(self) -> datetime: ...


class TzHistory:
    """A user's time zone history."""

    def __init__(self, records: Iterable[TzRecord]) -> None:
        raise NotImplementedError("step 4.1")

    def zone_at(self, ts: datetime) -> ZoneInfo:
        """The zone in effect at the instant `ts`."""
        raise NotImplementedError("step 4.1")

    def local_date(self, ts: datetime) -> date:
        """The local date of the instant `ts` in the zone in effect at `ts`."""
        raise NotImplementedError("step 4.1")

    def ranges_for_date(self, day: date) -> list[UtcRange]:
        """UTC ranges [start, end) of the instants dated `day`: sorted, never touching."""
        raise NotImplementedError("step 4.1")
