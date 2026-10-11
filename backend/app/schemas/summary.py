"""Schemas of /api/summary/* (SPEC F7, §6.3)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import DailySummary


class GoalProgress(BaseModel):
    """A goal on one date (SPEC F8): the target in effect that day, the share of it reached
    (rounded down; null without a value) and whether it is met."""

    target: int | float
    percent: int | None
    achieved: bool


class DayGoals(BaseModel):
    steps: GoalProgress = Field(description="Steps a day")
    sleep: GoalProgress = Field(description="Hours of sleep, counted on the wake day")


class DayOut(BaseModel):
    """One local date. A date without a daily_summaries row is `no_data`: wear 0, metrics null."""

    date: date
    status: Literal["no_data", "partial", "complete"]
    wear_minutes: int
    steps: int | None
    active_minutes: int | None
    sleep_minutes: int | None
    sleep_start: datetime | None
    sleep_end: datetime | None
    night_valid: bool
    resting_hr: float | None
    peak_hr: float | None
    goals: DayGoals

    @classmethod
    def of(cls, summary: DailySummary, goals: DayGoals) -> "DayOut":
        """The row as shown: pulse (REAL in the table) rounded to 0.1."""
        return cls(
            date=summary.local_date,
            status=summary.status,
            wear_minutes=summary.wear_minutes,
            steps=summary.steps,
            active_minutes=summary.active_minutes,
            sleep_minutes=summary.sleep_minutes,
            sleep_start=summary.sleep_start,
            sleep_end=summary.sleep_end,
            night_valid=summary.night_valid,
            resting_hr=_tenths(summary.resting_hr),
            peak_hr=_tenths(summary.peak_hr),
            goals=goals,
        )

    @classmethod
    def no_data(cls, day: date, goals: DayGoals) -> "DayOut":
        return cls(
            date=day,
            status="no_data",
            wear_minutes=0,
            steps=None,
            active_minutes=None,
            sleep_minutes=None,
            sleep_start=None,
            sleep_end=None,
            night_valid=False,
            resting_hr=None,
            peak_hr=None,
            goals=goals,
        )


def _tenths(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


class Delta(BaseModel):
    """Current minus previous; `pct` relative to previous, null when previous is 0."""

    abs: float
    pct: float | None


class Deltas(BaseModel):
    """Per metric; null when either side has no value ("нет данных для сравнения")."""

    steps: Delta | None
    active_minutes: Delta | None
    sleep_minutes: Delta | None
    resting_hr: Delta | None
    peak_hr: Delta | None


class DaySummaryOut(BaseModel):
    day: DayOut
    previous: DayOut
    delta: Deltas


class WeekMetric(BaseModel):
    """The metric over its base: `days` of the week's `of` days count (SPEC F7).
    `value` is null when the base is empty."""

    value: float | None
    days: int
    of: int = 7


class WeekMetrics(BaseModel):
    steps: WeekMetric = Field(description="Mean over complete days")
    active_minutes: WeekMetric = Field(description="Mean over complete days")
    sleep_minutes: WeekMetric = Field(description="Mean over valid nights, any day status")
    resting_hr: WeekMetric = Field(description="Mean over days where it is computed")
    peak_hr: WeekMetric = Field(description="Max over days where it is computed")


class WeekGoal(BaseModel):
    """ "Цель выполнена N из 7 дней": each day by the target in effect on it."""

    achieved_days: int
    of: int = 7


class WeekGoals(BaseModel):
    steps: WeekGoal
    sleep: WeekGoal


class WeekTotals(BaseModel):
    week: str = Field(examples=["2026-W41"])
    start: date
    end: date
    metrics: WeekMetrics
    goals: WeekGoals


class WeekSummaryOut(WeekTotals):
    days: list[DayOut]
    previous: WeekTotals
    delta: Deltas
