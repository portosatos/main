"""Events and SSE (SPEC F3, F12; plan step 5.1): services/events.py and GET /api/events.

The api runs in a real uvicorn server on a free port: httpx's ASGI transport hands out a response
only when it is complete, an SSE stream never is. Events are published as the worker does, from
another connection and committed for real, so these tests use committed `@jobs.example.com`
users like test_ingest_jobs.py.
"""

import asyncio
import itertools
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest
import uvicorn
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.config import Settings
from app.main import create_app
from app.services import events
from tests.integration.client import CSRF_HEADERS
from tests.integration.test_ingest_jobs import PASSWORD, days_file, make_worker, upload, wipe

# SPEC F12: a change in one tab shows in the other within 2 seconds.
DELIVERY_S = 2.0
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
    )


@pytest.fixture
async def server(settings: Settings) -> AsyncIterator[str]:
    """Base URL of the api served by uvicorn on 127.0.0.1 and a free port."""
    config = uvicorn.Config(
        create_app(settings),
        host="127.0.0.1",
        port=0,
        log_level="warning",
        timeout_graceful_shutdown=2,
    )
    served = uvicorn.Server(config)
    task = asyncio.create_task(served.serve())
    while not served.started:
        if task.done():
            task.result()  # startup failed: raise its error
        await asyncio.sleep(0.02)
    port = served.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        served.should_exit = True
        await task


@asynccontextmanager
async def http(
    base_url: str, cookies: httpx.Cookies | None = None
) -> AsyncIterator[httpx.AsyncClient]:
    # No read timeout: an SSE stream is quiet between events.
    async with httpx.AsyncClient(
        base_url=base_url,
        headers=CSRF_HEADERS,
        cookies=cookies,
        timeout=httpx.Timeout(WAIT_S, read=None),
    ) as client:
        yield client


async def register(client: httpx.AsyncClient, name: str) -> uuid.UUID:
    """Register a new user on `client` (logged in by the cookie); their id."""
    body = {
        "email": f"{name}-{uuid.uuid4().hex[:8]}@jobs.example.com",
        "password": PASSWORD,
        "timezone": "Europe/Moscow",
    }
    response = await client.post("/api/auth/register", json=body)
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


@dataclass(frozen=True)
class Event:
    type: str
    data: Any
    at: float  # loop time of arrival


