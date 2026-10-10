"""Derived minute tables of a device: steps_minute, sleep_minute, coverage_minute (SPEC F4.3).

They are a cache of the raw records: the rows of a minute range are deleted and computed again
from steps_raw, sleep_raw and hr_point, so a recompute is idempotent and a full rebuild equals
the incremental result. A minute's rows depend only on the raw records overlapping that minute,
so the ingest recomputes just the minutes its new records touch, after every batch and in the
batch's transaction (ADR-032).

Step contributions are summed as `numeric` and stored as `real`: the sum is exact, so the
stored value does not depend on which records were added in which batch.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CoverageMinute, Device, HrPoint, SleepMinute, SleepRaw, StepsMinute, StepsRaw
from app.worker.queue import lock_user

MINUTE = timedelta(minutes=1)
# A full rebuild goes in ranges of this length, so no statement covers months at once.
REBUILD_CHUNK = timedelta(days=7)

Range = tuple[uuid.UUID, datetime, datetime]


def floor_minute(ts: datetime) -> datetime:
    return ts.astimezone(UTC).replace(second=0, microsecond=0)


def ceil_minute(ts: datetime) -> datetime:
    floor = floor_minute(ts)
    return floor if floor == ts else floor + MINUTE


class DirtyMinutes:
    """Minute ranges [start, end) of each device whose derived rows are stale."""

    def __init__(self) -> None:
        self._spans: defaultdict[uuid.UUID, list[tuple[datetime, datetime]]] = defaultdict(list)

    def __bool__(self) -> bool:
        return bool(self._spans)

    def add(self, device_id: uuid.UUID, start: datetime, end: datetime) -> None:
        """Mark the minutes that the record span [start, end) touches."""
        self._spans[device_id].append((floor_minute(start), ceil_minute(end)))

    def add_point(self, device_id: uuid.UUID, ts: datetime) -> None:
        """Mark the minute of the instant `ts`."""
        minute = floor_minute(ts)
        self._spans[device_id].append((minute, minute + MINUTE))

    def ranges(self) -> list[Range]:
        """Merged ranges, sorted by device and start: overlapping and touching spans become one,
        so the ranges of a device never share a minute."""
        merged: list[Range] = []
        for device_id in sorted(self._spans):
            current: tuple[datetime, datetime] | None = None
            for start, end in sorted(self._spans[device_id]):
                if current is not None and start <= current[1]:
                    current = (current[0], max(current[1], end))
                    continue
                if current is not None:
                    merged.append((device_id, *current))
                current = (start, end)
            if current is not None:
                merged.append((device_id, *current))
        return merged


@dataclass(frozen=True, slots=True)
class RebuildResult:
    devices: int
    steps_minutes: int
    sleep_minutes: int
    coverage_minutes: int


# The dirty ranges come as three arrays. Every range starts and ends on a minute border and the
# ranges of a device are disjoint, so no minute is produced twice.
DIRTY = """unnest(CAST(:devices AS uuid[]), CAST(:starts AS timestamptz[]),
                   CAST(:ends AS timestamptz[])) AS d(device_id, a, b)"""

# The minutes of [lo, hi) as a set-returning expression (hi is exclusive, hence the microsecond:
# the resolution of timestamptz).
MINUTES_OF = """generate_series(date_trunc('minute', {lo}, 'UTC'),
                                {hi} - interval '1 microsecond', interval '1 minute')"""

STEPS_OVERLAPPING = """steps_raw r ON r.device_id = d.device_id
    AND tstzrange(r.start_utc, r.end_utc, '[)') && tstzrange(d.a, d.b, '[)')"""
# A sleep interval is at most 24 h long (SPEC §7.2): the bound lets the primary key serve.
SLEEP_OVERLAPPING = """sleep_raw r ON r.device_id = d.device_id
    AND r.start_utc < d.b AND r.start_utc > d.a - interval '24 hours' AND r.end_utc > d.a"""

DELETE = (
    "DELETE FROM {table} t USING "
    + DIRTY
    + """
WHERE t.device_id = d.device_id AND t.minute_utc >= d.a AND t.minute_utc < d.b"""
)

# count × (seconds of the overlap with the minute) / (seconds of the interval), summed per minute.
INSERT_STEPS = f"""
INSERT INTO steps_minute (device_id, minute_utc, steps)
SELECT r.device_id, m.minute,
       sum(r.count * extract(epoch FROM least(r.end_utc, m.minute + interval '1 minute')
                                        - greatest(r.start_utc, m.minute))
           / extract(epoch FROM r.end_utc - r.start_utc))::real
FROM {DIRTY}
JOIN {STEPS_OVERLAPPING}
CROSS JOIN LATERAL {MINUTES_OF.format(lo="greatest(r.start_utc, d.a)", hi="least(r.end_utc, d.b)")}
    AS m(minute)
