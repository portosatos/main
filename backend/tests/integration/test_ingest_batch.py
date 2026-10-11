"""Stream batches (SPEC F3, F9, §6.3; plan step 11.1): `POST /api/ingest/batch` puts up to 5000
records in a job that the worker runs through the file pipeline, and the rules are evaluated
10 s (by Clock) after the stream batches, not after every one of them.

Like test_ingest_jobs.py these commit for real: the API and the worker use their own
connections. Users get `@jobs.example.com` addresses and are deleted by the `clean` fixture.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.clock import Clock
from app.config import Settings
from app.db import create_sessionmaker
from app.models import DailySummary
from tests.integration.ingest import ndjson
from tests.integration.test_goals import api_user
from tests.integration.test_ingest_jobs import (
    META,
    day_records,
    days_file,
    get_job,
    make_worker,
    raw_rows,
    upload,
    user_client,
    wait_until,
    wipe,
)

DEVICES = META["devices"]
MOSCOW = ZoneInfo("Europe/Moscow")  # the zone the test users register with
D = date(2026, 10, 10)
# 09:00 in Moscow on D: R1 looks at the nights D−2 … D.
MORNING = datetime.combine(D, time(9, 0), MOSCOW).astimezone(UTC)


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


async def post_batch(
    client: httpx.AsyncClient, records: list[Any], devices: list[dict] | None = DEVICES
) -> httpx.Response:
    body: dict[str, Any] = {"records": records}
    if devices is not None:
        body["devices"] = devices
    return await client.post("/api/ingest/batch", json=body)


async def send_batch(client: httpx.AsyncClient, records: list[Any]) -> str:
    response = await post_batch(client, records)
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


async def queued_jobs(engine: AsyncEngine, user_id: uuid.UUID | str) -> list[tuple[str, datetime]]:
    """(kind, run_after) of the user's queued jobs."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT kind, run_after FROM jobs WHERE user_id = :u AND status = 'queued'"
                " ORDER BY id"
            ),
            {"u": user_id},
        )
        return [tuple(row) for row in result.all()]


async def jobs_of_kind(engine: AsyncEngine, user_id: uuid.UUID | str, kind: str) -> int:
    async with engine.connect() as conn:
        return await conn.scalar(
            text("SELECT count(*) FROM jobs WHERE user_id = :u AND kind = :k"),
            {"u": user_id, "k": kind},
        )


async def recommendations(engine: AsyncEngine, user_id: uuid.UUID | str) -> list[dict]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT rule_code, status, opened_at FROM recommendations"
                " WHERE user_id = :u ORDER BY opened_at, rule_code"
            ),
            {"u": user_id},
        )
        return [dict(row._mapping) for row in result]


async def short_nights(engine: AsyncEngine, user_id: uuid.UUID, *nights: date) -> None:
    """Valid 5 h nights on `nights` (wake days): R1 opens when the rules look at them."""
    async with create_sessionmaker(engine)() as session:
        for night in nights:
            session.add(
                DailySummary(
                    user_id=user_id,
                    local_date=night,
                    status="partial",
                    wear_minutes=600,
                    sleep_minutes=300,
                    night_valid=True,
                    computed_at=datetime(2026, 10, 1, tzinfo=UTC),
                )
            )
        await session.commit()


def far_steps(minute: int) -> dict[str, Any]:
    """A step interval of the watch on 2026-09-01: its date is far from the nights of R1."""
    start = datetime(2026, 9, 1, 12, 0, tzinfo=UTC) + timedelta(minutes=minute)
    return {
        "type": "steps",
        "device": "watch-1",
        "start": start.isoformat(),
        "end": (start + timedelta(minutes=1)).isoformat(),
        "count": 10,
    }