class SseStream:
    """GET /api/events read in the background. Entering waits for the `ready` event: from then
    on the stream is subscribed and gets every event of its user."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client
        self.received: asyncio.Queue[Event] = asyncio.Queue()

    async def __aenter__(self) -> "SseStream":
        loop = asyncio.get_running_loop()
        self._opened: asyncio.Future[int] = loop.create_future()
        self._task = asyncio.create_task(self._read())
        status = await asyncio.wait_for(self._opened, WAIT_S)
        assert status == 200
        ready = await self.next()
        assert ready.type == "ready"
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task

    async def _read(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            async with self.client.stream("GET", "/api/events") as response:
                self._opened.set_result(response.status_code)
                if response.status_code != 200:
                    return
                kind, data = "message", []
                async for line in response.aiter_lines():
                    if line == "":
                        if data:
                            event = Event(kind, json.loads("\n".join(data)), loop.time())
                            self.received.put_nowait(event)
                        kind, data = "message", []
                    elif not line.startswith(":"):  # ":" starts a keep-alive comment
                        field, _, value = line.partition(":")
                        value = value.removeprefix(" ")
                        if field == "event":
                            kind = value
                        elif field == "data":
                            data.append(value)
        except Exception as exc:
            if not self._opened.done():
                self._opened.set_exception(exc)
            raise

    async def next(self, within: float = WAIT_S) -> Event:
        return await asyncio.wait_for(self.received.get(), within)

    async def next_of(self, kind: str, within: float = WAIT_S) -> Event:
        """The next event of type `kind`; the others before it are skipped."""
        deadline = asyncio.get_running_loop().time() + within
        while True:
            event = await self.next(max(deadline - asyncio.get_running_loop().time(), 0))
            if event.type == kind:
                return event

    async def until(self, kind: str, within: float = 30.0) -> list[Event]:
        """Every event up to and including the first of type `kind`."""
        found: list[Event] = []
        async with asyncio.timeout(within):
            while not found or found[-1].type != kind:
                found.append(await self.received.get())
        return found


async def publish(
    engine: AsyncEngine,
    user_id: uuid.UUID,
    kind: str,
    data: dict[str, Any],
) -> float:
    """Publish from a connection of its own, as the worker does; the loop time of the commit."""
    async with AsyncSession(engine) as session:
        await events.publish(session, user_id, kind, data)
        at = asyncio.get_running_loop().time()
        await session.commit()
    return at


def slow_batches(delay_s: float) -> Callable[[int], Awaitable[None]]:
    async def hook(number: int) -> None:
        await asyncio.sleep(delay_s)

    return hook


@pytest.mark.xfail(strict=True, reason="step 5.1: not implemented")
async def test_two_sse_clients_same_user_both_receive_within_2s(
    clean: None, server: str, db_engine: AsyncEngine
) -> None:
    # Two tabs of one browser: one cookie, two streams.
    async with http(server) as first:
        user_id = await register(first, "tabs")
        async with http(server, first.cookies) as second:
            async with SseStream(first) as tab1, SseStream(second) as tab2:
                sent = await publish(db_engine, user_id, "ingest.progress", {"job_id": "x"})
                got = [await tab1.next(), await tab2.next()]
    for event in got:
        assert (event.type, event.data) == ("ingest.progress", {"job_id": "x"})
        assert event.at - sent <= DELIVERY_S


@pytest.mark.xfail(strict=True, reason="step 5.1: not implemented")
async def test_other_user_does_not_receive_events(
    clean: None, server: str, db_engine: AsyncEngine
) -> None:
    async with http(server) as alice, http(server) as bob:
        alice_id = await register(alice, "alice")
        bob_id = await register(bob, "bob")
        async with SseStream(alice) as alice_tab, SseStream(bob) as bob_tab:
            # Alice's events: one published directly and the ones of a real ingest job.
            await publish(db_engine, alice_id, "goal.changed", {"goal_id": 1})
            await upload(alice, days_file(0))
            assert await make_worker(db_engine, batch_size=10, summary_flush_s=0).run_until_idle()
            types = [e.type for e in await alice_tab.until("ingest.done")]
            assert {"goal.changed", "ingest.progress", "summary.updated"} <= set(types)

            # Events reach a stream in order: Bob's first event must be his own marker.
            await publish(db_engine, bob_id, "goal.changed", {"goal_id": 2})
            event = await bob_tab.next()
            assert (event.type, event.data) == ("goal.changed", {"goal_id": 2})


@pytest.mark.xfail(strict=True, reason="step 5.1: not implemented")
async def test_ingest_emits_progress_at_least_every_2s_and_done(
    clean: None, server: str, db_engine: AsyncEngine
) -> None:
    # 145 lines in 15 batches of 10, each batch held for 0.25 s: about 4 s of processing.
    data = days_file(0, 1)
    async with http(server) as client:
        await register(client, "progress")
        async with SseStream(client) as tab:
            job_id = await upload(client, data)
            started = asyncio.get_running_loop().time()
            worker = make_worker(db_engine, batch_size=10, on_batch=slow_batches(0.25))
            run = asyncio.create_task(worker.run_until_idle())
            found = await tab.until("ingest.done")
            await run
    mine = [e for e in found if e.type.startswith("ingest.") and e.data["job_id"] == job_id]
    progress = [e for e in mine if e.type == "ingest.progress"]
    done = mine[-1]
    assert done.type == "ingest.done"
    assert len(progress) >= 3

    times = [started] + [e.at for e in progress] + [done.at]
    assert max(b - a for a, b in itertools.pairwise(times)) <= DELIVERY_S
    done_bytes = [e.data["bytes_done"] for e in progress]
    assert done_bytes == sorted(done_bytes)
    assert all(e.data["bytes_total"] == len(data) for e in progress)
    assert done.data["status"] == "done"
    assert done.data["counts"] == {"new": 144, "duplicate": 0, "conflict": 0, "invalid": 0}


@pytest.mark.xfail(strict=True, reason="step 5.1: not implemented")
async def test_summary_updated_contains_dates(
    clean: None, server: str, db_engine: AsyncEngine
) -> None:
    # Days 0 and 1 of test_ingest_jobs: Oct 1 and 2 UTC, Moscow dates Oct 1–3. A flush after
    # every batch: the dates come in several events, all before ingest.done.
    async with http(server) as client:
        await register(client, "summary")
        async with SseStream(client) as tab:
            await upload(client, days_file(0, 1))
            worker = make_worker(db_engine, batch_size=10, summary_flush_s=0)
            assert await worker.run_until_idle() == 1
            found = await tab.until("ingest.done")
    updates = [e.data["dates"] for e in found if e.type == "summary.updated"]
    assert len(updates) >= 2
    assert all(dates == sorted(dates) and dates for dates in updates)
    assert {d for dates in updates for d in dates} == {"2026-10-01", "2026-10-02", "2026-10-03"}


@pytest.mark.xfail(strict=True, reason="step 5.1: not implemented")
async def test_large_date_set_split_into_payloads_under_8kb(
    clean: None, server: str, db_engine: AsyncEngine, migrated_database_url: str
) -> None:
    # 1500 dates are about 20 KB of JSON: more than one NOTIFY can carry.
    dates = [date(2022, 1, 1) + timedelta(days=i) for i in range(1500)]
    payloads: list[str] = []
    url = make_url(migrated_database_url)
    raw = await asyncpg.connect(
        user=url.username, password=url.password, host=url.host, port=url.port,
        database=url.database,
    )  # fmt: skip
    await raw.add_listener(events.CHANNEL, lambda *args: payloads.append(args[3]))
    try:
        async with http(server) as client:
            user_id = await register(client, "large")
            async with SseStream(client) as tab:
                async with AsyncSession(db_engine) as session:
                    await events.publish_summary_updated(session, user_id, reversed(dates))
                    await session.commit()
                got: list[list[str]] = []
                while sum(map(len, got)) < len(dates):
                    event = await tab.next_of("summary.updated")
                    got.append(event.data["dates"])
    finally:
        await raw.close()

    assert len(payloads) >= 3
    assert all(len(p.encode()) < 8000 for p in payloads)
    assert [d for chunk in got for d in chunk] == [d.isoformat() for d in dates]


@pytest.mark.xfail(strict=True, reason="step 5.1: not implemented")
async def test_events_requires_auth_401(clean: None, server: str) -> None:
    async with http(server) as client:
        response = await client.get("/api/events")
    assert response.status_code == 401


async def listener_pids(engine: AsyncEngine) -> list[int]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT pid FROM pg_stat_activity "
                "WHERE application_name = :name AND datname = current_database()"
            ),
            {"name": events.LISTENER_APP_NAME},
        )
        return [row.pid for row in result]


@pytest.mark.xfail(strict=True, reason="step 5.1: not implemented")
async def test_listener_recovers_after_db_connection_drop(
    clean: None, server: str, db_engine: AsyncEngine
) -> None:
    async with http(server) as client:
        user_id = await register(client, "drop")
        async with SseStream(client) as tab:
            [pid] = await listener_pids(db_engine)
            async with db_engine.connect() as conn:
                await conn.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})

            # The stream stays open; once the api listens again it tells the tab to refetch
            # everything (events of the gap are lost), and new events flow again.
            await tab.next_of("resync", within=15)
            [new_pid] = await listener_pids(db_engine)
            assert new_pid != pid
            sent = await publish(db_engine, user_id, "goal.changed", {"goal_id": 3})
            event = await tab.next_of("goal.changed")
    assert event.data == {"goal_id": 3}
    assert event.at - sent <= DELIVERY_S
