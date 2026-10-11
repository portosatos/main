"""Schemas of /api/summary/* (SPEC F7, §6.3)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


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


class WeekTotals(BaseModel):
    week: str = Field(examples=["2026-W41"])
    start: date
    end: date
    metrics: WeekMetrics


class WeekSummaryOut(WeekTotals):
    days: list[DayOut]
    previous: WeekTotals
    delta: Deltas