async def day_range(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/api/summary/range?from=2026-09-30&to=2026-10-04")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.xfail(strict=True, reason="step 11.1: not implemented")
async def test_batch_202_same_classification_as_file(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    good = day_records(0)[:3]
    clash = dict(good[0], count=999)  # same interval, another count → conflict
    file_data = ndjson(META, *good, good[1]) + b"not json\n" + ndjson(clash)
    # The same records in a batch; a string is the batch's "line that is not a record".
    records = [*good, good[1], "not json", clash]
    worker = make_worker(db_engine)

    async with user_client(settings, "file") as file_client:
        file_job_id = await upload(file_client, file_data)
        assert await worker.run_until_idle() == 1
        file_job = await get_job(file_client, file_job_id)
        file_rows = await raw_rows(db_engine, file_client)

    async with user_client(settings, "stream") as client:
        response = await post_batch(client, records)
        assert response.status_code == 202, response.text
        job_id = response.json()["job_id"]
        # Accepted, not processed: the worker does it.
        queued = await get_job(client, job_id)
        assert (queued["source"], queued["status"]) == ("stream", "queued")

        assert await worker.run_until_idle() == 1
        job = await get_job(client, job_id)
        stream_rows = await raw_rows(db_engine, client)
        devices = (await client.get("/api/devices")).json()

    assert job["status"] == "done"
    assert job["counts"] == file_job["counts"]
    assert job["counts"] == {"total": 6, "new": 3, "duplicate": 1, "conflict": 1, "invalid": 1}
    # In a batch `line` is the number of the record in `records`, from 1.
    assert [(e["line"], e["kind"]) for e in job["errors"]] == [(5, "invalid"), (6, "conflict")]
    assert [e["kind"] for e in job["errors"]] == [e["kind"] for e in file_job["errors"]]
    assert stream_rows == file_rows
    # The devices come from the `devices` field of the body, like from the meta line of a file.
    assert sorted((d["external_id"], d["kind"], d["name"]) for d in devices) == [
        ("phone-1", "phone", "Телефон"),
        ("watch-1", "watch", "Часы"),
    ]
    # Nothing of the batch is left on the ingest volume.
    assert not [p for p in settings.ingest_dir.rglob("*") if p.is_file()]


@pytest.mark.xfail(strict=True, reason="step 11.1: not implemented")
async def test_batch_over_5000_rejected(clean: None, settings: Settings) -> None:
    records = [far_steps(minute) for minute in range(5001)]
    async with user_client(settings, "limit") as client:
        too_many = await post_batch(client, records)
        not_a_list = await client.post("/api/ingest/batch", json={"records": {"type": "steps"}})
        no_records = await client.post("/api/ingest/batch", json={"devices": DEVICES})
        after_rejected = (await client.get("/api/ingest/jobs")).json()
        # Control: exactly 5000 is accepted.
        at_limit = await post_batch(client, records[:5000])

    assert too_many.status_code == 413, too_many.text
    assert "5000" in too_many.json()["detail"]
    assert not_a_list.status_code == 422
    assert no_records.status_code == 422
    assert after_rejected == [], "a rejected batch creates no job"
    assert at_limit.status_code == 202, at_limit.text


@pytest.mark.xfail(strict=True, reason="step 11.1: not implemented")
async def test_stream_then_file_all_duplicate_totals_unchanged(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    records = [r for day in (0, 1, 2) for r in day_records(day)]  # 216 records
    worker = make_worker(db_engine)
    async with user_client(settings, "stream-file") as client:
        stream_jobs = [
            await send_batch(client, records[i : i + 100]) for i in range(0, len(records), 100)
        ]
        assert await worker.run_until_idle() == 3
        streamed = [await get_job(client, job_id) for job_id in stream_jobs]
        rows_after_stream = await raw_rows(db_engine, client)
        days_after_stream = await day_range(client)

        file_job_id = await upload(client, days_file(0, 1, 2))
        assert await worker.run_until_idle() == 1
        file_job = await get_job(client, file_job_id)
        rows_after_file = await raw_rows(db_engine, client)
        days_after_file = await day_range(client)

    assert [job["status"] for job in streamed] == ["done"] * 3
    assert sum(job["counts"]["new"] for job in streamed) == 216
    assert file_job["counts"] == {
        "total": 216,
        "new": 0,
        "duplicate": 216,
        "conflict": 0,
        "invalid": 0,
    }
    assert len(rows_after_stream) == 216
    assert rows_after_file == rows_after_stream
    assert sum(day["steps"] or 0 for day in days_after_stream) > 0
    assert days_after_file == days_after_stream


@pytest.mark.xfail(strict=True, reason="step 11.1: not implemented")
async def test_rule_evaluation_debounced_10s(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with api_user(settings, "debounce", at=MORNING) as (client, clock, user_id):
        await short_nights(db_engine, user_id, D - timedelta(days=2), D - timedelta(days=1), D)
        worker = make_worker(db_engine, clock)
        t0 = clock.at

        await send_batch(client, [far_steps(0)])
        assert await worker.run_until_idle() == 1
        # Not after the batch itself: the evaluation waits 10 s by Clock.
        assert await recommendations(db_engine, user_id) == []
        assert await queued_jobs(db_engine, user_id) == [
            ("evaluate_rules", t0 + timedelta(seconds=10))
        ]

        # A batch inside the 10 s joins the waiting evaluation and does not move it.
        clock.at = t0 + timedelta(seconds=4)
        await send_batch(client, [far_steps(1)])
        assert await worker.run_until_idle() == 1
        assert await recommendations(db_engine, user_id) == []
        assert await queued_jobs(db_engine, user_id) == [
            ("evaluate_rules", t0 + timedelta(seconds=10))
        ]

        clock.at = t0 + timedelta(seconds=10) - timedelta(milliseconds=1)
        assert await worker.run_until_idle() == 0
        assert await recommendations(db_engine, user_id) == []

        clock.at = t0 + timedelta(seconds=10)
        assert await worker.run_until_idle() == 1

    [opened] = await recommendations(db_engine, user_id)
    assert (opened["rule_code"], opened["status"]) == ("R1", "open")
    assert opened["opened_at"] == t0 + timedelta(seconds=10)
    # Two batches, one evaluation.
    assert await jobs_of_kind(db_engine, user_id, "evaluate_rules") == 1
    assert await queued_jobs(db_engine, user_id) == []
    assert make_worker(db_engine).rules_debounce_s == 10


@pytest.mark.xfail(strict=True, reason="step 11.1: not implemented")
async def test_debounced_evaluation_runs_when_due_without_new_jobs(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    """Beyond the plan: the worker loop wakes for a delayed job when it is due, not on the next
    30 s tick or the next NOTIFY."""
    worker = make_worker(db_engine, Clock(app_env="test"), tick_s=30, rules_debounce_s=0.3)
    first_rules_tick = asyncio.Event()
    hourly_tick = worker.rules_tick

    async def rules_tick() -> None:
        await hourly_tick()
        first_rules_tick.set()

    worker.rules_tick = rules_tick  # type: ignore[method-assign]
    stop = asyncio.Event()
    loop_task = asyncio.create_task(worker.run(stop))
    try:
        assert await wait_until(lambda: _ticked(first_rules_tick, loop_task), timeout_s=5)
        # The data appear after the loop's first rules tick: only the batch can evaluate them.
        today = datetime.now(MOSCOW).date()
        async with user_client(settings, "due") as client:
            user_id = uuid.UUID((await client.get("/api/auth/me")).json()["id"])
            await short_nights(db_engine, user_id, *(today - timedelta(days=n) for n in range(3)))
            await send_batch(client, [far_steps(0)])

            async def opened() -> bool:
                if loop_task.done():
                    loop_task.result()  # re-raise the loop's error
                return bool(await recommendations(db_engine, user_id))

            assert await wait_until(opened, timeout_s=5), "the delayed evaluation did not run"
    finally:
        stop.set()
        await asyncio.wait_for(loop_task, timeout=10)


async def _ticked(event: asyncio.Event, loop_task: asyncio.Task) -> bool:
    if loop_task.done():
        loop_task.result()  # re-raise the loop's error
    return event.is_set()
