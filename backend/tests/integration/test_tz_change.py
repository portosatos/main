"""A change of the time zone history (SPEC F5, F9, F11, §9 #18; plan step 10.1): the job
`tz_changed` recomputes the dates the move touches and evaluates the rules again.

These commit for real, like test_ingest_jobs.py: the api queues the job, the worker runs it on
its own connections. Users get `@jobs.example.com` addresses and are deleted by the `clean`
fixture. The data are uploaded through the api and processed by the worker, as in the app.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.db import create_sessionmaker
from app.services.summaries import rebuild_summaries
from tests.integration.ingest import ndjson
from tests.integration.test_goals import api_user, listen, of_type
from tests.integration.test_ingest_jobs import (
    MovableClock,
    days_file,
    iso,
    make_worker,
    upload,
    wipe,
)
from tests.integration.test_summaries import SUMMARY_COLUMNS

# The data of days_file(0, …, 6): Oct 1 00:00Z – Oct 7 23:25Z, both devices every hour.
DATA_DAYS = range(7)
# The users register after the data; the worker processes the upload at BEFORE.
REGISTERED = datetime(2026, 10, 9, 5, 0, tzinfo=UTC)
BEFORE = datetime(2026, 10, 9, 6, 0, tzinfo=UTC)
AFTER = datetime(2026, 10, 9, 7, 0, tzinfo=UTC)


pytestmark = pytest.mark.xfail(strict=True, reason="step 10.1: not implemented")


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


async def summaries(engine: AsyncEngine, user_id: uuid.UUID) -> dict[date, dict[str, Any]]:
    """{local_date: row} of the user's daily_summaries."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT * FROM daily_summaries WHERE user_id = :u ORDER BY local_date"),
            {"u": user_id},
        )
        return {row["local_date"]: dict(row) for row in result.mappings()}


def metrics(found: dict[date, dict[str, Any]]) -> dict[date, tuple]:
    """The metrics of every row, computed_at left out."""
    return {day: tuple(row[c] for c in SUMMARY_COLUMNS) for day, row in found.items()}


async def move(client: httpx.AsyncClient, tz: str, valid_from: str) -> None:
    response = await client.post(
        "/api/settings/timezones", json={"tz": tz, "valid_from": valid_from}
    )
    assert response.status_code == 201, response.text


async def uploaded(
    client: httpx.AsyncClient, engine: AsyncEngine, data: bytes, at: datetime
) -> None:
    """The file uploaded and processed by a worker whose Clock reads `at`."""
    await upload(client, data)
    assert await make_worker(engine, MovableClock(at)).run_until_idle() == 1


