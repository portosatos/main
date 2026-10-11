"""Summary routes (SPEC F7, §6.3): a day, an ISO week and a range of the user's local dates.

They read daily_summaries of the session's user only; a date without a row is no_data with
nulls, never zeros (SPEC F6).
"""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import SessionDep
from app.auth.deps import CurrentUserDep
from app.schemas.summary import DayOut, DaySummaryOut, WeekSummaryOut
from app.services.weekly import (
    MAX_RANGE_DAYS,
    WEEK,
    day_deltas,
    load_days,
    parse_week,
    week_deltas,
    week_totals,
)

router = APIRouter(prefix="/api/summary", tags=["summary"])


def invalid(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


@router.get("/day")
async def day_summary(
    user: CurrentUserDep, session: SessionDep, day: Annotated[date, Query(alias="date")]
) -> DaySummaryOut:
    """The day and the difference with the day before."""
    if day == date.min:
        raise invalid("Нет предыдущего дня")
    previous, current = await load_days(session, user.id, day - timedelta(days=1), day)
    return DaySummaryOut(day=current, previous=previous, delta=day_deltas(current, previous))


@router.get("/week")
async def week_summary(
    user: CurrentUserDep,
    session: SessionDep,
    week: Annotated[str, Query(examples=["2026-W41"])],
) -> WeekSummaryOut:
    """ISO week Monday..Sunday of local dates: its seven days, the means over the F7 bases and
    the difference with the previous week."""
    try:
        monday = parse_week(week)
    except ValueError as exc:
        raise invalid(f"Неделя в формате 2026-W41: {exc}") from exc
    days = await load_days(session, user.id, monday - WEEK, monday + WEEK - timedelta(days=1))
    previous = week_totals(monday - WEEK, days[:7])
    current = week_totals(monday, days[7:])
    return WeekSummaryOut(
        **current.model_dump(),
        days=days[7:],
        previous=previous,
        delta=week_deltas(current.metrics, previous.metrics),
    )


@router.get("/range")
async def range_summary(
    user: CurrentUserDep,
    session: SessionDep,
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
) -> list[DayOut]:
    """Every date from `from` to `to` inclusive, at most a year, for charts."""
    if end < start:
        raise invalid("from позже to")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise invalid(f"Не больше {MAX_RANGE_DAYS} дней")
    return await load_days(session, user.id, start, end)
