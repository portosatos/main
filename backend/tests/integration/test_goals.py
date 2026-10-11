"""Goals, achievements and notifications (SPEC F8, F12, §6.3; plan step 7.1).

Like test_ingest_jobs.py these commit for real: the worker publishes from its own connections,
so the events are heard by a LISTEN connection of the test (`Listener`), as the api's EventHub
hears them. Users get `@jobs.example.com` addresses and are deleted by the `clean` fixture.

The users live in Moscow (UTC+3): the steps of UTC day 0 (Oct 1) fall on Moscow Oct 1 for
00:00–20:59 UTC and on Moscow Oct 2 for 21:00–23:59 UTC.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.main import create_app
from tests.integration.client import CSRF_HEADERS
from tests.integration.ingest import ndjson
from tests.integration.test_ingest_jobs import (
    PASSWORD,
    MovableClock,
    get_job,
    iso,
    make_worker,
    upload,
    wipe,
)

T0 = datetime(2026, 10, 1, tzinfo=UTC)
META = {
    "type": "meta",
    "schema": "ht.v1",
    "devices": [{"id": "watch-1", "kind": "watch", "name": "Часы"}],
}
WAIT_S = 5.0


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
async def api_user(
    settings: Settings, name: str, at: datetime = T0
) -> AsyncIterator[tuple[httpx.AsyncClient, MovableClock, uuid.UUID]]:
    """A client of a fresh app whose Clock the test moves, with a user registered at `at` in
    Europe/Moscow and logged in."""
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        clock = MovableClock(at)
        app.state.clock = clock
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
            yield client, clock, uuid.UUID(registered.json()["id"])


class Listener:
    """The committed `user_events` of one user, in the order they arrive."""

    def __init__(self, user_id: uuid.UUID) -> None:
        self.user_id = str(user_id)
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def on_notify(self, _conn: Any, _pid: int, _channel: str, payload: str) -> None:
        event = json.loads(payload)
        if event["user_id"] == self.user_id:
            self.queue.put_nowait(event)

    async def until(self, type: str, timeout_s: float = WAIT_S) -> list[dict[str, Any]]:
        """Events up to and including the first one of `type`; fails if it does not come."""
        found: list[dict[str, Any]] = []
        try:
            async with asyncio.timeout(timeout_s):
                while not found or found[-1]["type"] != type:
                    found.append(await self.queue.get())
        except TimeoutError:
            pytest.fail(f"no {type} within {timeout_s} s; got {[e['type'] for e in found]}")
        return found

    async def quiet(self, seconds: float = 0.5) -> list[dict[str, Any]]:
        """Whatever arrives within `seconds`."""
        found: list[dict[str, Any]] = []
        loop = asyncio.get_running_loop()
        deadline = loop.time() + seconds
        while (left := deadline - loop.time()) > 0:
            try:
                found.append(await asyncio.wait_for(self.queue.get(), left))
            except TimeoutError:
                break
        return found


@asynccontextmanager
async def listen(database_url: str, user_id: uuid.UUID) -> AsyncIterator[Listener]:
    url = make_url(database_url)
    conn = await asyncpg.connect(
        user=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        database=url.database,
        timeout=5,
    )
    listener = Listener(user_id)
    await conn.add_listener("user_events", listener.on_notify)
    try:
        yield listener
    finally:
        await conn.close()


def of_type(events: list[dict[str, Any]], type: str) -> list[dict[str, Any]]:
    return [e["data"] for e in events if e["type"] == type]


def steps(start: datetime, count: int, minutes: int = 10) -> dict[str, Any]:
    return {
        "type": "steps",
        "device": "watch-1",
        "start": iso(start),
        "end": iso(start + timedelta(minutes=minutes)),
        "count": count,
    }


def day_steps(day: int) -> list[dict[str, Any]]:
    """24 hourly step intervals on UTC day `day` after T0, 400 + hour steps each. Day 0 gives
    Moscow Oct 1 hours 0–20 UTC: 8610 steps (8190 after the first 20), Oct 2 hours 21–23: 1266."""
    return [steps(T0 + timedelta(days=day, hours=hour), 400 + hour) for hour in range(24)]


def steps_file(*days: int, extra: list[dict[str, Any]] | None = None) -> bytes:
    return ndjson(META, *(r for day in days for r in day_steps(day)), *(extra or []))


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


async def store_summary(
    engine: AsyncEngine,
    user_id: uuid.UUID,
    day: str,
    *,
    steps: int | None = None,
    sleep_minutes: int | None = None,
) -> None:
    """A complete day written straight into daily_summaries (no raw records behind it)."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO daily_summaries (user_id, local_date, status, wear_minutes, steps, "
                "active_minutes, sleep_minutes, night_valid, computed_at) "
                "VALUES (:u, :d, 'complete', 1440, :steps, 60, :sleep, "
                ":valid, :at)"
            ),
            {
                "u": user_id,
                "d": date.fromisoformat(day),
                "steps": steps,
                "sleep": sleep_minutes,
                "valid": sleep_minutes is not None,
                "at": T0,
            },
        )


