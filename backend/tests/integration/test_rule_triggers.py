"""When the rules are evaluated (SPEC F9): when an ingest job is done and every hour by the
worker's timer, so the anchors move with the local date even without new data.

These commit for real, like tests/integration/test_ingest_jobs.py: the worker uses its own
connections. Users get `@jobs.example.com` addresses and are deleted by the `clean` fixture.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.db import create_sessionmaker
from app.models import DailySummary
from app.worker.main import RULES_TICK_S
from app.worker.queue import USER_LOCK_NAMESPACE
from tests.integration.ingest import generate, make_user
from tests.integration.test_ingest_jobs import (
    MovableClock,
    get_job,
    make_worker,
    upload,
    user_client,
    wait_until,
    wipe,
)

D = date(2026, 10, 10)
MOSCOW = ZoneInfo("Europe/Moscow")  # htgen's zone and the zone the users register with


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


async def recommendations(engine: AsyncEngine, user_id: uuid.UUID | str) -> list[dict]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT rule_code, status, anchor_date, opened_at FROM recommendations"
                " WHERE user_id = :u ORDER BY opened_at, rule_code"
            ),
            {"u": user_id},
        )
        return [dict(row._mapping) for row in result]


async def user_with_short_nights(engine: AsyncEngine, *nights: date) -> uuid.UUID:
    """A committed user in UTC whose only data are valid 5 h nights on `nights` (wake days)."""
    async with create_sessionmaker(engine)() as session:
        user_id = await make_user(session, email=f"rules-{uuid.uuid4().hex[:8]}@jobs.example.com")
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
    return user_id


async def test_evaluated_after_ingest_done(
    clean: None,
    settings: Settings,
    db_engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    # The API stamps the job with the real time, so the worker's clock must not be behind it:
    # three short nights up to today in Moscow, evaluated at 09:00 tomorrow.
    last = datetime.now(MOSCOW).date()
    data = generate(
        tmp_path,
        *("--end", last.isoformat(), "--days", "4", "--seed", "7", "--hr-interval", "60"),
        *("--scenario", "short-sleep"),
    )
    morning = datetime.combine(last + timedelta(days=1), time(9, 0), MOSCOW).astimezone(UTC)
    worker = make_worker(db_engine, MovableClock(morning))

    async with user_client(settings, "rules") as client:
        user_id = (await client.get("/api/auth/me")).json()["id"]
        job_id = await upload(client, data)
        # Accepted, not processed: nothing is evaluated yet.
        assert await recommendations(db_engine, user_id) == []

        assert await worker.run_until_idle() == 1
        job = await get_job(client, job_id)

    assert job["status"] == "done"
    [opened] = await recommendations(db_engine, user_id)
    assert (opened["rule_code"], opened["status"]) == ("R1", "open")
    assert opened["anchor_date"] == last
    # Evaluated in the transaction that finished the job, at the same Clock moment.
    async with db_engine.connect() as conn:
        finished_at = await conn.scalar(
            text("SELECT finished_at FROM ingest_jobs WHERE id = :id"), {"id": job_id}
        )
    assert opened["opened_at"] == finished_at


@pytest.mark.xfail(strict=True, reason="step 8.2: not implemented")
async def test_hourly_tick_evaluates_on_day_change(
    clean: None,
    db_engine: AsyncEngine,
) -> None:
    user_id = await user_with_short_nights(
        db_engine, D - timedelta(days=2), D - timedelta(days=1), D
    )
    # On D−1 the last three nights are D−3 … D−1, and D−3 has no data: unknown.
    clock = MovableClock(datetime(2026, 10, 9, 12, 0, tzinfo=UTC))
    worker = make_worker(db_engine, clock, rules_tick_s=0.2)

    await worker.rules_tick()
    assert await recommendations(db_engine, user_id) == []

    # Past midnight: today is D, the nights D−2 … D are all short. No upload, only the timer.
    clock.at = datetime(2026, 10, 10, 0, 30, tzinfo=UTC)
    stop = asyncio.Event()
    loop_task = asyncio.create_task(worker.run(stop))
    try:

        async def opened() -> bool:
            if loop_task.done():
                loop_task.result()  # re-raise the loop's error
            return bool(await recommendations(db_engine, user_id))

        assert await wait_until(opened, timeout_s=5), "the timer did not evaluate the rules"
    finally:
        stop.set()
        await asyncio.wait_for(loop_task, timeout=10)

    [rec] = await recommendations(db_engine, user_id)
    assert (rec["rule_code"], rec["status"], rec["anchor_date"]) == ("R1", "open", D)
    assert rec["opened_at"] == clock.at
    # The timer runs every hour by default.
    assert make_worker(db_engine).rules_tick_s == RULES_TICK_S == 3600


@pytest.mark.xfail(strict=True, reason="step 8.2: not implemented")
async def test_hourly_tick_skips_user_with_running_job(
    clean: None,
    db_engine: AsyncEngine,
) -> None:
    """Beyond the plan: a user whose job is running is left to that job, which evaluates the
    rules when it is done; the timer does not wait for it either."""
    user_id = await user_with_short_nights(
        db_engine, D - timedelta(days=2), D - timedelta(days=1), D
    )
    worker = make_worker(db_engine, MovableClock(datetime(2026, 10, 10, 12, 0, tzinfo=UTC)))

    async with db_engine.connect() as job_conn:
        # The lock a claimed job of the user holds (app.worker.queue.claim).
        lock = func.pg_advisory_lock(USER_LOCK_NAMESPACE, func.hashtext(str(user_id)))
        await job_conn.execute(select(lock))
        await asyncio.wait_for(worker.rules_tick(), timeout=5)
        assert await recommendations(db_engine, user_id) == []
        await job_conn.execute(select(func.pg_advisory_unlock_all()))
        await job_conn.commit()

    await worker.rules_tick()
    assert [r["rule_code"] for r in await recommendations(db_engine, user_id)] == ["R1"]