async def test_past_tz_change_recomputes_affected_dates(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with api_user(settings, "tz-dates", at=REGISTERED) as (client, clock, user_id):
        await uploaded(client, db_engine, days_file(*DATA_DAYS), BEFORE)
        before = await summaries(db_engine, user_id)
        # Moscow: Oct 1 … Oct 7, and Oct 8 from 21:00Z of Oct 7 on.
        assert set(before) == {date(2026, 10, d) for d in range(1, 9)}

        # Moved to New York on Oct 5 at 08:00 local time (12:00Z). The instants from then on
        # change their dates: Moscow Oct 5 … Oct 8 before, New York Oct 5 … Oct 7 now.
        clock.at = AFTER
        async with listen(settings.database_url, user_id) as events:
            await move(client, "America/New_York", "2026-10-05T12:00:00Z")
            assert await make_worker(db_engine, MovableClock(AFTER)).run_until_idle() == 1
            found = await events.until("summary.updated")
        assert of_type(found, "summary.updated") == [
            {"dates": ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"]}
        ]

        after = await summaries(db_engine, user_id)
        assert set(after) == {date(2026, 10, d) for d in range(1, 8)}
        for day, row in after.items():
            recomputed = day >= date(2026, 10, 5)
            assert row["computed_at"] == (AFTER if recomputed else BEFORE), day
            if not recomputed:  # the days before the move are left as they were
                assert row == before[day]

        # The result equals a rebuild from scratch by the new history.
        async with create_sessionmaker(db_engine)() as session:
            await rebuild_summaries(session, user_id, AFTER + timedelta(hours=1))
            await session.commit()
        assert metrics(await summaries(db_engine, user_id)) == metrics(after)


async def test_tz_change_preserves_period_totals(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    # SPEC F5, §9 #18: Moscow → New York on Oct 3 at 12:00Z (Oct 3 lasts 31 hours), back to
    # Moscow on Oct 6 at 00:00Z. The steps and the wear time of the period stay the same: nothing
    # is lost or counted twice.
    async with api_user(settings, "tz-totals", at=REGISTERED) as (client, clock, user_id):
        await uploaded(client, db_engine, days_file(*DATA_DAYS), BEFORE)
        before = await summaries(db_engine, user_id)

        clock.at = AFTER
        await move(client, "America/New_York", "2026-10-03T12:00:00Z")
        await move(client, "Europe/Moscow", "2026-10-06T00:00:00Z")
        assert await make_worker(db_engine, MovableClock(AFTER)).run_until_idle() == 2

        after = await summaries(db_engine, user_id)
        for column in ("steps", "wear_minutes"):
            assert sum(r[column] for r in after.values()) == sum(r[column] for r in before.values())
        assert after[date(2026, 10, 3)]["wear_minutes"] > after[date(2026, 10, 2)]["wear_minutes"]
        assert after[date(2026, 10, 3)]["steps"] > before[date(2026, 10, 3)]["steps"]


def flat_hours(start: datetime, hours: int, count: int) -> bytes:
    """A watch walking `count` steps evenly through every hour from `start`: never an active
    minute (100 steps a minute and more)."""
    meta = {
        "type": "meta",
        "schema": "ht.v1",
        "devices": [{"id": "watch-1", "kind": "watch", "name": "Часы"}],
    }
    records = [
        {
            "type": "steps",
            "device": "watch-1",
            "start": iso(start + timedelta(hours=h)),
            "end": iso(start + timedelta(hours=h + 1)),
            "count": count,
        }
        for h in range(hours)
    ]
    return ndjson(meta, *records)


async def test_tz_change_reevaluates_rules(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    # R6 (5 complete days in a row under 15 active minutes, anchor yesterday) on data of
    # Oct 1 00:00Z – Oct 6 00:00Z, 7200 steps a day without an active minute; now is Oct 6 05:00Z.
    # In Auckland (UTC+13) Oct 1 starts at 13:00 local time: 660 minutes, a partial day, so the
    # window Oct 1–5 is unknown. In UTC every day of it is complete: R6 opens with the anchor Oct 5.
    # R2 holds in both (7200 steps ≥ 50 % of 8000).
    now = datetime(2026, 10, 6, 5, 0, tzinfo=UTC)
    async with api_user(settings, "tz-rules", at=now) as (client, _clock, user_id):
        async with db_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE user_timezones SET tz = 'Pacific/Auckland', valid_from = :at"
                    " WHERE user_id = :u"
                ),
                {"u": user_id, "at": datetime(2026, 9, 1, tzinfo=UTC)},
            )
        await uploaded(
            client, db_engine, flat_hours(datetime(2026, 10, 1, tzinfo=UTC), 120, 300), now
        )
        assert (await summaries(db_engine, user_id))[date(2026, 10, 1)]["status"] == "partial"
        assert await open_recommendations(db_engine, user_id) == []

        await move(client, "UTC", "2026-09-15T00:00:00Z")
        assert await make_worker(db_engine, MovableClock(now)).run_until_idle() == 1

        assert await open_recommendations(db_engine, user_id) == [("R6", date(2026, 10, 5))]
        found = await summaries(db_engine, user_id)
        assert [found[date(2026, 10, d)]["status"] for d in range(1, 6)] == ["complete"] * 5


async def open_recommendations(engine: AsyncEngine, user_id: uuid.UUID) -> list[tuple]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT rule_code, anchor_date FROM recommendations"
                " WHERE user_id = :u AND status = 'open' ORDER BY rule_code"
            ),
            {"u": user_id},
        )
        return [tuple(row) for row in result.all()]