async def notifications(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get("/api/notifications")
    assert response.status_code == 200, response.text
    return response.json()


async def day_goals(client: httpx.AsyncClient, day: str) -> dict[str, Any]:
    response = await client.get(f"/api/summary/day?date={day}")
    assert response.status_code == 200, response.text
    return response.json()["day"]["goals"]


async def test_default_goals_8000_steps_8h_sleep(clean: None, settings: Settings) -> None:
    async with api_user(settings, "goals-default") as (client, _clock, _user_id):
        response = await client.get("/api/goals")
        assert response.status_code == 200, response.text
        assert response.json() == [
            {"kind": "steps", "target": 8000, "valid_from": None},
            {"kind": "sleep", "target": 8, "valid_from": None},
        ]
        # A date without data: the target, no progress, not achieved.
        assert await day_goals(client, "2026-10-01") == {
            "steps": {"target": 8000, "percent": None, "achieved": False},
            "sleep": {"target": 8, "percent": None, "achieved": False},
        }


async def test_put_creates_new_version_past_days_use_old_target(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with api_user(settings, "goals-history") as (client, clock, user_id):
        await store_summary(db_engine, user_id, "2026-10-01", steps=4000, sleep_minutes=360)
        await store_summary(db_engine, user_id, "2026-10-05", steps=6000, sleep_minutes=360)
        async with listen(settings.database_url, user_id) as events:
            clock.at = datetime(2026, 10, 4, 21, tzinfo=UTC)  # Moscow Oct 5, 00:00
            response = await client.put("/api/goals", json={"steps": 12000, "sleep": 9})
            assert response.status_code == 200, response.text
            assert response.json() == [
                {"kind": "steps", "target": 12000, "valid_from": "2026-10-04T21:00:00Z"},
                {"kind": "sleep", "target": 9, "valid_from": "2026-10-04T21:00:00Z"},
            ]
            changed = of_type(await events.until("goal.changed"), "goal.changed")
            assert changed == [{"kinds": ["steps", "sleep"]}]

            # The same targets again: no new version, no event.
            clock.at += timedelta(hours=1)
            again = await client.put("/api/goals", json={"steps": 12000, "sleep": 9})
            assert again.status_code == 200, again.text
            assert again.json() == response.json()
            assert of_type(await events.quiet(), "goal.changed") == []

        current = await client.get("/api/goals")
        assert current.json() == response.json()
        # Oct 1 keeps the default goals, Oct 5 (the day of the change) has the new ones.
        assert await day_goals(client, "2026-10-01") == {
            "steps": {"target": 8000, "percent": 50, "achieved": False},
            "sleep": {"target": 8, "percent": 75, "achieved": False},
        }
        assert await day_goals(client, "2026-10-05") == {
            "steps": {"target": 12000, "percent": 50, "achieved": False},
            "sleep": {"target": 9, "percent": 66, "achieved": False},
        }


async def test_achievement_created_once_when_data_crosses_threshold_mid_ingest(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    # Day 0 in batches of 7 lines (line 1 is meta): after batch 3 the first 20 hours are in,
    # Moscow Oct 1 has 8190 steps and the goal of 8000 is met while the job still runs.
    hook, paused, resume = pause_after(3)
    async with api_user(settings, "goals-mid") as (client, _clock, user_id):
        async with listen(settings.database_url, user_id) as events:
            job_id = await upload(client, steps_file(0))
            clock = MovableClock(T0 + timedelta(days=1))  # Moscow Oct 2, 03:00
            worker = make_worker(db_engine, clock, batch_size=7, on_batch=hook, summary_flush_s=0)
            run = asyncio.create_task(worker.run_until_idle())
            try:
                await asyncio.wait_for(paused.wait(), timeout=30)
                before = await events.until("goal.achieved")
                assert of_type(before, "ingest.done") == []
                assert (await get_job(client, job_id))["status"] == "processing"
                assert of_type(before, "goal.achieved") == [
                    {
                        "kind": "steps",
                        "local_date": "2026-10-01",
                        "target": 8000,
                        "value": 8190,
                        "show_toast": True,  # yesterday
                        "notification_id": of_type(before, "goal.achieved")[0]["notification_id"],
                    }
                ]
                feed = await notifications(client)
                assert feed["unread"] == 1
                assert [n["payload"]["local_date"] for n in feed["items"]] == ["2026-10-01"]
                created = of_type(before, "notification.created")
                assert created == [{"id": feed["items"][0]["id"], "type": "goal.achieved"}]
            finally:
                resume.set()
                await run
            after = await events.until("ingest.done")

    # The rest of the file adds steps to Oct 1 again: no second achievement.
    assert of_type(after, "goal.achieved") == []
    assert of_type(after, "notification.created") == []


async def test_reupload_does_not_create_second_achievement(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with api_user(settings, "goals-reupload") as (client, _clock, user_id):
        clock = MovableClock(T0 + timedelta(days=1))
        async with listen(settings.database_url, user_id) as events:
            await upload(client, steps_file(0))
            await make_worker(db_engine, clock, summary_flush_s=0).run_until_idle()
            first = await events.until("ingest.done")
            assert [a["local_date"] for a in of_type(first, "goal.achieved")] == ["2026-10-01"]

            await upload(client, steps_file(0))
            await make_worker(db_engine, clock, summary_flush_s=0).run_until_idle()
            second = await events.until("ingest.done")
            assert of_type(second, "summary.updated") == []  # all duplicates
            assert of_type(second, "goal.achieved") == []
            assert of_type(second, "notification.created") == []

        feed = await notifications(client)
        assert len(feed["items"]) == 1
        assert feed["unread"] == 1


async def test_toast_flag_only_for_today_and_yesterday_by_clock(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    # Days 0–2 meet the goal on Moscow Oct 1, 2 and 3; 9000 more steps at 02:30 Moscow time
    # meet it on Oct 4 too. The worker's clock: Moscow Oct 4, 03:00 — today is Oct 4.
    extra = [steps(datetime(2026, 10, 3, 23, 30, tzinfo=UTC), 9000)]
    async with api_user(settings, "goals-toast") as (client, _clock, user_id):
        async with listen(settings.database_url, user_id) as events:
            await upload(client, steps_file(0, 1, 2, extra=extra))
            clock = MovableClock(T0 + timedelta(days=3))
            await make_worker(db_engine, clock, summary_flush_s=0).run_until_idle()
            found = await events.until("ingest.done")
        feed = await notifications(client)

    toasts = {a["local_date"]: a["show_toast"] for a in of_type(found, "goal.achieved")}
    assert toasts == {
        "2026-10-01": False,
        "2026-10-02": False,
        "2026-10-03": True,
        "2026-10-04": True,
    }
    # Every achievement is in the feed, the old ones without a toast too.
    assert sorted(n["payload"]["local_date"] for n in feed["items"]) == sorted(toasts)


async def test_sleep_goal_counted_on_wake_day(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    # 9.5 h of sleep from Moscow Oct 1, 22:00 to Oct 2, 07:30: the goal is met on Oct 2.
    sleep = {
        "type": "sleep",
        "device": "watch-1",
        "start": "2026-10-01T19:00:00Z",
        "end": "2026-10-02T04:30:00Z",
    }
    async with api_user(settings, "goals-sleep") as (client, _clock, user_id):
        async with listen(settings.database_url, user_id) as events:
            await upload(client, ndjson(META, sleep))
            clock = MovableClock(T0 + timedelta(days=5))
            await make_worker(db_engine, clock, summary_flush_s=0).run_until_idle()
            found = await events.until("ingest.done")
        wake_day = await day_goals(client, "2026-10-02")
        bed_day = await day_goals(client, "2026-10-01")

    achieved = of_type(found, "goal.achieved")
    assert [(a["kind"], a["local_date"], a["value"]) for a in achieved] == [
        ("sleep", "2026-10-02", 9.5)
    ]
    assert achieved[0]["show_toast"] is False  # Oct 2 is long ago by the clock
    assert wake_day["sleep"] == {"target": 8, "percent": 118, "achieved": True}
    assert bed_day["sleep"] == {"target": 8, "percent": None, "achieved": False}


async def test_week_progress_n_of_7(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    # W41 = Oct 5–11. The steps goal goes up to 12000 from Moscow Oct 7.
    async with api_user(settings, "goals-week") as (client, clock, user_id):
        for day, step_count, sleep in [
            ("2026-10-05", 9000, 480),
            ("2026-10-06", 1000, 420),
            ("2026-10-07", 12000, None),
            ("2026-10-08", 8000, 500),
        ]:
            await store_summary(db_engine, user_id, day, steps=step_count, sleep_minutes=sleep)
        clock.at = datetime(2026, 10, 6, 21, tzinfo=UTC)
        update = await client.put("/api/goals", json={"steps": 12000, "sleep": 8})
        assert update.status_code == 200, update.text

        response = await client.get("/api/summary/week?week=2026-W41")
        assert response.status_code == 200, response.text
        week = response.json()

    assert week["goals"] == {
        "steps": {"achieved_days": 2, "of": 7},  # Oct 5 (9000 ≥ 8000), Oct 7 (12000 ≥ 12000)
        "sleep": {"achieved_days": 2, "of": 7},  # Oct 5 and Oct 8
    }
    assert week["previous"]["goals"] == {
        "steps": {"achieved_days": 0, "of": 7},
        "sleep": {"achieved_days": 0, "of": 7},
    }
    assert [d["goals"]["steps"]["target"] for d in week["days"]] == [8000, 8000] + [12000] * 5


async def test_notifications_list_mark_read_and_isolation(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with (
        api_user(settings, "goals-alice") as (alice, _clock, alice_id),
        api_user(settings, "goals-bob") as (bob, _bob_clock, _bob_id),
    ):
        async with listen(settings.database_url, alice_id) as events:
            await upload(alice, steps_file(0))
            clock = MovableClock(T0 + timedelta(days=1))
            await make_worker(db_engine, clock, summary_flush_s=0).run_until_idle()
            await events.until("ingest.done")

            feed = await notifications(alice)
            assert feed["unread"] == 1
            [item] = feed["items"]
            assert item["type"] == "goal.achieved"
            assert item["payload"] == {
                "kind": "steps",
                "local_date": "2026-10-01",
                "target": 8000,
                "value": 8610,
            }
            assert item["read_at"] is None

            # Bob sees nothing of Alice's and cannot mark her notification read.
            assert await notifications(bob) == {"items": [], "unread": 0}
            foreign = await bob.post("/api/notifications/read", json={"ids": [item["id"]]})
            assert foreign.status_code == 200, foreign.text
            assert foreign.json() == {"unread": 0}
            assert (await notifications(alice))["unread"] == 1

            marked = await alice.post("/api/notifications/read", json={"ids": [item["id"]]})
            assert marked.status_code == 200, marked.text
            assert marked.json() == {"unread": 0}
            read = of_type(await events.until("notifications.read"), "notifications.read")
            assert read == [{"ids": [item["id"]]}]

        after = await notifications(alice)
        assert after["unread"] == 0
        assert after["items"][0]["read_at"] is not None


# Beyond the plan's list (Допущение of this step, ADR-043): a goal lowered below today's value
# is met at once, and the targets are validated.


async def test_lowering_goal_below_today_value_creates_achievement(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    # Day 0: Moscow Oct 2 (today by the clock) has 1266 steps, under 8000.
    async with api_user(settings, "goals-lower") as (client, clock, user_id):
        await upload(client, steps_file(0))
        worker_clock = MovableClock(T0 + timedelta(days=1))
        await make_worker(db_engine, worker_clock, summary_flush_s=0).run_until_idle()
        async with listen(settings.database_url, user_id) as events:
            clock.at = T0 + timedelta(days=1)
            response = await client.put("/api/goals", json={"steps": 1000, "sleep": 8})
            assert response.status_code == 200, response.text
            found = await events.until("goal.achieved")
        assert of_type(found, "goal.achieved")[0] | {"notification_id": None} == {
            "kind": "steps",
            "local_date": "2026-10-02",
            "target": 1000,
            "value": 1266,
            "show_toast": True,
            "notification_id": None,
        }
        assert len((await notifications(client))["items"]) == 2  # Oct 1 and Oct 2


async def test_put_rejects_invalid_targets(clean: None, settings: Settings) -> None:
    async with api_user(settings, "goals-invalid") as (client, _clock, _user_id):
        for body in [
            {"steps": 99, "sleep": 8},
            {"steps": 100_001, "sleep": 8},
            {"steps": 8000.5, "sleep": 8},
            {"steps": 8000, "sleep": 0.5},
            {"steps": 8000, "sleep": 16.5},
            {"steps": 8000},
        ]:
            response = await client.put("/api/goals", json=body)
            assert response.status_code == 422, (body, response.text)
        ok = await client.put("/api/goals", json={"steps": 100, "sleep": 7.5})
        assert ok.status_code == 200, ok.text
        assert [g["target"] for g in ok.json()] == [100, 7.5]