GROUP BY r.device_id, m.minute"""

# Sleep intervals may overlap: their union inside the range is cut into disjoint pieces first,
# so a second covered twice counts once.
INSERT_SLEEP = f"""
INSERT INTO sleep_minute (device_id, minute_utc)
SELECT u.device_id, m.minute
FROM (
    SELECT d.device_id,
           unnest(range_agg(tstzrange(r.start_utc, r.end_utc, '[)') * tstzrange(d.a, d.b, '[)')))
               AS piece
    FROM {DIRTY}
    JOIN {SLEEP_OVERLAPPING}
    GROUP BY d.device_id, d.a
) u
CROSS JOIN LATERAL {MINUTES_OF.format(lo="lower(u.piece)", hi="upper(u.piece)")} AS m(minute)
GROUP BY u.device_id, m.minute
HAVING sum(extract(epoch FROM least(upper(u.piece), m.minute + interval '1 minute')
                              - greatest(lower(u.piece), m.minute))) >= 30"""

INSERT_COVERAGE = f"""
INSERT INTO coverage_minute (device_id, minute_utc)
SELECT r.device_id, m.minute
FROM {DIRTY}
JOIN {STEPS_OVERLAPPING}
CROSS JOIN LATERAL {MINUTES_OF.format(lo="greatest(r.start_utc, d.a)", hi="least(r.end_utc, d.b)")}
    AS m(minute)
UNION
SELECT r.device_id, m.minute
FROM {DIRTY}
JOIN {SLEEP_OVERLAPPING}
CROSS JOIN LATERAL {MINUTES_OF.format(lo="greatest(r.start_utc, d.a)", hi="least(r.end_utc, d.b)")}
    AS m(minute)
UNION
SELECT h.device_id, date_trunc('minute', h.ts_utc, 'UTC')
FROM {DIRTY}
JOIN hr_point h ON h.device_id = d.device_id AND h.ts_utc >= d.a AND h.ts_utc < d.b"""

DERIVED = ("steps_minute", "sleep_minute", "coverage_minute")


async def recompute(session: AsyncSession, dirty: DirtyMinutes) -> None:
    """Delete the derived rows of the dirty ranges and insert them computed from raw records."""
    await _recompute_ranges(session, dirty.ranges())


async def _recompute_ranges(session: AsyncSession, ranges: list[Range]) -> None:
    if not ranges:
        return
    params = {
        "devices": [device_id for device_id, _, _ in ranges],
        "starts": [start for _, start, _ in ranges],
        "ends": [end for _, _, end in ranges],
    }
    for table in DERIVED:
        await session.execute(text(DELETE.format(table=table)), params)
    for insert in (INSERT_STEPS, INSERT_SLEEP, INSERT_COVERAGE):
        await session.execute(text(insert), params)


async def rebuild_user(session: AsyncSession, user_id: uuid.UUID) -> RebuildResult:
    """Drop every derived minute row of the user's devices and compute them from raw records.
    Waits for the user's running ingest job, if any (the same user lock as the worker)."""
    await lock_user(session, user_id)
    device_ids = list(
        (await session.scalars(select(Device.id).where(Device.user_id == user_id))).all()
    )
    for model in (StepsMinute, SleepMinute, CoverageMinute):
        await session.execute(model.__table__.delete().where(model.device_id.in_(device_ids)))

    for device_id in device_ids:
        span = await _raw_span(session, device_id)
        if span is None:
            continue
        start, end = floor_minute(span[0]), ceil_minute(span[1])
        while start < end:
            chunk_end = min(start + REBUILD_CHUNK, end)
            await _recompute_ranges(session, [(device_id, start, chunk_end)])
            start = chunk_end

    async def rows(model: type[StepsMinute | SleepMinute | CoverageMinute]) -> int:
        query = select(func.count()).select_from(model).where(model.device_id.in_(device_ids))
        return (await session.scalar(query)) or 0

    return RebuildResult(
        devices=len(device_ids),
        steps_minutes=await rows(StepsMinute),
        sleep_minutes=await rows(SleepMinute),
        coverage_minutes=await rows(CoverageMinute),
    )


async def _raw_span(
    session: AsyncSession, device_id: uuid.UUID
) -> tuple[datetime, datetime] | None:
    """The earliest start and the latest end of the device's raw records."""
    bounds = []
    for low, high in (
        (StepsRaw.start_utc, StepsRaw.end_utc),
        (SleepRaw.start_utc, SleepRaw.end_utc),
        (HrPoint.ts_utc, HrPoint.ts_utc + MINUTE),
    ):
        table = low.class_
        row = (
            await session.execute(
                select(func.min(low), func.max(high)).where(table.device_id == device_id)
            )
        ).one()
        if row[0] is not None:
            bounds.append((row[0], row[1]))
    if not bounds:
        return None
    return min(b[0] for b in bounds), max(b[1] for b in bounds)
