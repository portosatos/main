"""Local dates by the user's time zone history (SPEC F5, ADR-009, ADR-033).

The only place that turns UTC instants into local dates and back. An instant belongs to the local
date of the zone in effect at that instant, so every instant has exactly one date: on the day of a
move nothing is lost or counted twice, and a day may last 17 or 31 hours or come in two pieces.

The first zone of the history also covers everything before its `valid_from` (data recorded before
registration). A local day starts at the first instant of that date: 00:00, or the end of the gap
when the clock jumps over midnight (America/Santiago, 00:00 → 01:00).
"""

from bisect import bisect_right
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
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
        periods = [(_aware(r.valid_from, "valid_from").astimezone(UTC), r.tz) for r in records]
        if not periods:
            raise ValueError("time zone history is empty")
        periods.sort(key=lambda p: p[0])
        self._starts = [start for start, _ in periods]
        self._zones = [ZoneInfo(tz) for _, tz in periods]

    def zone_at(self, ts: datetime) -> ZoneInfo:
        """The zone in effect at the instant `ts`."""
        i = bisect_right(self._starts, _aware(ts, "ts")) - 1
        return self._zones[max(i, 0)]

    def local_date(self, ts: datetime) -> date:
        """The local date of the instant `ts` in the zone in effect at `ts`."""
        return ts.astimezone(self.zone_at(ts)).date()

    def ranges_for_date(self, day: date) -> list[UtcRange]:
        """UTC ranges [start, end) of the instants dated `day`: sorted, never touching."""
        next_day = day + timedelta(days=1)
        ranges: list[UtcRange] = []
        for i, zone in enumerate(self._zones):
            # Period i lasts from its valid_from (the first one: from the beginning of time) to
            # the next valid_from; inside it the day is [local midnight of day, of next day).
            start = _day_start(day, zone)
            end = _day_start(next_day, zone)
            if i > 0:
                start = max(start, self._starts[i])
            if i + 1 < len(self._starts):
                end = min(end, self._starts[i + 1])
            if start >= end:
                continue
            # Periods are in time order, so the pieces are too; glue the touching ones.
            if ranges and ranges[-1][1] >= start:
                ranges[-1] = (ranges[-1][0], end)
            else:
                ranges.append((start, end))
        return ranges


def _day_start(day: date, zone: ZoneInfo) -> datetime:
    # fold=0 is the earlier reading of an ambiguous 00:00; a 00:00 inside a gap is read with the
    # offset before the jump, which lands on the end of the gap: the first instant of `day`.
    return datetime.combine(day, time(0), tzinfo=zone).astimezone(UTC)


def _aware(ts: datetime, name: str) -> datetime:
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware, got {ts!r}")
    return ts
