"""Settings API (SPEC F10, F11, F12, §6.3; plan step 10.1): the address for digests, quiet hours
and the time zone history with «действует с».

Like test_goals.py these commit for real: events are heard by a LISTEN connection of the test, the
second tab by an SSE stream of a served api (test_events.py). Users get `@jobs.example.com`
addresses and are deleted by the `clean` fixture. They register in Moscow on Oct 1 (UTC); the
api's Clock is then moved to T.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from tests.integration import test_events
from tests.integration.test_events import DELIVERY_S, SseStream, http, register
from tests.integration.test_goals import api_user, listen, of_type
from tests.integration.test_ingest_jobs import wipe

REGISTERED = datetime(2026, 10, 1, tzinfo=UTC)
# 09:00 on Oct 10 in Moscow.
T = datetime(2026, 10, 10, 6, 0, tzinfo=UTC)

# The api of test_events.py served by uvicorn, with this module's settings.
server = test_events.server


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


async def get_settings(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get("/api/settings")
    assert response.status_code == 200, response.text
    return response.json()


async def get_timezones(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get("/api/settings/timezones")
    assert response.status_code == 200, response.text
    return response.json()


async def tz_jobs(engine: AsyncEngine, user_id: uuid.UUID) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT payload, status FROM jobs WHERE user_id = :u AND kind = 'tz_changed'"),
            {"u": user_id},
        )
        return [dict(row._mapping) for row in result]


async def test_update_email_and_quiet_hours(clean: None, settings: Settings) -> None:
    async with api_user(settings, "settings", at=REGISTERED) as (client, clock, user_id):
        clock.at = T
        email = (await client.get("/api/auth/me")).json()["email"]
        # A new user: digests go to the login, quiet hours 22:00–08:00 prefilled but off (ADR-026).
        assert await get_settings(client) == {
            "notify_email": email,
            "quiet_enabled": False,
            "quiet_start": "22:00",
            "quiet_end": "08:00",
            "timezone": "Europe/Moscow",
        }

        changes = {
            "notify_email": "me@mail.example.com",
            "quiet_enabled": True,
            "quiet_start": "23:30",
            "quiet_end": "07:15",
        }
        async with listen(settings.database_url, user_id) as events:
            response = await client.patch("/api/settings", json=changes)
            assert response.status_code == 200, response.text
            [changed] = of_type(await events.until("settings.changed"), "settings.changed")
            assert sorted(changed["fields"]) == sorted(changes)
            # The same values again change nothing and send nothing.
            again = await client.patch("/api/settings", json=changes)
            assert again.status_code == 200, again.text
            assert await events.quiet() == []
        assert response.json() == changes | {"timezone": "Europe/Moscow"}
        assert again.json() == response.json()
        assert await get_settings(client) == response.json()
        assert (await client.get("/api/auth/me")).json()["notify_email"] == "me@mail.example.com"

        # A partial PATCH keeps the other fields.
        off = await client.patch("/api/settings", json={"quiet_enabled": False})
        assert off.status_code == 200, off.text
        assert off.json() == changes | {"quiet_enabled": False, "timezone": "Europe/Moscow"}

        # An empty address means no digests: null, and the digests API warns (SPEC F10).
        for empty in ("", None):
            cleared = await client.patch("/api/settings", json={"notify_email": empty})
            assert cleared.status_code == 200, cleared.text
            assert cleared.json()["notify_email"] is None
        digests = (await client.get("/api/digests")).json()
        assert (digests["notify_email"], digests["warning"]) == (None, "no_notify_email")


@pytest.mark.parametrize(
    "body",
    [
        {"quiet_start": "25:00"},
        {"quiet_start": "7:15"},
        {"quiet_end": "22:00:30"},
        {"quiet_end": "noon"},
        {"quiet_start": ""},
        {"quiet_start": None},
        {"quiet_end": 2200},
        {"quiet_enabled": "maybe"},
        {"quiet_enabled": None},
        {"notify_email": "not-an-email"},
        # The zone is changed through the history, not here.
        {"timezone": "UTC"},
    ],
)
async def test_invalid_quiet_hours_422(
    clean: None, settings: Settings, body: dict[str, Any]
) -> None:
    async with api_user(settings, "settings-bad", at=REGISTERED) as (client, clock, _user_id):
        clock.at = T
        before = await get_settings(client)
        response = await client.patch("/api/settings", json=body)
        assert response.status_code == 422, response.text
        assert await get_settings(client) == before


@pytest.mark.xfail(strict=True, reason="step 10.1: not implemented")
async def test_timezone_history_and_past_move(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with api_user(settings, "settings-tz", at=REGISTERED) as (client, clock, user_id):
        clock.at = T
        assert await get_timezones(client) == {
            "current": "Europe/Moscow",
            "items": [
                {
                    "tz": "Europe/Moscow",
                    "valid_from": "2026-10-01T00:00:00Z",
                    "valid_to": None,
                    "current": True,
                }
            ],
        }

        # «Действует с» without an offset is the local time of the new zone (08:00 EDT = 12:00Z).
        async with listen(settings.database_url, user_id) as events:
            response = await client.post(
                "/api/settings/timezones",
                json={"tz": "America/New_York", "valid_from": "2026-10-05T08:00"},
            )
            assert response.status_code == 201, response.text
            [changed] = of_type(await events.until("settings.changed"), "settings.changed")
        assert changed == {"fields": ["timezone"]}
        history = {
            "current": "America/New_York",
            "items": [
                {
                    "tz": "America/New_York",
                    "valid_from": "2026-10-05T12:00:00Z",
                    "valid_to": None,
                    "current": True,
                },
                {
                    "tz": "Europe/Moscow",
                    "valid_from": "2026-10-01T00:00:00Z",
                    "valid_to": "2026-10-05T12:00:00Z",
                    "current": False,
                },
            ],
        }
        assert response.json() == history
        assert await get_timezones(client) == history
        # The dates from the move on are recomputed by a job (SPEC F5).
        assert await tz_jobs(db_engine, user_id) == [
            {
                "payload": {"valid_from": "2026-10-05T12:00:00+00:00", "valid_to": None},
                "status": "queued",
            }
        ]
        # Today and the zone of /api/auth/me follow the history: 02:00 on Oct 10 in New York.
        me = (await client.get("/api/auth/me")).json()
        assert (me["timezone"], me["today"]) == ("America/New_York", "2026-10-10")
        assert (await get_settings(client))["timezone"] == "America/New_York"

        # The same moment twice, or the zone already in effect then: nothing to change.
        for body in (
            {"tz": "Asia/Tokyo", "valid_from": "2026-10-05T12:00:00Z"},
            {"tz": "America/New_York", "valid_from": "2026-10-07T00:00:00Z"},
        ):
            conflict = await client.post("/api/settings/timezones", json=body)
            assert conflict.status_code == 409, conflict.text
        assert await get_timezones(client) == history

        # Without «действует с» the move is now (Clock).
        now = await client.post("/api/settings/timezones", json={"tz": "Asia/Tokyo"})
        assert now.status_code == 201, now.text
        assert now.json()["items"][0] == {
            "tz": "Asia/Tokyo",
            "valid_from": "2026-10-10T06:00:00Z",
            "valid_to": None,
            "current": True,
        }


@pytest.mark.xfail(strict=True, reason="step 10.1: not implemented")
@pytest.mark.parametrize("tz", ["Mars/Olympus", "europe/moscow", "", "UTC+3", None])
async def test_invalid_iana_tz_422(
    clean: None, settings: Settings, db_engine: AsyncEngine, tz: str | None
) -> None:
    async with api_user(settings, "settings-iana", at=REGISTERED) as (client, clock, user_id):
        clock.at = T
        before = await get_timezones(client)
        response = await client.post("/api/settings/timezones", json={"tz": tz})
        assert response.status_code == 422, response.text
        assert await get_timezones(client) == before
        assert await tz_jobs(db_engine, user_id) == []


@pytest.mark.xfail(strict=True, reason="step 10.1: not implemented")
async def test_future_valid_from_rejected(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    # SPEC F11, ADR-017: a move may be now or in the past, never later than Clock.now().
    async with api_user(settings, "settings-future", at=REGISTERED) as (client, clock, user_id):
        clock.at = T
        before = await get_timezones(client)
        for valid_from in (
            "2026-10-10T06:01:00Z",
            "2026-10-11T00:00:00+03:00",
            # Naive: 15:30 in Tokyo is 06:30Z, after T.
            "2026-10-10T15:30",
        ):
            response = await client.post(
                "/api/settings/timezones", json={"tz": "Asia/Tokyo", "valid_from": valid_from}
            )
            assert response.status_code == 422, response.text
        assert await get_timezones(client) == before
        assert await tz_jobs(db_engine, user_id) == []

        # Exactly now is allowed.
        response = await client.post(
            "/api/settings/timezones",
            json={"tz": "Asia/Tokyo", "valid_from": "2026-10-10T06:00:00Z"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["current"] == "Asia/Tokyo"


@pytest.mark.xfail(strict=True, reason="step 10.1: not implemented")
async def test_settings_changed_event_reaches_second_client(
    clean: None, server: str, db_engine: AsyncEngine
) -> None:
    # SPEC F11, F12: a change in one tab shows in the other within 2 s.
    async with http(server) as first:
        await register(first, "settings-tabs")
        async with http(server, first.cookies) as second, SseStream(second) as tab:
            loop = asyncio.get_running_loop()
            sent = loop.time()
            response = await first.patch("/api/settings", json={"quiet_enabled": True})
            assert response.status_code == 200, response.text
            event = await tab.next_of("settings.changed")
            assert event.data == {"fields": ["quiet_enabled"]}
            assert event.at - sent <= DELIVERY_S

            sent = loop.time()
            moved = await first.post("/api/settings/timezones", json={"tz": "Asia/Tokyo"})
            assert moved.status_code == 201, moved.text
            event = await tab.next_of("settings.changed")
            assert event.data == {"fields": ["timezone"]}
            assert event.at - sent <= DELIVERY_S
