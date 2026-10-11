"""When to send the digest (SPEC F10): `plan_send_time`, a pure function without the database.

The rules, in order: the window and the cap (`window`, `max_delay`), one digest per local day
(`daily_limit`), quiet hours (`quiet_hours`), and the daily limit once more, since the quiet hours
may have moved the time to another date.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from app.services.localtime import TzHistory

PlanReason = Literal["window", "max_delay", "daily_limit", "quiet_hours"]

DIGEST_WINDOW = timedelta(minutes=15)
DIGEST_MAX_DELAY = timedelta(minutes=60)


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


def plan_send_time(
    pending: Sequence[datetime],
    last_digest_local_date: date | None,
    tz_history: TzHistory,
    quiet_hours: QuietHours,
    now: datetime,
    *,
    window: timedelta = DIGEST_WINDOW,
    max_delay: timedelta = DIGEST_MAX_DELAY,
) -> SendPlan:
    """The send time of a digest of the `pending` outbox entries (their creation times)."""
    raise NotImplementedError("step 9.1")
