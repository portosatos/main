"""Goals (SPEC F8, ADR-043): versions with history, progress of a day and of a week.

A version of a kind's target is in effect from the local date of its `valid_from` on (by the
time zone history), so a goal changed today counts already today and the past days keep the
goal that was in effect then. Before the first version the defaults apply.

A goal is met when the value reaches the target. A partial day or an invalid night gives a value
no greater than the real one, so missing data never makes a goal met that was not.

Every recompute of summaries ends with `record_achievements`: a goal newly met on a date gets
its goal_achievements row (once: the primary key), a notification for the bell and, when the
transaction commits, `notification.created` and `goal.achieved` (SPEC F8, F12).
"""

import math
import uuid
from bisect import bisect_right
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailySummary, Goal, GoalAchievement, Notification
from app.services import events
from app.services.localtime import TzHistory, load_tz_history

GoalKind = Literal["steps", "sleep"]
KINDS: tuple[GoalKind, ...] = ("steps", "sleep")
# Steps a day and hours of sleep before the user sets a goal (SPEC F8, a Допущение there).
DEFAULT_TARGETS: dict[GoalKind, float] = {"steps": 8000, "sleep": 8}
GOAL_ACHIEVED = "goal.achieved"
# A toast only for an achievement of today or of the day before (SPEC F8): an import of old dates
# fills the bell's feed without a flood of toasts.
TOAST_DAYS = timedelta(days=1)


def shown(target: float) -> int | float:
    """A target as the API shows it: 8000, not 8000.0; REAL noise rounded off (7.5, not 7.50…)."""
    rounded = round(target, 2)
    return int(rounded) if rounded.is_integer() else rounded


@dataclass(frozen=True)
class GoalVersion:
    kind: GoalKind
    target: int | float
    # None: the default, in effect since always.
    valid_from: datetime | None


class GoalBook:
    """The goal versions of a user, looked up by local date."""

    def __init__(self, goals: Iterable[Goal], history: TzHistory) -> None:
        by_kind: dict[str, list[Goal]] = {kind: [] for kind in KINDS}
        for goal in sorted(goals, key=lambda g: (g.valid_from, g.id)):
            by_kind[goal.kind].append(goal)
        self._versions = by_kind
        self._starts = {
            kind: [history.local_date(g.valid_from) for g in versions]
            for kind, versions in by_kind.items()
        }

    def current(self, kind: GoalKind) -> GoalVersion:
        """The latest version (every version starts at the moment it was set)."""
        versions = self._versions[kind]
        if not versions:
            return GoalVersion(kind, shown(DEFAULT_TARGETS[kind]), None)
        last = versions[-1]
        return GoalVersion(kind, shown(last.target), last.valid_from)

    def target(self, kind: GoalKind, day: date) -> int | float:
        """The target in effect on the local date `day`."""
        i = bisect_right(self._starts[kind], day) - 1
        if i < 0:
            return shown(DEFAULT_TARGETS[kind])
        return shown(self._versions[kind][i].target)


async def load_goal_book(
    session: AsyncSession, user_id: uuid.UUID, history: TzHistory | None = None
) -> GoalBook:
    goals = await session.scalars(select(Goal).where(Goal.user_id == user_id))
    return GoalBook(goals.all(), history or await load_tz_history(session, user_id))


def goal_value(kind: GoalKind, steps: int | None, sleep_minutes: int | None) -> float | None:
    """The day's value in the units of the target: steps, or hours of sleep (the wake day's)."""
    if kind == "steps":
        return steps
    return None if sleep_minutes is None else sleep_minutes / 60


def summary_value(kind: GoalKind, summary: DailySummary) -> float | None:
    return goal_value(kind, summary.steps, summary.sleep_minutes)


def is_met(value: float | None, target: float) -> bool:
    return value is not None and value >= target


def percent(value: float | None, target: float) -> int | None:
    """Of the target, rounded down: 100 only when the goal is met."""
    if value is None:
        return None
    share = math.floor(value * 100 / target)
    return share if is_met(value, target) else min(share, 99)


def shown_value(kind: GoalKind, value: float) -> int | float:
    """A value as an event or a notification shows it: whole steps, hours to 0.1."""
    return int(value) if kind == "steps" else round(value, 1)


async def record_achievements(
    session: AsyncSession,
    user_id: uuid.UUID,
    dates: Iterable[date],
    now: datetime,
    history: TzHistory | None = None,
) -> None:
    """Record the goals met on `dates` by the summaries of this transaction and not recorded
    before; `now` (from Clock) is the time of the achievement and decides the toast."""
    days = sorted(set(dates))
    if not days:
        return
    history = history or await load_tz_history(session, user_id)
    book = await load_goal_book(session, user_id, history)
    summaries = await session.scalars(
        select(DailySummary)
        .where(DailySummary.user_id == user_id, DailySummary.local_date.in_(days))
        .order_by(DailySummary.local_date)
    )
    met = []
    for summary in summaries:
        for kind in KINDS:
            target = book.target(kind, summary.local_date)
            value = summary_value(kind, summary)
            if value is not None and is_met(value, target):
                met.append((kind, summary.local_date, target, value))
    if not met:
        return
    rows = [
        {"user_id": user_id, "kind": kind, "local_date": day, "achieved_at": now}
        for kind, day, _, _ in met
    ]
    inserted = await session.execute(
        insert(GoalAchievement)
        .values(rows)
        .on_conflict_do_nothing()
        .returning(GoalAchievement.kind, GoalAchievement.local_date)
    )
    new = {(kind, day) for kind, day in inserted.all()}
    today = history.local_date(now)
    for kind, day, target, value in met:
        if (kind, day) in new:
            await _notify(session, user_id, kind, day, target, value, now, today)


async def _notify(
    session: AsyncSession,
    user_id: uuid.UUID,
    kind: GoalKind,
    day: date,
    target: int | float,
    value: float,
    now: datetime,
    today: date,
) -> None:
    """The bell's notification of an achievement; `notification.created` goes first, so a tab
    that shows the toast already finds the notification in the feed."""
    payload = {
        "kind": kind,
        "local_date": day.isoformat(),
        "target": target,
        "value": shown_value(kind, value),
    }
    notification = Notification(
        user_id=user_id, type=GOAL_ACHIEVED, payload=payload, created_at=now
    )
    session.add(notification)
    await session.flush()
    notification_id = str(notification.id)
    await events.publish(
        session, user_id, "notification.created", {"id": notification_id, "type": GOAL_ACHIEVED}
    )
    toast = today - TOAST_DAYS <= day <= today
    await events.publish(
        session,
        user_id,
        GOAL_ACHIEVED,
        payload | {"show_toast": toast, "notification_id": notification_id},
    )
