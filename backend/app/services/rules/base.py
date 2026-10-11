"""What a rule reads and what it returns (SPEC F6, F9).

A rule reads `Facts`: the daily summaries of the user's recent local dates (a date without a row
is `no_data`), the goal in effect on each date, today's local date by Clock and the local time of
an instant by the user's time zone history. It returns a
`Verdict` for an anchor date:

- `fire` — the condition is true (a recommendation opens, unless one is open);
- `close` — the auto-close condition is true (an open recommendation is resolved);
- `hold` — the data are there, but neither condition is true (e.g. R1 with a 6–7 h night);
- `unknown` — the data the rule needs are missing: nothing changes (SPEC F6).
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Literal

from app.services.goals import DEFAULT_TARGETS, GoalKind

VerdictKind = Literal["fire", "close", "hold", "unknown"]


@dataclass(frozen=True)
class Day:
    """The summary of a local date as the rules see it; the defaults are a no_data date."""

    local_date: date
    status: Literal["no_data", "partial", "complete"] = "no_data"
    wear_minutes: int = 0
    steps: int | None = None
    active_minutes: int | None = None
    sleep_minutes: int | None = None
    sleep_start: datetime | None = None
    sleep_end: datetime | None = None
    night_valid: bool = False
    resting_hr: float | None = None
    peak_hr: float | None = None


def default_goal(kind: GoalKind, day: date) -> float:
    return DEFAULT_TARGETS[kind]


def utc_time(ts: datetime) -> datetime:
    return ts


class Facts:
    """The days of a user around `today`, looked up by local date."""

    def __init__(
        self,
        days: Iterable[Day],
        today: date,
        goal: Callable[[GoalKind, date], float] = default_goal,
        local_time: Callable[[datetime], datetime] = utc_time,
    ) -> None:
        self._days = {d.local_date: d for d in days}
        self.today = today
        self.goal = goal
        # The wall-clock time of an instant in the zone in effect at it (R5 bedtimes).
        self.local_time = local_time

    def day(self, local_date: date) -> Day:
        return self._days.get(local_date) or Day(local_date)


def yesterday(facts: Facts) -> date:
    """The anchor of the rules about whole days: today is not over yet (SPEC F9)."""
    return facts.today - timedelta(days=1)


def has_night(day: Day) -> bool:
    """A valid night with its main session (SPEC F6): its sleep and bedtime are known."""
    return day.night_valid and day.sleep_minutes is not None and day.sleep_start is not None


def last_night(facts: Facts) -> date:
    """The anchor of the rules about nights: today if last night is valid, else yesterday."""
    return facts.today if has_night(facts.day(facts.today)) else yesterday(facts)


@dataclass(frozen=True)
class Verdict:
    kind: VerdictKind
    # A snapshot of the values the verdict rests on (stored with an opened recommendation).
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Rule:
    code: str
    # The rule reads the local dates from this many days before today on (its anchor and window).
    window_days: int
    # The date the rule is evaluated at (SPEC F9 «опорная дата»).
    anchor: Callable[[Facts], date]
    evaluate: Callable[[Facts, date], Verdict]
