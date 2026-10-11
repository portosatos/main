"""daily_summaries: storing the day metrics and finding the dates to recompute (SPEC F3, F7).

A summary row is derived like the minute tables: `recompute_dates` computes the given local
dates from the minutes (services/metrics.py) and replaces their rows; a no_data date has no row.
`rebuild_summaries` recomputes every date of a user (`htadmin rebuild`). Every recompute ends
with the goals met on its dates (services/goals.py: achievements, notifications, events).

`affected_dates` turns the minutes a batch changed into the local dates whose summary may have
changed. A changed minute m changes the metrics of its own date and, through sleep, the dates of
the sessions near it: the session that m joins or splits (asleep minutes within 31 minutes of m)
and every session whose validity window (60 minutes around it) holds m. All of them meet
[m − 91 min, m + 91 min), so the dirty dates are the dates of that span plus the wake days of the
sessions that meet it, followed forward up to 48 hours. The ingest collects the dates with its
checkpoint and recomputes them at least every ~2 s and at the end of the job.
"""

import uuid
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CoverageMinute, DailySummary, Device, SleepMinute
from app.services.goals import record_achievements
from app.services.localtime import TzHistory, UtcRange, load_tz_history
from app.services.merge import device_order, merge_sleep
from app.services.metrics import SLEEP_LOOKBACK, DayMetrics, compute_day, load_minutes
from app.services.minutes import DirtyMinutes
from app.services.sleep import MINUTE, sleep_sessions
from app.worker.queue import lock_user

# The ingest recomputes stale summaries at least this often, in seconds (SPEC F3).
FLUSH_INTERVAL_S = 2.0
# How far a changed minute reaches: a session gap (30 min + 1) and the validity window (60 min).
DIRTY_MARGIN = timedelta(minutes=91)


async def affected_dates(
    session: AsyncSession, user_id: uuid.UUID, dirty: DirtyMinutes
) -> set[date]:
    """Local dates whose summary may change because the minutes of `dirty` changed."""
    spans = _union((start - DIRTY_MARGIN, end + DIRTY_MARGIN) for _, start, end in dirty.ranges())
    if not spans:
        return set()
    history = await load_tz_history(session, user_id)
    dates: set[date] = set()
    for start, end in spans:
        dates |= history.dates_between(start, end)

    devices = (await session.scalars(select(Device).where(Device.user_id == user_id))).all()
    device_ids = [d.id for d in devices]
    # No device sleeps inside the spans: no session meets them.
    asleep_inside = await load_minutes(session, SleepMinute, device_ids, spans)
    if not any(asleep_inside.values()):
        return dates
    window = [(spans[0][0], spans[-1][1] + SLEEP_LOOKBACK)]
    coverage = await load_minutes(session, CoverageMinute, device_ids, window)
    asleep = await load_minutes(session, SleepMinute, device_ids, window)
    merged = merge_sleep(device_order(devices), coverage, asleep)
    for s in sleep_sessions(m for m, v in merged.items() if v.value):
        if any(s.start < end and s.end > start for start, end in spans):
            dates.add(history.local_date(s.end - MINUTE))
    return dates


async def recompute_dates(
    session: AsyncSession, user_id: uuid.UUID, dates: Iterable[date], now: datetime
) -> None:
    """Compute the user's summaries of `dates` and replace their rows, then record the goals
    newly met on them; `now` (from Clock) becomes `computed_at`."""
    days = sorted(set(dates))
    if not days:
        return
    history = await load_tz_history(session, user_id)
    devices = (await session.scalars(select(Device).where(Device.user_id == user_id))).all()
    metrics = [await compute_day(session, history, devices, day) for day in days]

    empty = [m.local_date for m in metrics if m.status == "no_data"]
    if empty:
        await session.execute(
            delete(DailySummary).where(
                DailySummary.user_id == user_id, DailySummary.local_date.in_(empty)
            )
        )
    rows = [_row(user_id, m, now) for m in metrics if m.status != "no_data"]
    if rows:
        query = insert(DailySummary).values(rows)
        updated = {c: query.excluded[c] for c in rows[0] if c not in ("user_id", "local_date")}
        await session.execute(
            query.on_conflict_do_update(index_elements=["user_id", "local_date"], set_=updated)
        )
        dates_with_data = [row["local_date"] for row in rows]
        await record_achievements(session, user_id, dates_with_data, now, history)


async def rebuild_summaries(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> int:
    """Drop the user's summaries and compute every date that has data; the number of rows.
    Waits for the user's running ingest job, if any (the same user lock as the worker)."""
    await lock_user(session, user_id)
    await session.execute(delete(DailySummary).where(DailySummary.user_id == user_id))
    span = (
        await session.execute(
            select(func.min(CoverageMinute.minute_utc), func.max(CoverageMinute.minute_utc))
            .join(Device, Device.id == CoverageMinute.device_id)
            .where(Device.user_id == user_id)
        )
    ).one()
    if span[0] is None:
        return 0
    history: TzHistory = await load_tz_history(session, user_id)
    # Every date with data has a covered minute; a sleep session ends on a covered minute too.
    await recompute_dates(session, user_id, history.dates_between(span[0], span[1] + MINUTE), now)
    query = select(func.count()).select_from(DailySummary).where(DailySummary.user_id == user_id)
    return (await session.scalar(query)) or 0


def _row(user_id: uuid.UUID, m: DayMetrics, now: datetime) -> dict:
    return {
        "user_id": user_id,
        "local_date": m.local_date,
        "status": m.status,
        "wear_minutes": m.wear_minutes,
        "steps": m.steps,
        "active_minutes": m.active_minutes,
        "sleep_minutes": m.sleep_minutes,
        "sleep_start": m.sleep_start,
        "sleep_end": m.sleep_end,
        "night_valid": m.night_valid,
        "resting_hr": m.resting_hr,
        "peak_hr": m.peak_hr,
        "computed_at": now,
    }


def _union(spans: Iterable[UtcRange]) -> list[UtcRange]:
    """Sorted spans with the overlapping and touching ones joined."""
    joined: list[UtcRange] = []
    for start, end in sorted(spans):
        if joined and start <= joined[-1][1]:
            joined[-1] = (joined[-1][0], max(joined[-1][1], end))
        else:
            joined.append((start, end))
    return joined
