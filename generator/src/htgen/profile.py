"""Daily profile of one local date: sleep, walks, sitting periods and light activity per minute.

Every random choice comes from a generator seeded by (seed, date, purpose), so a date looks the
same in any period that contains it. A date owns the wall-clock window [00:00, 24:00) local:
the end of the previous night and the start of the next one are taken from the nights' own seeds.
With a time zone change the window is longer or shorter than 24 hours (htgen.timeline); times of
day inside it count from its start.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from htgen.scenarios import NONE, Scenarios
from htgen.timeline import Timeline

SLEEP, SITTING, LIGHT, WALK = range(4)
MINUTE = timedelta(minutes=1)

BED_MINUTES = (-90, 30)  # bedtime relative to the local midnight: 22:30..00:30
SLEEP_MINUTES = (390, 510)  # 6.5..8.5 h
PHONE_SLEEP_ERROR = 20  # minutes, each boundary
WALKS = (1, 2, 2, 3)
WALK_MINUTES = (15, 60)
WALK_CADENCE = (95.0, 125.0)  # steps per minute
WALK_PHONE_RATIO = (0.91, 0.96)  # phone counts 90-97 % of the watch steps on a walk
OTHER_PHONE_RATIO = (0.4, 0.8)  # the phone is not always in a pocket
SITTINGS = (2, 3)
SITTING_MINUTES = (60, 150)
LIGHT_ACTIVE_SHARE = 0.3
LIGHT_CADENCE = (5.0, 40.0)
SEDENTARY_LIGHT_SHARE = 0.1
SEDENTARY_LIGHT_CADENCE = (5.0, 25.0)
BRISK_WALK_MINUTES = (60, 90)
BRISK_CADENCE = (110.0, 120.0)  # every minute >= 100 steps: active (SPEC F7)
PLACEMENT_TRIES = 50


def rng(seed: int, day: date, purpose: str) -> random.Random:
    """Seeding with a str is stable across platforms and Python versions (sha512)."""
    return random.Random(f"htgen:{seed}:{day.isoformat()}:{purpose}")


@dataclass(frozen=True)
class Night:
    """The night that ends on the morning of its date (UTC instants)."""

    bed: datetime
    wake: datetime
    phone_bed: datetime
    phone_wake: datetime


def night(seed: int, wake_day: date, timeline: Timeline, scenarios: Scenarios = NONE) -> Night:
    r = rng(seed, wake_day, "night")
    bed_minutes, sleep_minutes = r.randint(*BED_MINUTES), r.randint(*SLEEP_MINUTES)
    error = (-PHONE_SLEEP_ERROR, PHONE_SLEEP_ERROR)
    phone_bed_error, phone_wake_error = r.randint(*error), r.randint(*error)
    s = rng(seed, wake_day, "scenario:night")
    scenario_bed = scenarios.bed_minutes(wake_day, s)
    if scenario_bed is not None:
        bed_minutes = scenario_bed
    if (scenario_sleep := scenarios.sleep_minutes(wake_day)) is not None:
        sleep_minutes = s.randint(*scenario_sleep)
    bed = timeline.day_start(wake_day) + MINUTE * bed_minutes
    wake = bed + MINUTE * sleep_minutes
    return Night(bed, wake, bed + MINUTE * phone_bed_error, wake + MINUTE * phone_wake_error)


@dataclass(frozen=True)
class DayProfile:
    day: date
    start: datetime  # the first moment of the date (local midnight), UTC
    end: datetime  # the first moment of the next date, UTC
    state: list[int]  # per minute of the window
    cadence: list[float]  # true steps per minute
    phone_ratio: list[float]  # share of the true steps the phone counts
    sleep: list[tuple[datetime, datetime]]  # watch sleep inside the window
    phone_sleep: list[tuple[datetime, datetime]]
    resting_hr: float

    def minute(self, moment: datetime) -> int:
        return int((moment - self.start).total_seconds() // 60)

    def awake_segments(self) -> list[tuple[datetime, datetime]]:
        segments: list[tuple[datetime, datetime]] = []
        begin: int | None = None
        for i, state in enumerate([*self.state, SLEEP]):
            if state != SLEEP and begin is None:
                begin = i
            elif state == SLEEP and begin is not None:
                segments.append((self.start + MINUTE * begin, self.start + MINUTE * i))
                begin = None
        return segments

    def steps_between(self, start: datetime, end: datetime, phone: bool = False) -> float:
        """True steps in [start, end): the cadence of each minute is spread evenly over it."""
        total = 0.0
        i = self.minute(start)
        while i < len(self.state):
            lo = max(start, self.start + MINUTE * i)
            hi = min(end, self.start + MINUTE * (i + 1))
            if lo >= end:
                break
            share = (hi - lo).total_seconds() / 60
            total += self.cadence[i] * share * (self.phone_ratio[i] if phone else 1.0)
            i += 1
        return total


def _merge(spans: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Nights of a short day (a move east) may overlap; a device never writes overlapping sleep."""
    merged: list[tuple[datetime, datetime]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _clip(
    spans: list[tuple[datetime, datetime]], lo: datetime, hi: datetime
) -> list[tuple[datetime, datetime]]:
    return [(max(s, lo), min(e, hi)) for s, e in _merge(spans) if s < hi and e > lo]


def plan_day(seed: int, day: date, timeline: Timeline, scenarios: Scenarios = NONE) -> DayProfile:
    start = timeline.day_start(day)
    end = timeline.day_start(day + timedelta(days=1))
    size = int((end - start).total_seconds() // 60)
    nights = [night(seed, d, timeline, scenarios) for d in (day, day + timedelta(days=1))]

    state = [LIGHT] * size
    for n in nights:
        for i in range(max(0, (n.bed - start) // MINUTE), min(size, (n.wake - start) // MINUTE)):
            state[i] = SLEEP

    def at(hour: int, minute: int = 0) -> int:
        """Minutes from the start of the window (wall clock time when the zone does not change)."""
        return min(hour * 60 + minute, size)

    def place(r: random.Random, length: int, earliest: int, latest: int) -> range | None:
        """A free (LIGHT) block of `length` minutes starting in [earliest, latest - length]."""
        if latest - length < earliest:
            return None  # a short day of a move east
        for _ in range(PLACEMENT_TRIES):
            first = r.randint(earliest, latest - length)
            block = range(max(0, first - 1), min(size, first + length + 1))  # keep a gap
            if all(state[i] == LIGHT for i in block):
                return range(first, first + length)
        return None

    r = rng(seed, day, "activity")
    cadence = [0.0] * size
    phone_ratio = [r.uniform(*OTHER_PHONE_RATIO) for _ in range(size)]

    def walk(r: random.Random, minutes: tuple[int, int], pace: tuple[float, float]) -> None:
        block = place(r, r.randint(*minutes), at(7), at(21, 30))
        if block is None:
            return
        tempo, ratio = r.uniform(*pace), r.uniform(*WALK_PHONE_RATIO)
        for i in block:
            state[i] = WALK
            cadence[i] = min(max(tempo + r.uniform(-5, 5), WALK_CADENCE[0]), WALK_CADENCE[1])
            phone_ratio[i] = ratio

    sedentary = scenarios.sedentary(day)
    if scenarios.brisk_walk(day):
        walk(rng(seed, day, "scenario:activity"), BRISK_WALK_MINUTES, BRISK_CADENCE)
    for _ in range(0 if sedentary else r.choice(WALKS)):
        walk(r, WALK_MINUTES, WALK_CADENCE)
    for _ in range(r.randint(*SITTINGS)):
        sitting = place(r, r.randint(*SITTING_MINUTES), at(8, 30), at(20))
        for i in sitting or ():
            state[i] = SITTING
    share, light = (
        (SEDENTARY_LIGHT_SHARE, SEDENTARY_LIGHT_CADENCE)
        if sedentary
        else (LIGHT_ACTIVE_SHARE, LIGHT_CADENCE)
    )
    for i in range(size):
        if state[i] == LIGHT and r.random() < share:
            cadence[i] = r.uniform(*light)
    resting_hr = r.uniform(58.0, 66.0)
    if (scenario_hr := scenarios.resting_hr(day)) is not None:
        resting_hr = rng(seed, day, "scenario:hr").uniform(*scenario_hr)

    return DayProfile(
        day=day,
        start=start,
        end=end,
        state=state,
        cadence=cadence,
        phone_ratio=phone_ratio,
        sleep=_clip([(n.bed, n.wake) for n in nights], start, end),
        phone_sleep=_clip([(n.phone_bed, n.phone_wake) for n in nights], start, end),
        resting_hr=resting_hr,
    )
