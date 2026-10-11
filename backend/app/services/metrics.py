"""Metrics of a user's local day from the merged minutes (SPEC F6, F7).

A minute belongs to the local date of its start (services/localtime.py). The day's minutes are
merged across devices (services/merge.py), then:
- `wear_minutes` — minutes covered by at least one device; `status` — no_data (0), partial (1–719),
  complete (720 and more);
- `steps` — the sum of the merged minutes; `active_minutes` — merged minutes with at least 100
  steps; both are None on a no_data day: no data is not zero;
- `resting_hr` — the 10th percentile of the minute pulse over minutes without steps, None if there
  are fewer than 60 such minutes; `peak_hr` — the maximum of the minute pulse. The pulse of a minute
  is the median of its points, so a single spike does not make the peak; a minute without steps
  has exactly 0 merged steps; the percentile interpolates linearly, as percentile_cont (ADR-034).

Sleep and storing the day in daily_summaries come in step 4.3.
"""

import math
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import ColumnElement, and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models import CoverageMinute, Device, HrPoint, StepsMinute
from app.services.localtime import UtcRange, load_tz_history
from app.services.merge import Merged, device_order, merge_hr, merge_steps
from app.services.minutes import ceil_minute

COMPLETE_WEAR_MINUTES = 12 * 60
ACTIVE_MINUTE_STEPS = 100
REST_MINUTES_MIN = 60
RESTING_PERCENTILE = 0.1


@dataclass(frozen=True, slots=True)
class DayMetrics:
    local_date: date
    status: str  # no_data | partial | complete
    wear_minutes: int
    steps: int | None
    active_minutes: int | None
    resting_hr: float | None
    peak_hr: float | None


def day_status(wear_minutes: int) -> str:
    if wear_minutes == 0:
        return "no_data"
    return "complete" if wear_minutes >= COMPLETE_WEAR_MINUTES else "partial"


def percentile(values: Sequence[float], q: float) -> float:
    """The q-th quantile (0 <= q <= 1) with linear interpolation between the closest ranks."""
    if not values:
        raise ValueError("percentile of no values")
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = math.floor(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def summarize_day(
    day: date, steps: Mapping[datetime, Merged[float]], hr: Mapping[datetime, Merged[float]]
) -> DayMetrics:
    """Metrics of a day from its merged minutes: the steps of every covered minute and the
    pulse (the median of the points) of every minute that has any."""
    wear_minutes = len(steps)
    status = day_status(wear_minutes)
    if status == "no_data":
        return DayMetrics(day, status, 0, None, None, None, None)
    rest = [hr[m].value for m, s in steps.items() if s.value == 0 and m in hr]
    return DayMetrics(
        local_date=day,
        status=status,
        wear_minutes=wear_minutes,
        steps=round(sum(s.value for s in steps.values())),
        active_minutes=sum(1 for s in steps.values() if s.value >= ACTIVE_MINUTE_STEPS),
        resting_hr=percentile(rest, RESTING_PERCENTILE) if len(rest) >= REST_MINUTES_MIN else None,
        peak_hr=max((p.value for p in hr.values()), default=None),
    )


async def day_metrics(session: AsyncSession, user_id: uuid.UUID, day: date) -> DayMetrics:
    """Metrics of the user's local date `day` from the minute tables and pulse points."""
    history = await load_tz_history(session, user_id)
    ranges = _minute_ranges(history.ranges_for_date(day))
    devices = (await session.scalars(select(Device).where(Device.user_id == user_id))).all()
    device_ids = [d.id for d in devices]

    coverage: dict[uuid.UUID, set[datetime]] = {d: set() for d in device_ids}
    query = select(CoverageMinute.device_id, CoverageMinute.minute_utc).where(
        CoverageMinute.device_id.in_(device_ids), _within(CoverageMinute.minute_utc, ranges)
    )
    for device_id, minute in await session.execute(query):
        coverage[device_id].add(minute)

    steps: dict[uuid.UUID, dict[datetime, float]] = {d: {} for d in device_ids}
    query = select(StepsMinute.device_id, StepsMinute.minute_utc, StepsMinute.steps).where(
        StepsMinute.device_id.in_(device_ids), _within(StepsMinute.minute_utc, ranges)
    )
    for device_id, minute, value in await session.execute(query):
        steps[device_id][minute] = value

    # The ranges start and end on minute borders, so a point is inside iff its minute is.
    hr: dict[uuid.UUID, dict[datetime, float]] = {d: {} for d in device_ids}
    minute = func.date_trunc("minute", HrPoint.ts_utc, "UTC")
    query = (
        select(
            HrPoint.device_id,
            minute,
            func.percentile_cont(0.5).within_group(HrPoint.bpm),
        )
        .where(HrPoint.device_id.in_(device_ids), _within(HrPoint.ts_utc, ranges))
        .group_by(HrPoint.device_id, minute)
    )
    for device_id, minute_utc, median in await session.execute(query):
        hr[device_id][minute_utc] = median

    order = device_order(devices)
    return summarize_day(day, merge_steps(order, coverage, steps), merge_hr(order, hr))


def _minute_ranges(ranges: list[UtcRange]) -> list[UtcRange]:
    """The day's ranges on minute borders: a minute belongs to the date of its start."""
    rounded = [(ceil_minute(start), ceil_minute(end)) for start, end in ranges]
    return [(start, end) for start, end in rounded if start < end]


def _within(column: InstrumentedAttribute[datetime], ranges: list[UtcRange]) -> ColumnElement[bool]:
    return or_(false(), *(and_(column >= start, column < end) for start, end in ranges))
