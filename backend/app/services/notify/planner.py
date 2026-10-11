"""When to send the digest (SPEC F10, ADR-049): pure functions without the database.

`plan_send` applies the rules in order: the window and the cap (`window`, `max_delay`), one digest
per local day (`daily_limit`), quiet hours (`quiet_hours`), and the daily limit once more, since
the quiet hours may have moved the time to another date. A time already in the past becomes «now»
before the limit and the quiet hours. The reason is the last rule that moved the time.
`plan_send_time` is the signature of SPEC F10: the time only.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from app.services.localtime import TzHistory

PlanReason = Literal["window", "max_delay", "daily_limit", "quiet_hours"]

DIGEST_WINDOW = timedelta(minutes=15)
DIGEST_MAX_DELAY = timedelta(minutes=60)

# The limit and the quiet hours settle in two or three rounds; more means a bug, not a plan.
_MAX_ROUNDS = 10
# The first date after the last digest is at most this many days after it (offsets differ by
# at most 26 hours).
_DATES_AHEAD = 3
_SECOND = timedelta(seconds=1)


@dataclass(frozen=True)
class QuietHours:
    """The user's quiet hours in local time; they may cross midnight (22:00–08:00)."""

    enabled: bool
    start: time
    end: time


@dataclass(frozen=True)
class SendPlan:
    """The planned send time (UTC) and the rule that set it."""

    at: datetime
    reason: PlanReason


def plan_send(
    pending: Sequence[datetime],
    last_digest_local_date: date | None,
    tz_history: TzHistory,
    quiet_hours: QuietHours,
    now: datetime,
    *,
    window: timedelta = DIGEST_WINDOW,
    max_delay: timedelta = DIGEST_MAX_DELAY,
) -> SendPlan:
    """The send time of a digest of the `pending` outbox entries (their creation times) and
    the rule that set it."""
    by_window, by_cap = max(pending) + window, min(pending) + max_delay
    reason: PlanReason = "window" if by_window <= by_cap else "max_delay"
    # Overdue (the worker was down): «now» keeps the reason of the window or the cap.
    at = max(min(by_window, by_cap), now).astimezone(UTC)

    for _ in range(_MAX_ROUNDS):
        allowed = _first_allowed(at, last_digest_local_date, tz_history)
        if allowed > at:
            at, reason = allowed, "daily_limit"
        quiet_end = _quiet_end(at, quiet_hours, tz_history)
        if quiet_end == at:
            return SendPlan(at, reason)
        at, reason = quiet_end, "quiet_hours"
    raise RuntimeError(f"digest plan did not settle in {_MAX_ROUNDS} rounds, at {at.isoformat()}")


def plan_send_time(
    pending: Sequence[datetime],
    last_digest_local_date: date | None,
    tz_history: TzHistory,
    quiet_hours: QuietHours,
    now: datetime,
) -> datetime:
    """The signature of SPEC F10: the time of `plan_send`."""
    return plan_send(pending, last_digest_local_date, tz_history, quiet_hours, now).at


def _first_allowed(at: datetime, last: date | None, tz_history: TzHistory) -> datetime:
    """The first instant from `at` on whose local date is after the last digest's one (ADR-049):
    the dates of digests only grow, even when a move west takes the local date back."""
    if last is None or tz_history.local_date(at) > last:
        return at
    starts = [
        max(start, at)
        for days in range(1, _DATES_AHEAD + 1)
        for start, end in tz_history.ranges_for_date(last + timedelta(days=days))
        if end > at
    ]
    return min(starts)


def _quiet_end(at: datetime, quiet: QuietHours, tz_history: TzHistory) -> datetime:
    """The end of the quiet hours [start, end) that `at` falls in, or `at` itself. Local time is
    read in the zone in effect at `at`: the history has no moves after now (ADR-017)."""
    zone = tz_history.zone_at(at)
    local = at.astimezone(zone)
    if not _is_quiet(local.time(), quiet):
        return at
    # Across midnight, the evening part ends tomorrow.
    evening = quiet.start > quiet.end and local.time() >= quiet.start
    end_day = local.date() + timedelta(days=1) if evening else local.date()
    # The end is the first instant after `at` that is not quiet. When the clocks go back, its wall
    # time happens twice (fold 0 and 1) and the first pass may be before `at`; when they go
    # forward, it may never happen, and the quiet hours end when the clock jumps past it.
    for fold in (0, 1):
        end = datetime.combine(end_day, quiet.end, tzinfo=zone).replace(fold=fold).astimezone(UTC)
        if end > at and not _is_quiet(end.astimezone(zone).time(), quiet):
            break
    else:
        raise RuntimeError(f"no end of the quiet hours after {at.isoformat()}")
    if end.astimezone(zone).time() == quiet.end:
        return end
    return _first_not_quiet(at, end, zone, quiet)


def _is_quiet(clock: time, quiet: QuietHours) -> bool:
    """Is the local wall time in the quiet hours [start, end)?"""
    if not quiet.enabled or quiet.start == quiet.end:  # start == end: off (ADR-017)
        return False
    if quiet.start < quiet.end:
        return quiet.start <= clock < quiet.end
    return clock >= quiet.start or clock < quiet.end


def _first_not_quiet(
    quiet_at: datetime, free_at: datetime, zone: ZoneInfo, quiet: QuietHours
) -> datetime:
    """The first whole second after `quiet_at` (quiet) up to `free_at` (not quiet) that is not
    quiet: the moment the clock jumps over the end of the quiet hours."""
    lo, hi = quiet_at.replace(microsecond=0), free_at
    while hi - lo > _SECOND:
        mid = (lo + (hi - lo) / 2).replace(microsecond=0)
        if _is_quiet(mid.astimezone(zone).time(), quiet):
            lo = mid
        else:
            hi = mid
    return hi
