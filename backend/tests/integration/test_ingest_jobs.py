"""File upload, the job queue and the worker (SPEC F3, §4; plan step 3.2).

Unlike the other integration tests these commit for real: the API, the worker and the queue use
separate connections (SKIP LOCKED, advisory locks, NOTIFY), which a rolled-back test transaction
cannot show. Users get `@jobs.example.com` addresses; the `clean` fixture deletes them (their jobs,
devices and records go by cascade) and the worker heartbeats before and after every test.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.clock import Clock
from app.config import Settings
from app.main import create_app
from app.worker.main import SimulatedCrash, Worker
from tests.integration.client import CSRF_HEADERS
from tests.integration.ingest import ndjson

NOT_IMPLEMENTED = pytest.mark.xfail(strict=True, reason="step 3.2: not implemented")

PASSWORD = "correct horse battery"
T0 = datetime(2026, 10, 1, tzinfo=UTC)
META = {
    "type": "meta",
    "schema": "ht.v1",
    "devices": [
        {"id": "watch-1", "kind": "watch", "name": "Часы"},
        {"id": "phone-1", "kind": "phone", "name": "Телефон"},
    ],
}


class MovableClock(Clock):
    """A Clock whose system time the test sets."""

    def __init__(self, now: datetime) -> None:
        self.at = now
        super().__init__(app_env="test", system_now=lambda: self.at)


def iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def day_records(day: int) -> list[dict[str, Any]]:
    """24 hourly step intervals of the watch, 24 pulse points of the watch and 24 step intervals
    of the phone on day `day` after T0: 72 records."""
    records = []
    for hour in range(24):
        start = T0 + timedelta(days=day, hours=hour)
        records += [
            {
                "type": "steps",
                "device": "watch-1",
                "start": iso(start),
                "end": iso(start + timedelta(minutes=10)),
                "count": 100 + hour,
            },
            {"type": "hr", "device": "watch-1", "ts": iso(start), "bpm": 60 + hour},
            {
                "type": "steps",
                "device": "phone-1",
                "start": iso(start + timedelta(minutes=20)),
                "end": iso(start + timedelta(minutes=25)),
                "count": 50 + hour,
            },
        ]
    return records


def days_file(*days: int) -> bytes:
    return ndjson(META, *(r for day in days for r in day_records(day)))


async def wipe(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users WHERE email LIKE '%@jobs.example.com'"))
        await conn.execute(
            text(
                "DO $$ BEGIN IF to_regclass('worker_heartbeat') IS NOT NULL THEN "
                "DELETE FROM worker_heartbeat; END IF; END $$"
            )
        )


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
        ingest_max_bytes=1_000_000,
    )


@asynccontextmanager
async def user_client(settings: Settings, name: str) -> AsyncIterator[httpx.AsyncClient]:
    """A client of a fresh app (committing for real) with a newly registered user logged in."""
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", headers=CSRF_HEADERS
        ) as client:
            body = {
                "email": f"{name}-{uuid.uuid4().hex[:8]}@jobs.example.com",
                "password": PASSWORD,
                "timezone": "Europe/Moscow",
            }
            registered = await client.post("/api/auth/register", json=body)
            assert registered.status_code == 201, registered.text
            yield client


async def upload(client: httpx.AsyncClient, data: bytes, name: str = "data.ndjson") -> str:
    response = await client.post(
        "/api/ingest/files", files={"file": (name, data, "application/x-ndjson")}
    )
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


async def get_job(client: httpx.AsyncClient, job_id: str) -> dict[str, Any]:
    response = await client.get(f"/api/ingest/jobs/{job_id}")
    assert response.status_code == 200, response.text
    return response.json()


def make_worker(engine: AsyncEngine, clock: Clock | None = None, **kwargs: Any) -> Worker:
    return Worker(engine, clock or Clock(app_env="test"), **kwargs)


async def wait_until(condition: Callable[[], Awaitable[bool]], timeout_s: float) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while asyncio.get_running_loop().time() < deadline:
        if await condition():
            return True
        await asyncio.sleep(0.05)
    return False


async def raw_rows(engine: AsyncEngine, client: httpx.AsyncClient) -> list[tuple]:
    """Every raw record of the client's user: (table, external_id, start/ts, end, value)."""
    user_id = (await client.get("/api/auth/me")).json()["id"]
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT 'steps', d.external_id, s.start_utc, s.end_utc, s.count FROM steps_raw s "
                "JOIN devices d ON d.id = s.device_id WHERE d.user_id = :u "
                "UNION ALL "
                "SELECT 'hr', d.external_id, h.ts_utc, NULL, h.bpm FROM hr_point h "
                "JOIN devices d ON d.id = h.device_id WHERE d.user_id = :u "
                "ORDER BY 1, 2, 3"
            ),
            {"u": user_id},
        )
        return [tuple(row) for row in result.all()]


