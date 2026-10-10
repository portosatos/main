"""Gaps: time when a device writes nothing (SPEC F13, --gap, --gap-prob, --gap-max-hours).

Random gaps are drawn per (seed, date, device kind): a gap that starts on the date with
probability --gap-prob and lasts from 1 hour to --gap-max-hours. A gap may run into the next
dates, so a date also looks back at the gaps of earlier dates, even before the period: the same
seed gives the same gaps in any period. Gaps of one device never overlap and stay apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from htgen.profile import MINUTE, rng
from htgen.timeline import Timeline

Span = tuple[datetime, datetime]

MIN_GAP_MINUTES = 60
SEPARATION = timedelta(hours=1)  # between two random gaps of one device


@dataclass(frozen=True)
class Gap:
    start: datetime  # UTC
    end: datetime
    kind: str | None  # watch, phone or None: every device


def parse_gap(value: str, timeline: Timeline) -> Gap:
    """2026-10-03T00:00/2026-10-04T12:00@watch; a time without offset is local (timeline)."""
    period, _sep, kind = value.partition("@")
    first, sep, last = period.partition("/")
    if not sep:
        raise ValueError(f"ожидается НАЧАЛО/КОНЕЦ[@watch|@phone]: {value!r}")
    if kind not in ("", "watch", "phone"):
        raise ValueError(f"устройство пропуска — watch или phone: {value!r}")
    bounds = []
    for text in (first, last):
        moment = datetime.fromisoformat(text)
        bounds.append(timeline.localize(moment) if moment.tzinfo is None else moment)
    start, end = bounds
    if end <= start:
        raise ValueError(f"конец пропуска раньше начала: {value!r}")
    return Gap(start, end, kind or None)


class RandomGaps:
    def __init__(self, seed: int, timeline: Timeline, prob: float, max_hours: float) -> None:
        self.seed, self.timeline, self.prob = seed, timeline, prob
        self.longest = round(max_hours * 60)
        self.shortest = min(MIN_GAP_MINUTES, self.longest)

    def _drawn(self, day: date, kind: str) -> Span | None:
        """The gap that may start on the date, before the check against earlier gaps."""
        if self.prob <= 0:
            return None
        r = rng(self.seed, day, f"gap:{kind}")
        if r.random() >= self.prob:
            return None
        window = self.timeline.day_start(day), self.timeline.day_start(day + timedelta(days=1))
        size = (window[1] - window[0]) // MINUTE
        if size <= 0:
            return None
        start = window[0] + MINUTE * r.randrange(size)
        return start, start + MINUTE * r.randint(self.shortest, self.longest)

    def _earlier(self, day: date, moment: datetime) -> list[date]:
        """Earlier dates whose gaps could reach the moment."""
        reach = MINUTE * self.longest + SEPARATION
        days, back = [], day - timedelta(days=1)
        while self.timeline.day_start(back + timedelta(days=1)) + reach > moment:
            days.append(back)
            back -= timedelta(days=1)
        return days

    def _accepted(self, day: date, kind: str) -> Span | None:
        gap = self._drawn(day, kind)
        if gap is None:
            return None
        for earlier in self._earlier(day, gap[0]):
            other = self._drawn(earlier, kind)  # drawn, not accepted: no chain into the past
            if other is not None and other[1] + SEPARATION > gap[0]:
                return None
        return gap

    def touching(self, day: date, kind: str) -> list[Span]:
        """Gaps of the device that overlap the window of the date."""
        start = self.timeline.day_start(day)
        end = self.timeline.day_start(day + timedelta(days=1))
        gaps = [self._accepted(d, kind) for d in [day, *self._earlier(day, start)]]
        return [g for g in gaps if g is not None and g[0] < end and g[1] > start]


def subtract(spans: list[Span], holes: list[Span]) -> list[Span]:
    """Parts of the spans outside the holes."""
    for hole_start, hole_end in holes:
        rest: list[Span] = []
        for start, end in spans:
            if hole_end <= start or end <= hole_start:
                rest.append((start, end))
                continue
            if start < hole_start:
                rest.append((start, hole_start))
            if hole_end < end:
                rest.append((hole_end, end))
        spans = rest
    return spans
