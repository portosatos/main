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
  has exactly 0 merged steps; the percentile interpolates linearly, as percentile_cont (ADR-034);
- sleep — the sessions that ended on the day (services/sleep.py) from the merged sleep minutes and
  the coverage around the day: 48 hours back for the start of a session, 2 hours forward to see
  whether the last one goes on and to check the hour after it. A session longer than 48 hours
  would be cut; real ones are far shorter. A session that ends with the user's data (no device
  covers any minute after it, `data_end`) belongs to no day yet (ADR-046).

services/summaries.py stores the result in daily_summaries.
"""

import math
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import ColumnElement, and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models import CoverageMinute, Device, HrPoint, SleepMinute, StepsMinute
from app.services.localtime import TzHistory, UtcRange, load_tz_history
from app.services.merge import Merged, device_order, merge_hr, merge_sleep, merge_steps
from app.services.minutes import MINUTE, ceil_minute
from app.services.sleep import NO_SLEEP, DaySleep, summarize_sleep

COMPLETE_WEAR_MINUTES = 12 * 60
ACTIVE_MINUTE_STEPS = 100
REST_MINUTES_MIN = 60
RESTING_PERCENTILE = 0.1
SLEEP_LOOKBACK = timedelta(hours=48)
SLEEP_LOOKAHEAD = timedelta(hours=2)


@dataclass(frozen=True, slots=True)
class DayMetrics:
    local_date: date
    status: str  # no_data | partial | complete
    wear_minutes: int
    steps: int | None
    active_minutes: int | None
    resting_hr: float | None
    peak_hr: float | None
    # Sleep of the sessions that ended on this date (services/sleep.py).
    sleep_minutes: int | None = None
    sleep_start: datetime | None = None
    sleep_end: datetime | None = None
    night_valid: bool = False


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
    day: date,
    steps: Mapping[datetime, Merged[float]],
    hr: Mapping[datetime, Merged[float]],
    sleep: DaySleep = NO_SLEEP,
) -> DayMetrics:
    """Metrics of a day from its merged minutes: the steps of every covered minute, the pulse
    (the median of the points) of every minute that has any, and the day's sleep."""
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
        sleep_minutes=sleep.sleep_minutes,
        sleep_start=sleep.sleep_start,
        sleep_end=sleep.sleep_end,
        night_valid=sleep.night_valid,
    )


async def day_metrics(session: AsyncSession, user_id: uuid.UUID, day: date) -> DayMetrics:
    """Metrics of the user's local date `day` from the minute tables and pulse points."""
    history = await load_tz_history(session, user_id)
    devices = (await session.scalars(select(Device).where(Device.user_id == user_id))).all()
    return await compute_day(session, history, devices, day)


async def last_covered(
    session: AsyncSession, device_ids: Sequence[uuid.UUID], before: datetime | None = None
) -> datetime | None:
    """The latest minute any of the devices covers (earlier than `before`); None without one.
    One index lookup per device."""
    latest = []
    for device_id in device_ids:
        query = select(func.max(CoverageMinute.minute_utc)).where(
            CoverageMinute.device_id == device_id
        )
        if before is not None:
            query = query.where(CoverageMinute.minute_utc < before)
        latest.append(query.scalar_subquery())
    if not latest:
        return None
    return await session.scalar(select(func.greatest(*latest)))


async def data_end(session: AsyncSession, device_ids: Sequence[uuid.UUID]) -> datetime | None:
    """The end of the user's data: the end of the last minute any device covers."""
    last = await last_covered(session, device_ids)
    return None if last is None else last + MINUTE


async def compute_day(
    session: AsyncSession,
    history: TzHistory,
    devices: Sequence[Device],
    day: date,
    end_of_data: datetime | None = None,
) -> DayMetrics:
    """day_metrics with the user's time zone history and devices already loaded;
    `end_of_data` — data_end of the devices, loaded if not given."""
    ranges = _minute_ranges(history.ranges_for_date(day))
    device_ids = [d.id for d in devices]
    if not ranges or not device_ids:
        return summarize_day(day, {}, {})
    window = [(ranges[0][0] - SLEEP_LOOKBACK, ranges[-1][1] + SLEEP_LOOKAHEAD)]
    coverage = await load_minutes(session, CoverageMinute, device_ids, window)
    asleep = await load_minutes(session, SleepMinute, device_ids, window)

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
    day_coverage = {
        device_id: {m for m in minutes if any(a <= m < b for a, b in ranges)}
        for device_id, minutes in coverage.items()
    }
    merged_sleep = merge_sleep(order, coverage, asleep)
    if end_of_data is None:
        end_of_data = await data_end(session, device_ids)
    sleep = summarize_sleep(
        day,
        history,
        (m for m, s in merged_sleep.items() if s.value),
        merged_sleep.keys(),
        end_of_data,
    )
    return summarize_day(day, merge_steps(order, day_coverage, steps), merge_hr(order, hr), sleep)


async def load_minutes(
    session: AsyncSession,
    model: type[CoverageMinute | SleepMinute],
    device_ids: list[uuid.UUID],
    ranges: list[UtcRange],
) -> dict[uuid.UUID, set[datetime]]:
    """{device_id: minutes} of a minute table inside the ranges."""
    found: dict[uuid.UUID, set[datetime]] = {d: set() for d in device_ids}
    query = select(model.device_id, model.minute_utc).where(
        model.device_id.in_(device_ids), _within(model.minute_utc, ranges)
    )
    for device_id, minute in await session.execute(query):
        found[device_id].add(minute)
    return found


def _minute_ranges(ranges: list[UtcRange]) -> list[UtcRange]:
    """The day's ranges on minute borders: a minute belongs to the date of its start."""
    rounded = [(ceil_minute(start), ceil_minute(end)) for start, end in ranges]
    return [(start, end) for start, end in rounded if start < end]


def _within(column: InstrumentedAttribute[datetime], ranges: list[UtcRange]) -> ColumnElement[bool]:
    return or_(false(), *(and_(column >= start, column < end) for start, end in ranges))
