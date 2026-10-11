"""Daily summaries (SPEC F3, F5–F7): services/summaries.py and the daily_summaries table.

Most tests load data through the parser and the classifier in a rolled-back transaction, like the
other ingest tests, and recompute the dirty dates the upload reports. The worker test commits for
real, as in test_ingest_jobs.py: the summaries must appear while the job is still running.
"""

import asyncio
import dataclasses
import shutil
import subprocess
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app import cli
from app.config import Settings
from app.models import UserTimezone
from app.services.ingest.classify import Counts
from app.services.localtime import TzHistory
from app.services.merge import merge_steps
from app.services.metrics import DayMetrics, day_metrics
from app.services.summaries import rebuild_summaries, recompute_dates
from tests.integration.ingest import (
    NOW,
    coverage_minute_rows,
    make_user,
    ndjson,
    rows,
    steps_minute_rows,
    upload,
)
from tests.integration.test_ingest_jobs import (
    days_file,
    get_job,
    make_worker,
    user_client,
    wipe,
)
from tests.integration.test_ingest_jobs import upload as api_upload

MSK = timezone(timedelta(hours=3))
MINUTE = timedelta(minutes=1)
DAY = date(2026, 10, 5)
META = {
    "type": "meta",
    "schema": "ht.v1",
    "devices": [
        {"id": "watch-1", "kind": "watch", "name": "Часы"},
        {"id": "phone-1", "kind": "phone", "name": "Телефон"},
    ],
}
GENERATOR_DIR = Path(__file__).resolve().parents[3] / "generator"
# Three days of both devices with sleep, unaligned steps, pulse every minute and random gaps.
HTGEN_ARGS = [
    "--start", "2026-10-01",
    "--end", "2026-10-03",
    "--seed", "7",
    "--unaligned",
    "--hr-interval", "60",
    "--gap-prob", "0.3",
    "--gap-max-hours", "6",
]  # fmt: skip
SUMMARY_COLUMNS = [f.name for f in dataclasses.fields(DayMetrics)]