def counts(job: dict[str, Any]) -> dict[str, int]:
    return job["counts"]


@NOT_IMPLEMENTED
async def test_upload_returns_202_before_processing_done(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    data = days_file(0)
    async with user_client(settings, "early") as client:
        response = await client.post(
            "/api/ingest/files", files={"file": ("day.ndjson", data, "application/x-ndjson")}
        )
        assert response.status_code == 202, response.text
        job_id = response.json()["job_id"]

        # No worker has run yet: the file is on disk and the job waits in the queue.
        job = await get_job(client, job_id)
        assert job["status"] == "queued"
        assert job["filename"] == "day.ndjson"
        assert job["bytes_total"] == len(data)
        assert job["bytes_done"] == 0
        stored = list((settings.ingest_dir).rglob("*"))
        assert [p.read_bytes() for p in stored if p.is_file()] == [data]

        assert await make_worker(db_engine).run_until_idle() == 1
        assert (await get_job(client, job_id))["status"] == "done"


@NOT_IMPLEMENTED
async def test_job_completes_with_counts_per_class(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    good = day_records(0)[:3]
    clash = dict(good[0], count=999)  # same interval, another count → conflict
    data = ndjson(META, *good, good[1]) + b"not json\n" + ndjson(clash)
    async with user_client(settings, "classes") as client:
        job_id = await upload(client, data)
        await make_worker(db_engine, batch_size=2).run_until_idle()
        job = await get_job(client, job_id)

    assert job["status"] == "done"
    assert counts(job) == {"total": 6, "new": 3, "duplicate": 1, "conflict": 1, "invalid": 1}
    assert job["bytes_done"] == job["bytes_total"] == len(data)
    assert job["progress"] == 1.0
    assert job["started_at"] is not None and job["finished_at"] is not None
    assert [(e["line"], e["kind"]) for e in job["errors"]] == [(6, "invalid"), (7, "conflict")]
    assert job["warnings"] == []
    # Assumption: a processed file is deleted from the volume.
    assert not [p for p in settings.ingest_dir.rglob("*") if p.is_file()]


@NOT_IMPLEMENTED
async def test_reupload_same_file_zero_new_all_duplicate(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    data = days_file(0, 1)
    async with user_client(settings, "again") as client:
        first = await upload(client, data)
        second = await upload(client, data)
        await make_worker(db_engine).run_until_idle()
        rows_after_both = await raw_rows(db_engine, client)
        first_job, second_job = await get_job(client, first), await get_job(client, second)

    assert counts(first_job)["new"] == 144
    assert counts(second_job) == {
        "total": 144,
        "new": 0,
        "duplicate": 144,
        "conflict": 0,
        "invalid": 0,
    }
    assert len(rows_after_both) == 144


@NOT_IMPLEMENTED
async def test_partially_overlapping_file_new_only_for_new_part(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with user_client(settings, "overlap") as client:
        await upload(client, days_file(0, 1))
        await make_worker(db_engine).run_until_idle()
        second = await upload(client, days_file(1, 2))
        await make_worker(db_engine).run_until_idle()
        job = await get_job(client, second)

    assert counts(job) == {"total": 144, "new": 72, "duplicate": 72, "conflict": 0, "invalid": 0}


@NOT_IMPLEMENTED
async def test_worker_crash_after_batch_k_resumes_same_result(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    records = day_records(0)[:40]
    data = ndjson(META, *records[:15]) + b"{broken\n" + ndjson(*records[15:])
    clock = MovableClock(T0)
    async with user_client(settings, "crash") as crashed, user_client(settings, "calm") as calm:
        crash_job = await upload(crashed, data)
        calm_job = await upload(calm, data)

        dying = make_worker(db_engine, clock, batch_size=10, crash_after_batch=2)
        claimed = await dying.claim()
        assert claimed is not None and claimed.payload["ingest_job_id"] == crash_job
        with pytest.raises(SimulatedCrash):
            await dying.process(claimed)

        # Two batches of 10 lines are committed together with the checkpoint.
        half = await get_job(crashed, crash_job)
        assert half["status"] == "processing"
        assert 0 < half["bytes_done"] < half["bytes_total"]
        assert counts(half)["total"] == 19  # line 1 is meta

        # Five minutes later the lock is stale: the job is back in the queue and resumes.
        clock.at = T0 + timedelta(minutes=5, seconds=1)
        survivor = make_worker(db_engine, clock, batch_size=10)
        await survivor.tick()
        assert await survivor.run_until_idle() == 2

        resumed, clean_run = await get_job(crashed, crash_job), await get_job(calm, calm_job)
        assert resumed["status"] == clean_run["status"] == "done"
        assert (
            counts(resumed)
            == counts(clean_run)
            == {
                "total": 41,
                "new": 40,
                "duplicate": 0,
                "conflict": 0,
                "invalid": 1,
            }
        )
        assert resumed["errors"] == clean_run["errors"]
        resumed_rows = [row[1:] for row in await raw_rows(db_engine, crashed)]
        assert resumed_rows == [row[1:] for row in await raw_rows(db_engine, calm)]


@NOT_IMPLEMENTED
async def test_stale_lock_requeued_after_5_min_by_clock(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    clock = MovableClock(T0)
    async with user_client(settings, "stale") as client:
        job_id = await upload(client, days_file(0))
        dying = make_worker(db_engine, clock, batch_size=10, crash_after_batch=1)
        claimed = await dying.claim()
        assert claimed is not None
        with pytest.raises(SimulatedCrash):
            await dying.process(claimed)

        other = make_worker(db_engine, clock, worker_id="other")
        clock.at = T0 + timedelta(minutes=4, seconds=59)
        await other.tick()
        assert await other.claim() is None, "locked less than 5 minutes ago: not stale yet"

        clock.at = T0 + timedelta(minutes=5, seconds=1)
        await other.tick()
        again = await other.claim()
        assert again is not None and again.payload["ingest_job_id"] == job_id
        assert again.job.attempts == 2
        await other.process(again)
        assert (await get_job(client, job_id))["status"] == "done"


@NOT_IMPLEMENTED
async def test_same_user_jobs_sequential_different_users_parallel(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with user_client(settings, "alice") as alice, user_client(settings, "bob") as bob:
        a1 = await upload(alice, days_file(0))
        a2 = await upload(alice, days_file(1))
        b1 = await upload(bob, days_file(0))
        w1, w2, w3 = (make_worker(db_engine, worker_id=f"w{i}") for i in (1, 2, 3))

        first = await w1.claim()
        assert first is not None and first.payload["ingest_job_id"] == a1
        # Alice is busy: her second job waits, Bob's job runs in parallel.
        second = await w2.claim()
        assert second is not None and second.payload["ingest_job_id"] == b1
        assert await w3.claim() is None

        await w1.process(first)
        third = await w3.claim()
        assert third is not None and third.payload["ingest_job_id"] == a2
        await asyncio.gather(w2.process(second), w3.process(third))

        assert [(await get_job(alice, j))["status"] for j in (a1, a2)] == ["done", "done"]
        assert (await get_job(bob, b1))["status"] == "done"


async def test_upload_over_limit_413(clean: None, settings: Settings) -> None:
    limited = settings.model_copy(update={"ingest_max_bytes": 1000})
    async with user_client(limited, "big") as client:
        response = await client.post(
            "/api/ingest/files", files={"file": ("big.ndjson", b"x" * 1001, "application/x-ndjson")}
        )
        assert response.status_code == 413, response.text
        listed = await client.get("/api/ingest/jobs")

    assert listed.json() == []
    assert not [p for p in limited.ingest_dir.rglob("*") if p.is_file()]


async def test_job_of_other_user_404(clean: None, settings: Settings) -> None:
    async with user_client(settings, "owner") as owner, user_client(settings, "other") as other:
        job_id = await upload(owner, days_file(0))

        assert (await other.get(f"/api/ingest/jobs/{job_id}")).status_code == 404
        assert (await other.get(f"/api/ingest/jobs/{uuid.uuid4()}")).status_code == 404
        assert (await other.get("/api/ingest/jobs")).json() == []
        assert [j["id"] for j in (await owner.get("/api/ingest/jobs")).json()] == [job_id]

        del owner.cookies["ht_session"]
        assert (await owner.get(f"/api/ingest/jobs/{job_id}")).status_code == 401


@NOT_IMPLEMENTED
async def test_errors_capped_at_50(clean: None, settings: Settings, db_engine: AsyncEngine) -> None:
    good = day_records(0)[:10]
    data = ndjson(META, *good) + b"".join(b"garbage %d\n" % i for i in range(120))
    async with user_client(settings, "errors") as client:
        job_id = await upload(client, data)
        await make_worker(db_engine, batch_size=25).run_until_idle()
        job = await get_job(client, job_id)

    assert counts(job)["invalid"] == 120
    assert counts(job)["new"] == 10
    assert len(job["errors"]) == 50
    # The first 50 bad lines across batches: lines 12..61 (meta is 1, good records 2..11).
    assert [e["line"] for e in job["errors"]] == list(range(12, 62))


@NOT_IMPLEMENTED
async def test_health_reports_worker_heartbeat(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with AsyncExitStack() as stack:
        app = create_app(settings)
        await stack.enter_async_context(app.router.lifespan_context(app))
        client = await stack.enter_async_context(
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        )

        never = (await client.get("/api/health")).json()
        assert never["worker"] == {"status": "unknown", "last_tick_at": None}

        long_ago = datetime.now(UTC) - timedelta(minutes=10)
        await make_worker(db_engine, MovableClock(long_ago), worker_id="old").tick()
        stale = await client.get("/api/health")
        assert stale.status_code == 200, "a stale worker does not make the api unhealthy"
        assert stale.json()["worker"]["status"] == "stale"

        await make_worker(db_engine, worker_id="fresh").tick()
        fresh = await client.get("/api/health")
        body = fresh.json()
        assert fresh.status_code == 200
        assert body["status"] == "ok" and body["db"] == "ok"
        assert body["worker"]["status"] == "ok"
        last_tick = datetime.fromisoformat(body["worker"]["last_tick_at"])
        assert abs(datetime.now(UTC) - last_tick) < timedelta(seconds=30)


@NOT_IMPLEMENTED
async def test_worker_wakes_on_notify_without_waiting_for_tick(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    """Beyond the plan: a new job is picked up at once (LISTEN), not on the next 30 s tick."""
    worker = make_worker(db_engine, tick_s=30)
    stop = asyncio.Event()
    loop_task = asyncio.create_task(worker.run(stop))
    listening = asyncio.create_task(worker.listening.wait())
    try:
        await asyncio.wait({loop_task, listening}, timeout=5, return_when="FIRST_COMPLETED")
        if loop_task.done():
            loop_task.result()  # re-raise the loop's error
        assert worker.listening.is_set(), "the worker did not start listening"

        async with user_client(settings, "notify") as client:
            job_id = await upload(client, days_file(0))

            async def done() -> bool:
                return (await get_job(client, job_id))["status"] == "done"

            assert await wait_until(done, timeout_s=5), "the job waited for the tick"
    finally:
        listening.cancel()
        stop.set()
        await asyncio.wait_for(loop_task, timeout=10)
