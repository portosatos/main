"""Classification of parsed records into new / duplicate / conflict / invalid (SPEC F4.2).

Records go in batches. A batch is copied into staging tables (`COPY`) and compared with the
stored raw records by one SQL query per record type; then records inside the batch are compared
with each other in line order; only `new` records are inserted. On a conflict the first loaded
record wins: stored records first, then earlier lines of the file (ADR-030). The result does not
depend on the batch size. After every batch the derived minutes its new records touch are
recomputed in the same transaction (services/minutes.py, ADR-032).
"""

import bisect
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ingest.devices import DeviceResolver
from app.services.ingest.parser import HeartRate, Invalid, Line, Meta, Sleep, Steps
from app.services.minutes import DirtyMinutes, recompute

BATCH_SIZE = 5000
# Errors (invalid and conflicting lines) kept in the report; the counters count all of them.
ERRORS_LIMIT = 50


@dataclass(frozen=True, slots=True)
class IngestError:
    line: int
    kind: Literal["invalid", "conflict"]
    reason: str


@dataclass(slots=True)
class Counts:
    new: int = 0
    duplicate: int = 0
    conflict: int = 0
    invalid: int = 0
    errors: list[IngestError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.new + self.duplicate + self.conflict + self.invalid

    def reject(self, line: int, kind: Literal["invalid", "conflict"], reason: str) -> None:
        if kind == "invalid":
            self.invalid += 1
        else:
            self.conflict += 1
        if len(self.errors) < ERRORS_LIMIT:
            self.errors.append(IngestError(line, kind, reason))


async def ingest_records(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    now: datetime,
    lines: Iterable[Line],
    batch_size: int = BATCH_SIZE,
) -> Counts:
    """Classify and store the records of `lines` for the user; `now` (from Clock) becomes
    `ingested_at`. Devices are created on first sight. Does not commit."""
    counts = Counts()
    devices = DeviceResolver(session, user_id=user_id, now=now)
    writer = _BatchWriter(session, job_id=job_id, now=now)
    batch: list[tuple[int, Steps | Sleep | HeartRate]] = []

    async def flush() -> None:
        if batch:
            ids, warnings = await devices.resolve({record.device for _, record in batch})
            counts.warnings.extend(warnings)
            dirty = await writer.write(batch, ids, counts)
            await recompute(session, dirty)
            batch.clear()

    for line in lines:
        record = line.record
        if isinstance(record, Invalid):
            counts.reject(line.number, "invalid", record.reason)
        elif isinstance(record, Meta):
            # Records above the meta line meet their devices before it, whatever the batch size.
            await flush()
            await devices.register(record)
        else:
            batch.append((line.number, record))
            if len(batch) >= batch_size:
                await flush()
    await flush()
    return counts


# Each staging table is temporary: private to the connection, dropped at commit.
STAGE_STEPS = """
CREATE TEMP TABLE IF NOT EXISTS ingest_stage_steps (
    line int, device_id uuid, start_utc timestamptz, end_utc timestamptz, count int
) ON COMMIT DROP"""
STAGE_SLEEP = """
CREATE TEMP TABLE IF NOT EXISTS ingest_stage_sleep (
    line int, device_id uuid, start_utc timestamptz, end_utc timestamptz
) ON COMMIT DROP"""
STAGE_HR = """
CREATE TEMP TABLE IF NOT EXISTS ingest_stage_hr (
    line int, device_id uuid, ts_utc timestamptz, bpm smallint
) ON COMMIT DROP"""

# Verdict of every staged record against the stored ones: NULL when nothing stored matches.
# The overlap check uses the same range expression as the exclusion constraint, so its GiST
# index serves it.
CLASSIFY_STEPS = """
SELECT s.line,
       CASE
           WHEN r.device_id IS NOT NULL AND r.count = s.count THEN 'duplicate'
           WHEN r.device_id IS NOT NULL THEN 'value'
           WHEN EXISTS (
               SELECT 1 FROM steps_raw o
               WHERE o.device_id = s.device_id
                 AND tstzrange(o.start_utc, o.end_utc, '[)')
                     && tstzrange(s.start_utc, s.end_utc, '[)')
           ) THEN 'overlap'
       END AS verdict,
       r.count AS stored
FROM ingest_stage_steps s
LEFT JOIN steps_raw r
       ON r.device_id = s.device_id AND r.start_utc = s.start_utc AND r.end_utc = s.end_utc"""
CLASSIFY_SLEEP = """
SELECT s.line,
       CASE WHEN r.device_id IS NOT NULL THEN 'duplicate' END AS verdict,
       NULL::int AS stored
FROM ingest_stage_sleep s
LEFT JOIN sleep_raw r
       ON r.device_id = s.device_id AND r.start_utc = s.start_utc AND r.end_utc = s.end_utc"""
CLASSIFY_HR = """
SELECT s.line,
       CASE
           WHEN r.device_id IS NOT NULL AND r.bpm = s.bpm THEN 'duplicate'
           WHEN r.device_id IS NOT NULL THEN 'value'
       END AS verdict,
       r.bpm::int AS stored
FROM ingest_stage_hr s
LEFT JOIN hr_point r ON r.device_id = s.device_id AND r.ts_utc = s.ts_utc"""

# The accepted lines are joined, not matched with `= ANY(array)`: that scans the array per row.
INSERT_STEPS = """
INSERT INTO steps_raw (device_id, start_utc, end_utc, count, ingest_job_id, ingested_at)
SELECT device_id, start_utc, end_utc, count, $1, $2 FROM ingest_stage_steps
JOIN unnest($3::int[]) AS accepted(line) USING (line)"""
INSERT_SLEEP = """
INSERT INTO sleep_raw (device_id, start_utc, end_utc, ingest_job_id, ingested_at)
SELECT device_id, start_utc, end_utc, $1, $2 FROM ingest_stage_sleep
JOIN unnest($3::int[]) AS accepted(line) USING (line)"""
INSERT_HR = """
INSERT INTO hr_point (device_id, ts_utc, bpm, ingest_job_id, ingested_at)
SELECT device_id, ts_utc, bpm, $1, $2 FROM ingest_stage_hr
JOIN unnest($3::int[]) AS accepted(line) USING (line)"""

Interval = tuple[datetime, datetime]


class _BatchWriter:
    def __init__(self, session: AsyncSession, *, job_id: uuid.UUID, now: datetime) -> None:
        self._session = session
        self._job_id = job_id
        self._now = now

    async def write(
        self,
        batch: Sequence[tuple[int, Steps | Sleep | HeartRate]],
        device_ids: dict[str, uuid.UUID],
        counts: Counts,
    ) -> DirtyMinutes:
        """Store the `new` records of the batch; returns the minutes they touch."""
        conn = await self._driver_connection()
        dirty = DirtyMinutes()
        steps = [(n, device_ids[r.device], r) for n, r in batch if isinstance(r, Steps)]
        sleep = [(n, device_ids[r.device], r) for n, r in batch if isinstance(r, Sleep)]
        pulse = [(n, device_ids[r.device], r) for n, r in batch if isinstance(r, HeartRate)]
        if steps:
            await self._steps(conn, steps, counts, dirty)
        if sleep:
            await self._sleep(conn, sleep, counts, dirty)
        if pulse:
            await self._pulse(conn, pulse, counts, dirty)
        return dirty

    async def _driver_connection(self) -> asyncpg.Connection:
        """The asyncpg connection under the session, inside its transaction: COPY needs it."""
        connection = await self._session.connection()
        raw = await connection.get_raw_connection()
        return raw.driver_connection

    async def _stage(
        self, conn: asyncpg.Connection, ddl: str, table: str, columns: list[str], rows: list
    ) -> dict[int, tuple[str | None, int | None]]:
        """Copy `rows` into the staging table and return {line: (verdict, stored value)}."""
        await conn.execute(ddl)
        await conn.execute(f"TRUNCATE {table}")
        await conn.copy_records_to_table(table, records=rows, columns=columns)
        query = {
            "ingest_stage_steps": CLASSIFY_STEPS,
            "ingest_stage_sleep": CLASSIFY_SLEEP,
            "ingest_stage_hr": CLASSIFY_HR,
        }[table]
        return {r["line"]: (r["verdict"], r["stored"]) for r in await conn.fetch(query)}

    async def _insert(self, conn: asyncpg.Connection, sql: str, lines: list[int]) -> None:
        if lines:
            await conn.execute(sql, self._job_id, self._now, lines)

    async def _steps(
        self,
        conn: asyncpg.Connection,
        items: list[tuple[int, uuid.UUID, Steps]],
        counts: Counts,
        dirty: DirtyMinutes,
    ) -> None:
        rows = [(n, d, r.start, r.end, r.count) for n, d, r in items]
        columns = ["line", "device_id", "start_utc", "end_utc", "count"]
        verdicts = await self._stage(conn, STAGE_STEPS, "ingest_stage_steps", columns, rows)

        accepted: list[int] = []
        by_key: dict[tuple[uuid.UUID, datetime, datetime], tuple[int, int]] = {}
        # Accepted intervals of each device, sorted and never overlapping each other.
        intervals: dict[uuid.UUID, list[Interval]] = {}
        interval_lines: dict[tuple[uuid.UUID, Interval], int] = {}
        for line, device_id, record in items:
            verdict, stored = verdicts[line]
            if verdict == "duplicate":
                counts.duplicate += 1
            elif verdict == "value":
                reason = f"этот интервал уже загружен с count={stored}"
                counts.reject(line, "conflict", reason)
            elif verdict == "overlap":
                reason = "интервал пересекается с уже загруженным интервалом устройства"
                counts.reject(line, "conflict", reason)
            elif (first := by_key.get((device_id, record.start, record.end))) is not None:
                first_line, first_count = first
                if first_count == record.count:
                    counts.duplicate += 1
                else:
                    reason = f"этот интервал уже есть в строке {first_line} с count={first_count}"
                    counts.reject(line, "conflict", reason)
            else:
                device_intervals = intervals.setdefault(device_id, [])
                other = _overlapping(device_intervals, (record.start, record.end))
                if other is not None:
                    other_line = interval_lines[(device_id, other)]
                    reason = f"интервал пересекается с интервалом из строки {other_line}"
                    counts.reject(line, "conflict", reason)
                else:
                    bisect.insort(device_intervals, (record.start, record.end))
                    interval_lines[(device_id, (record.start, record.end))] = line
                    by_key[(device_id, record.start, record.end)] = (line, record.count)
                    accepted.append(line)
                    dirty.add(device_id, record.start, record.end)
        await self._insert(conn, INSERT_STEPS, accepted)
        counts.new += len(accepted)

    async def _sleep(
        self,
        conn: asyncpg.Connection,
        items: list[tuple[int, uuid.UUID, Sleep]],
        counts: Counts,
        dirty: DirtyMinutes,
    ) -> None:
        # Overlaps are allowed: only an exact repeat of the interval is a duplicate.
        rows = [(n, d, r.start, r.end) for n, d, r in items]
        columns = ["line", "device_id", "start_utc", "end_utc"]
        verdicts = await self._stage(conn, STAGE_SLEEP, "ingest_stage_sleep", columns, rows)

        accepted: list[int] = []
        seen: set[tuple[uuid.UUID, datetime, datetime]] = set()
        for line, device_id, record in items:
            key = (device_id, record.start, record.end)
            if verdicts[line][0] == "duplicate" or key in seen:
                counts.duplicate += 1
            else:
                seen.add(key)
                accepted.append(line)
                dirty.add(device_id, record.start, record.end)
        await self._insert(conn, INSERT_SLEEP, accepted)
        counts.new += len(accepted)

    async def _pulse(
        self,
        conn: asyncpg.Connection,
        items: list[tuple[int, uuid.UUID, HeartRate]],
        counts: Counts,
        dirty: DirtyMinutes,
    ) -> None:
        rows = [(n, d, r.ts, r.bpm) for n, d, r in items]
        columns = ["line", "device_id", "ts_utc", "bpm"]
        verdicts = await self._stage(conn, STAGE_HR, "ingest_stage_hr", columns, rows)

        accepted: list[int] = []
        by_key: dict[tuple[uuid.UUID, datetime], tuple[int, int]] = {}
        for line, device_id, record in items:
            verdict, stored = verdicts[line]
            if verdict == "duplicate":
                counts.duplicate += 1
            elif verdict == "value":
                counts.reject(line, "conflict", f"пульс на этот момент уже загружен: bpm={stored}")
            elif (first := by_key.get((device_id, record.ts))) is not None:
                first_line, first_bpm = first
                if first_bpm == record.bpm:
                    counts.duplicate += 1
                else:
                    reason = f"пульс на этот момент уже есть в строке {first_line}: bpm={first_bpm}"
                    counts.reject(line, "conflict", reason)
            else:
                by_key[(device_id, record.ts)] = (line, record.bpm)
                accepted.append(line)
                dirty.add_point(device_id, record.ts)
        await self._insert(conn, INSERT_HR, accepted)
        counts.new += len(accepted)


def _overlapping(intervals: list[Interval], new: Interval) -> Interval | None:
    """An interval of the sorted non-overlapping `intervals` that overlaps `new` ([start, end))."""
    i = bisect.bisect_left(intervals, new)
    if i > 0 and intervals[i - 1][1] > new[0]:
        return intervals[i - 1]
    if i < len(intervals) and intervals[i][0] < new[1]:
        return intervals[i]
    return None
