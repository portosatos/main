"""Reading daily summaries for the API: days with no_data filled in, ISO weeks, the week's
bases (SPEC F7) and the difference with the previous period (ADR-037, ADR-038).

Values are rounded to 0.1 as the API shows them, and differences are taken between the shown
values, so a client never sees a delta that disagrees with the two numbers next to it.
"""

import re
import uuid
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from statistics import fmean

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailySummary
from app.schemas.summary import (
    DayGoals,
    DayOut,
    Delta,
    Deltas,
    GoalProgress,
    WeekGoal,
    WeekGoals,
    WeekMetric,
    WeekMetrics,
    WeekTotals,
)
from app.services.goals import GoalBook, GoalKind, goal_value, is_met, load_goal_book, percent

WEEK = timedelta(days=7)
# The longest /api/summary/range, in days: a year of a chart.
MAX_RANGE_DAYS = 366
WEEK_PATTERN = re.compile(r"(\d{4})-W(\d{2})")


def parse_week(text: str) -> date:
    """The Monday of an ISO week `YYYY-Www`. ValueError for another format, a week the year
    does not have (W00, W53 of a 52-week year) or a week without a previous one."""
    match = WEEK_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError("week must look like 2026-W41")
    monday = date.fromisocalendar(int(match[1]), int(match[2]), 1)
    if monday - date.min < WEEK:
        raise ValueError("the week has no previous week")
    return monday


def week_label(monday: date) -> str:
    year, week, _ = monday.isocalendar()
    return f"{year}-W{week:02d}"


async def load_days(
    session: AsyncSession, user_id: uuid.UUID, start: date, end: date
) -> list[DayOut]:
    """Every local date from `start` to `end` inclusive with its goals; a date without a row
    is no_data."""
    book = await load_goal_book(session, user_id)
    summaries = await session.scalars(
        select(DailySummary).where(
            DailySummary.user_id == user_id,
            DailySummary.local_date >= start,
            DailySummary.local_date <= end,
        )
    )
    by_date = {
        s.local_date: DayOut.of(s, day_goals(book, s.local_date, s.steps, s.sleep_minutes))
        for s in summaries
    }
    days = (start + timedelta(days=i) for i in range((end - start).days + 1))
    return [
        by_date.get(day) or DayOut.no_data(day, day_goals(book, day, None, None)) for day in days
    ]


def day_goals(book: GoalBook, day: date, steps: int | None, sleep_minutes: int | None) -> DayGoals:
    def progress(kind: GoalKind) -> GoalProgress:
        target = book.target(kind, day)
        value = goal_value(kind, steps, sleep_minutes)
        return GoalProgress(
            target=target, percent=percent(value, target), achieved=is_met(value, target)
        )

    return DayGoals(steps=progress("steps"), sleep=progress("sleep"))


def delta(current: float | None, previous: float | None) -> Delta | None:
    if current is None or previous is None:
        return None
    change = current - previous
    pct = None if previous == 0 else round(change / previous * 100, 1)
    return Delta(abs=round(change, 1), pct=pct)


def day_deltas(day: DayOut, previous: DayOut) -> Deltas:
    """Any two values compare, except sleep: only between two valid nights (ADR-037)."""
    valid_nights = day.night_valid and previous.night_valid
    return Deltas(
        steps=delta(day.steps, previous.steps),
        active_minutes=delta(day.active_minutes, previous.active_minutes),
        sleep_minutes=delta(day.sleep_minutes, previous.sleep_minutes) if valid_nights else None,
        resting_hr=delta(day.resting_hr, previous.resting_hr),
        peak_hr=delta(day.peak_hr, previous.peak_hr),
    )


def week_metric(
    values: Sequence[float | None], combine: Callable[[list[float]], float] = fmean
) -> WeekMetric:
    base = [v for v in values if v is not None]
    return WeekMetric(value=round(combine(base), 1) if base else None, days=len(base))


def week_metrics(days: Sequence[DayOut]) -> WeekMetrics:
    """SPEC F7 bases: steps and activity over complete days, sleep over valid nights whatever
    the day's status, resting pulse over days where it is computed, peak pulse is their max."""
    complete = [d for d in days if d.status == "complete"]
    return WeekMetrics(
        steps=week_metric([d.steps for d in complete]),
        active_minutes=week_metric([d.active_minutes for d in complete]),
        sleep_minutes=week_metric([d.sleep_minutes for d in days if d.night_valid]),
        resting_hr=week_metric([d.resting_hr for d in days]),
        peak_hr=week_metric([d.peak_hr for d in days], max),
    )


def week_totals(monday: date, days: Sequence[DayOut]) -> WeekTotals:
    return WeekTotals(
        week=week_label(monday),
        start=monday,
        end=monday + WEEK - timedelta(days=1),
        metrics=week_metrics(days),
        goals=WeekGoals(
            steps=WeekGoal(achieved_days=sum(d.goals.steps.achieved for d in days)),
            sleep=WeekGoal(achieved_days=sum(d.goals.sleep.achieved for d in days)),
        ),
    )


def week_deltas(week: WeekMetrics, previous: WeekMetrics) -> Deltas:
    return Deltas(
        **{
            name: delta(getattr(week, name).value, getattr(previous, name).value)
            for name in Deltas.model_fields
        }
    )
