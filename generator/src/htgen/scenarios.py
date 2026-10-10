"""--scenario: ready-made data for the rules of SPEC F9, anchored to the end of the period.

| scenario      | rule   | what changes                                                        |
|---------------|--------|---------------------------------------------------------------------|
| short-sleep   | R1     | the last 3 nights last 4.5-5.5 h                                    |
| sedentary     | R2, R6 | the last 5 days: no walks, little light activity                    |
| high-rhr      | R3     | the last 2 days: resting pulse about 12 bpm above the usual level   |
| irregular     | R5     | the last 7 bedtimes spread from 20:30 to 02:30                      |
| worse-week    | R4     | nights of the last complete ISO week last 5-6.5 h                   |
| recovery      | all    | the last 7 nights and the last complete ISO week 7.5-8.5 h with a   |
|               |        | steady bedtime, a brisk walk on the last 3 days, a low pulse on the |
|               |        | last 2 days                                                         |

Scenario values come from their own seeds (seed, date, "scenario:..."), so the dates a scenario
does not touch are the same as without it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

NAMES = ("short-sleep", "sedentary", "high-rhr", "irregular", "worse-week", "recovery")
MIN_DAYS = {"short-sleep": 4, "sedentary": 5, "high-rhr": 9, "irregular": 8}

SHORT_SLEEP_MINUTES = (270, 330)
WORSE_WEEK_SLEEP_MINUTES = (300, 390)
RECOVERY_SLEEP_MINUTES = (450, 510)
RECOVERY_BED_MINUTES = (-45, -15)  # 23:15..23:45
# Bedtimes relative to midnight; 7 dates in a row take every value once (stdev 120 min).
IRREGULAR_BED_MINUTES = (-30, 150, -210, 90, -90, 30, -150)
IRREGULAR_JITTER = 10
HIGH_RESTING_HR = (74.0, 76.0)  # the usual level is 58-66
LOW_RESTING_HR = (57.0, 59.0)


@dataclass(frozen=True)
class Scenarios:
    names: frozenset[str] = frozenset()
    first: date = date.min  # the period, inclusive local dates
    last: date = date.min

    def problem(self) -> str | None:
        """Why the scenarios cannot be generated for the period, or None."""
        if "recovery" in self.names and len(self.names) > 1:
            return "recovery не сочетается с другими сценариями"
        days = (self.last - self.first).days + 1
        for name in sorted(self.names):
            if days < MIN_DAYS.get(name, 1):
                return f"сценарию {name} нужно не меньше {MIN_DAYS[name]} дней, в периоде {days}"
        if "worse-week" in self.names:
            week = self._last_complete_week()
            if week is None or week[0] - timedelta(days=7) < self.first:
                return "сценарию worse-week нужны две полные ISO-недели (пн–вс) в периоде"
        return None

    def _in_last(self, name: str, days: int, day: date) -> bool:
        return name in self.names and self.last - timedelta(days=days) < day <= self.last

    def _last_complete_week(self) -> tuple[date, date] | None:
        sunday = self.last - timedelta(days=self.last.isoweekday() % 7)
        monday = sunday - timedelta(days=6)
        return (monday, sunday) if monday >= self.first else None

    def _in_last_week(self, name: str, day: date) -> bool:
        week = self._last_complete_week() if name in self.names else None
        return week is not None and week[0] <= day <= week[1]

    def sleep_minutes(self, wake_day: date) -> tuple[int, int] | None:
        if self._in_last("short-sleep", 3, wake_day):
            return SHORT_SLEEP_MINUTES
        if self._in_last("recovery", 7, wake_day) or self._in_last_week("recovery", wake_day):
            return RECOVERY_SLEEP_MINUTES
        if self._in_last_week("worse-week", wake_day):
            return WORSE_WEEK_SLEEP_MINUTES
        return None

    def bed_minutes(self, wake_day: date, r: random.Random) -> int | None:
        if self._in_last("irregular", 7, wake_day):
            bed = IRREGULAR_BED_MINUTES[wake_day.toordinal() % len(IRREGULAR_BED_MINUTES)]
            return bed + r.randint(-IRREGULAR_JITTER, IRREGULAR_JITTER)
        if self._in_last("recovery", 7, wake_day) or self._in_last_week("recovery", wake_day):
            return r.randint(*RECOVERY_BED_MINUTES)
        return None

    def sedentary(self, day: date) -> bool:
        return self._in_last("sedentary", 5, day)

    def brisk_walk(self, day: date) -> bool:
        return self._in_last("recovery", 3, day)

    def resting_hr(self, day: date) -> tuple[float, float] | None:
        if self._in_last("high-rhr", 2, day):
            return HIGH_RESTING_HR
        if self._in_last("recovery", 2, day):
            return LOW_RESTING_HR
        return None


NONE = Scenarios()