@pytest.fixture
async def session(
    test_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with test_sessionmaker() as session:
        yield session


def at(hour: int, minute: int = 0, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=MSK)


def steps(device: str, start: datetime, end: datetime, count: int) -> dict:
    return {
        "type": "steps",
        "device": device,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "count": count,
    }


def per_minute(device: str, start: datetime, counts: list[int]) -> list[dict]:
    return [
        steps(device, start + i * MINUTE, start + (i + 1) * MINUTE, c) for i, c in enumerate(counts)
    ]


def sleep(device: str, start: datetime, end: datetime) -> dict:
    return {"type": "sleep", "device": device, "start": start.isoformat(), "end": end.isoformat()}


def hr(device: str, ts: datetime, bpm: int) -> dict:
    return {"type": "hr", "device": device, "ts": ts.isoformat(), "bpm": bpm}


def pulse_every_minute(device: str, start: datetime, end: datetime, bpm: int = 60) -> list[dict]:
    return [hr(device, start + i * MINUTE, bpm) for i in range((end - start) // MINUTE)]


async def load(session: AsyncSession, user_id: uuid.UUID, *records: dict) -> Counts:
    _, counts = await upload(session, user_id, ndjson(META, *records))
    return counts


async def summary_rows(session: AsyncSession, user_id: uuid.UUID) -> dict[date, dict[str, Any]]:
    """{local_date: row} of the user's daily_summaries, computed_at included."""
    result = await session.execute(
        text("SELECT * FROM daily_summaries WHERE user_id = :u ORDER BY local_date"),
        {"u": user_id},
    )
    return {row["local_date"]: dict(row) for row in result.mappings()}


async def summary_hash(session: AsyncSession, user_id: uuid.UUID) -> tuple[int, str]:
    """(row count, md5 of the ordered rows) of the user's summaries without computed_at."""
    columns = ", ".join(f"coalesce({c}::text, '-')" for c in SUMMARY_COLUMNS)
    [(count, digest)] = await rows(
        session,
        f"SELECT count(*), md5(coalesce(string_agg(concat_ws('|', {columns}), ',' "
        "ORDER BY local_date), '')) FROM daily_summaries WHERE user_id = :u",
        u=user_id,
    )
    return count, digest


def as_metrics(row: dict[str, Any]) -> dict[str, Any]:
    """The DayMetrics fields of a row; REAL columns compare approximately."""
    return {
        c: pytest.approx(row[c]) if c.endswith("_hr") and row[c] is not None else row[c]
        for c in SUMMARY_COLUMNS
    }


async def test_night_valid_on_partial_day(session: AsyncSession) -> None:
    # SPEC F6, §8 stage 4: the night is recorded whole (sleep 23:40–07:10, data 22:00–08:30), the
    # watch is off for the rest of the day: the day is partial, the night is valid.
    user_id = await make_user(session, tz="Europe/Moscow")
    eve = DAY - timedelta(days=1)
    counts = await load(
        session,
        user_id,
        sleep("watch-1", at(23, 40, eve), at(0)),  # htgen cuts sleep at midnight
        sleep("watch-1", at(0), at(7, 10)),
        *pulse_every_minute("watch-1", at(22, 0, eve), at(8, 30)),
    )
    await recompute_dates(session, user_id, counts.dirty_dates, NOW)

    found = await summary_rows(session, user_id)

    assert set(found) == {eve, DAY}
    day = found[DAY]
    assert (day["status"], day["wear_minutes"]) == ("partial", 510)
    assert (day["sleep_minutes"], day["sleep_start"], day["sleep_end"], day["night_valid"]) == (
        450,
        at(23, 40, eve),
        at(7, 10),
        True,
    )
    evening = found[eve]
    assert (evening["status"], evening["wear_minutes"]) == ("partial", 120)
    assert (evening["sleep_minutes"], evening["night_valid"]) == (None, False)


async def test_tz_move_period_sum_equals_sum_of_merged_minutes(session: AsyncSession) -> None:
    # SPEC F5, §8 stage 4, §9 #18: Moscow → New York on Oct 3 at 12:00Z (Oct 3 lasts 31 hours)
    # and back on Oct 6 at 00:00Z (Oct 5 lasts 20 hours, Oct 6 — 21). The days' steps and wear
    # time add up to the merged minutes of the period: no minute is lost or counted twice.
    user_id = await make_user(session, tz=None)
    for tz, since in (
        ("Europe/Moscow", datetime(2026, 9, 1, tzinfo=UTC)),
        ("America/New_York", datetime(2026, 10, 3, 12, tzinfo=UTC)),
        ("Europe/Moscow", datetime(2026, 10, 6, tzinfo=UTC)),
    ):
        session.add(UserTimezone(user_id=user_id, tz=tz, valid_from=since, created_at=NOW))
    await session.flush()
    start = datetime(2026, 10, 1, tzinfo=UTC)
    watch_off = (datetime(2026, 10, 4, 6, tzinfo=UTC), datetime(2026, 10, 4, 18, tzinfo=UTC))
    records = []
    for i in range(0, 8 * 24 * 60, 7):
        minute = start + i * MINUTE
        if not watch_off[0] <= minute < watch_off[1]:
            records.append(steps("watch-1", minute, minute + MINUTE, i * 13 % 150))
        if i % 2 == 0:
            records.append(steps("phone-1", minute, minute + MINUTE, i * 7 % 120))
    counts = await load(session, user_id, *records)
    await recompute_dates(session, user_id, counts.dirty_dates, NOW)

    coverage: dict[str, set[datetime]] = {"watch-1": set(), "phone-1": set()}
    for device, minute in await coverage_minute_rows(session, user_id):
        coverage[device].add(minute)
    per_device: dict[str, dict[datetime, float]] = {"watch-1": {}, "phone-1": {}}
    for (device, minute), value in (await steps_minute_rows(session, user_id)).items():
        per_device[device][minute] = value
    merged = merge_steps(["watch-1", "phone-1"], coverage, per_device)
    history = TzHistory(
        (
            await session.execute(
                text("SELECT tz, valid_from FROM user_timezones WHERE user_id = :u"), {"u": user_id}
            )
        ).all()
    )
    found = await summary_rows(session, user_id)

    assert set(found) == {history.local_date(minute) for minute in merged}
    assert sum(day["wear_minutes"] for day in found.values()) == len(merged)
    assert sum(day["steps"] for day in found.values()) == sum(m.value for m in merged.values())
    # Data are spread evenly: the 31-hour Oct 3 has more of them than the 24-hour Oct 2.
    assert found[date(2026, 10, 3)]["wear_minutes"] > found[date(2026, 10, 2)]["wear_minutes"]


async def test_only_dirty_dates_recomputed(session: AsyncSession) -> None:
    # SPEC F3, F7: an upload recomputes only the dates its records can change. A walk on each of
    # Oct 1–5 and the night of Oct 3 → 4 (asleep 21:30–07:00, pulse 20:00–08:00).
    user_id = await make_user(session, tz="Europe/Moscow")
    days = [date(2026, 10, d) for d in range(1, 6)]
    oct2, oct3, oct4 = days[1], days[2], days[3]
    t1, t2, t3 = NOW, NOW + timedelta(hours=1), NOW + timedelta(hours=2)
    counts = await load(
        session,
        user_id,
        *(r for d in days for r in per_minute("watch-1", at(12, day=d), [100] * 10)),
        sleep("watch-1", at(21, 30, oct3), at(0, day=oct4)),
        sleep("watch-1", at(0, day=oct4), at(7, day=oct4)),
        *pulse_every_minute("watch-1", at(20, day=oct3), at(8, day=oct4)),
    )
    assert counts.dirty_dates == set(days)
    await recompute_dates(session, user_id, counts.dirty_dates, t1)
    assert (await summary_rows(session, user_id))[oct4]["sleep_minutes"] == 570

    # Another walk on Oct 2: only Oct 2 changes.
    counts = await load(session, user_id, steps("watch-1", at(15, day=oct2), at(15, 5, oct2), 300))
    assert counts.dirty_dates == {oct2}
    await recompute_dates(session, user_id, counts.dirty_dates, t2)
    found = await summary_rows(session, user_id)
    assert {d: r["computed_at"] for d, r in found.items()} == {
        d: t2 if d == oct2 else t1 for d in days
    }
    assert found[oct2]["steps"] == 1300

    # Sleep from 21:00 on Oct 3 lengthens the night that ends on Oct 4, far from the new record.
    counts = await load(session, user_id, sleep("watch-1", at(21, 0, oct3), at(21, 30, oct3)))
    assert counts.dirty_dates == {oct3, oct4}
    await recompute_dates(session, user_id, counts.dirty_dates, t3)
    found = await summary_rows(session, user_id)
    assert {d: r["computed_at"] for d, r in found.items()} == {
        d: t3 if d in (oct3, oct4) else t2 if d == oct2 else t1 for d in days
    }
    assert (found[oct4]["sleep_minutes"], found[oct4]["sleep_start"]) == (600, at(21, 0, oct3))


@pytest.fixture(scope="module")
def htgen_file(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    uv = shutil.which("uv")
    if uv is None:
        pytest.fail("uv is not on PATH: it runs the generator (generator/)", pytrace=False)
    out = tmp_path_factory.mktemp("htgen") / "summaries.ndjson"
    subprocess.run(
        [uv, "run", "--project", str(GENERATOR_DIR), "htgen", *HTGEN_ARGS, "--out", str(out)],
        check=True,
        timeout=300,
    )
    return out.read_bytes()


async def test_rebuild_reproduces_summaries(
    session: AsyncSession,
    test_sessionmaker: async_sessionmaker[AsyncSession],
    htgen_file: bytes,
) -> None:
    # Plan step 4.3, Done When: `htadmin rebuild` gives the summaries the ingest computed.
    user_id = await make_user(session, email="rebuild@example.com", tz="Europe/Moscow")
    other_id = await make_user(session, email="other@example.com", tz="Europe/Moscow")
    for user, batch_size in ((user_id, 997), (other_id, 5000)):
        _, counts = await upload(session, user, htgen_file, batch_size=batch_size)
        await recompute_dates(session, user, counts.dirty_dates, NOW)
    incremental = await summary_hash(session, user_id)
    other = await summary_hash(session, other_id)
    found = await summary_rows(session, user_id)
    assert len(found) >= 3
    assert any(day["night_valid"] for day in found.values())
    assert any(day["sleep_minutes"] for day in found.values())
    # The rows are gone: `htadmin rebuild` restores them from the minutes alone.
    await session.execute(text("DELETE FROM daily_summaries WHERE user_id = :u"), {"u": user_id})
    await session.commit()

    assert await cli.run(["rebuild", "--user", "rebuild@example.com"], test_sessionmaker) == 0

    assert await summary_hash(session, user_id) == incremental
    # A rebuild over the rows in place gives them again.
    assert await rebuild_summaries(session, user_id, NOW) == len(found)
    assert await summary_hash(session, user_id) == incremental
    assert await summary_hash(session, other_id) == other


# The worker test commits for real: users of @jobs.example.com are deleted around it.


@pytest.fixture
async def clean(db_engine: AsyncEngine) -> AsyncIterator[None]:
    await wipe(db_engine)
    yield
    await wipe(db_engine)


@pytest.fixture
def settings(migrated_database_url: str, tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=migrated_database_url,
        app_env="test",
        ingest_dir=tmp_path / "ingest",
    )


def pause_after(
    batch: int,
) -> tuple[Callable[[int], Awaitable[None]], asyncio.Event, asyncio.Event]:
    """A worker hook that stops after the given batch is committed until `resume` is set."""
    paused, resume = asyncio.Event(), asyncio.Event()

    async def hook(number: int) -> None:
        if number == batch:
            paused.set()
            await resume.wait()

    return hook, paused, resume


async def committed_summaries(engine: AsyncEngine, user_id: uuid.UUID) -> dict[date, dict]:
    async with AsyncSession(engine) as session:
        return await summary_rows(session, user_id)


async def test_summaries_exist_before_job_done(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    # SPEC F3, §9 #7: the summary is updated while the file is processed. Days 0 and 1 of
    # test_ingest_jobs (Oct 1 and 2 UTC: Moscow dates Oct 1–3), 10 lines a batch, a pause after
    # batch 3: lines 2–30 are in, they lie on Oct 1 (03:00–12:10 Moscow time).
    hook, paused, resume = pause_after(3)
    async with user_client(settings, "summary") as client:
        user_id = uuid.UUID((await client.get("/api/auth/me")).json()["id"])
        job_id = await api_upload(client, days_file(0, 1))
        worker = make_worker(db_engine, batch_size=10, on_batch=hook, summary_flush_s=0)
        run = asyncio.create_task(worker.run_until_idle())
        try:
            await asyncio.wait_for(paused.wait(), timeout=30)
            assert (await get_job(client, job_id))["status"] == "processing"
            found = await committed_summaries(db_engine, user_id)
            assert set(found) == {date(2026, 10, 1)}
            async with AsyncSession(db_engine) as session:
                expected = await day_metrics(session, user_id, date(2026, 10, 1))
            assert as_metrics(found[date(2026, 10, 1)]) == dataclasses.asdict(expected)
            assert 0 < expected.wear_minutes < 24 * 15
        finally:
            resume.set()
            await run
        assert (await get_job(client, job_id))["status"] == "done"

    found = await committed_summaries(db_engine, user_id)
    assert set(found) == {date(2026, 10, d) for d in (1, 2, 3)}
    async with AsyncSession(db_engine) as session:
        before = await summary_hash(session, user_id)
        await rebuild_summaries(session, user_id, NOW)
        assert await summary_hash(session, user_id) == before
        await session.rollback()
