"""Time zone history of the generated person: --tz and --tz-change (SPEC F13).

Every timestamp gets the offset of the zone in effect at that moment. A local date lasts from
the first moment of that date to the first moment of the next one, so the day of a move is
longer or shorter than 24 hours (Moscow -> New York: 31 h) and nothing is lost or doubled.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo


class Timeline:
    def __init__(self, tz: str, changes: Sequence[tuple[datetime, str]] = ()) -> None:
        ordered = sorted(changes, key=lambda change: change[0])
        self._since = [moment.astimezone(UTC) for moment, _zone in ordered]
        self._zones = [ZoneInfo(tz), *(ZoneInfo(zone) for _moment, zone in ordered)]

    def _segments(self) -> list[tuple[datetime | None, datetime | None, ZoneInfo]]:
        """(since, until, zone); None is an open end."""
        bounds: list[datetime | None] = [None, *self._since, None]
        return [(bounds[i], bounds[i + 1], zone) for i, zone in enumerate(self._zones)]

    def zone_at(self, moment: datetime) -> ZoneInfo:
        return self._zones[bisect_right(self._since, moment)]

    def iso(self, moment: datetime) -> str:
        """2026-10-01T08:00:30+03:00: seconds precision, offset of the zone at that moment."""
        return moment.astimezone(self.zone_at(moment)).isoformat(timespec="seconds")

    def local_date(self, moment: datetime) -> date:
        return moment.astimezone(self.zone_at(moment)).date()

    def day_start(self, day: date) -> datetime:
        """The first moment (UTC) whose local date is `day` or later."""
        candidates = []
        for since, until, zone in self._segments():
            moment = datetime.combine(day, time(0), tzinfo=zone).astimezone(UTC)
            if since is not None:
                moment = max(moment, since)
            if until is None or moment < until:
                candidates.append(moment)
        return min(candidates)

    def localize(self, wall: datetime) -> datetime:
        """A wall-clock time without offset read in the zone in effect at that time (UTC)."""
        readings = []
        for since, until, zone in self._segments():
            moment = wall.replace(tzinfo=zone).astimezone(UTC)
            if (since is None or since <= moment) and (until is None or moment < until):
                return moment
            if since is None or since <= moment:
                readings.append(moment)
        return readings[-1]  # a wall time skipped by a move east: read in the newer zone
