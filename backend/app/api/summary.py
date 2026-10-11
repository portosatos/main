"""Summary routes (SPEC F7, §6.3): a day, an ISO week and a range of the user's local dates."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import SessionDep
from app.auth.deps import CurrentUserDep
from app.schemas.summary import DayOut, DaySummaryOut, WeekSummaryOut

router = APIRouter(prefix="/api/summary", tags=["summary"])


def not_implemented() -> HTTPException:
    return HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="Не реализовано")


@router.get("/day")
async def day_summary(
    user: CurrentUserDep, session: SessionDep, day: Annotated[date, Query(alias="date")]
) -> DaySummaryOut:
    raise not_implemented()


@router.get("/week")
async def week_summary(
    user: CurrentUserDep,
    session: SessionDep,
    week: Annotated[str, Query(examples=["2026-W41"])],
) -> WeekSummaryOut:
    raise not_implemented()


@router.get("/range")
async def range_summary(
    user: CurrentUserDep,
    session: SessionDep,
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
) -> list[DayOut]:
    raise not_implemented()
