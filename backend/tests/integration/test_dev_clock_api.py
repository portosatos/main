from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import AppEnv, Settings
from app.main import create_app
from app.worker.main import worker_context

pytestmark = pytest.mark.xfail(strict=True, reason="step 1.1: not implemented")


@asynccontextmanager
async def api_client(
    database_url: str,
    app_env: AppEnv = "dev",
    sessionmaker: async_sessionmaker[AsyncSession] | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(_env_file=None, database_url=database_url, app_env=app_env)
    app = create_app(settings, sessionmaker=sessionmaker)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


def parse_times(body: dict) -> tuple[datetime, datetime]:
    return datetime.fromisoformat(body["system_now"]), datetime.fromisoformat(body["now"])


async def test_set_and_get_offset_in_dev(
    migrated_database_url: str, test_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    async with api_client(migrated_database_url, sessionmaker=test_sessionmaker) as client:
        initial = await client.get("/api/dev/clock")
        posted = await client.post("/api/dev/clock", json={"offset_seconds": 3600})
        got = await client.get("/api/dev/clock")

    assert initial.status_code == 200
    assert initial.json()["offset_seconds"] == 0

    assert posted.status_code == 200
    assert got.status_code == 200
    for body in (posted.json(), got.json()):
        assert body["offset_seconds"] == 3600
        system_now, now = parse_times(body)
        assert now - system_now == timedelta(hours=1)
        assert abs(system_now - datetime.now(UTC)) < timedelta(minutes=1)


async def test_post_rejects_out_of_range_offset(
    migrated_database_url: str, test_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    async with api_client(migrated_database_url, sessionmaker=test_sessionmaker) as client:
        too_far = await client.post("/api/dev/clock", json={"offset_seconds": 10**10})
        not_int = await client.post("/api/dev/clock", json={"offset_seconds": "soon"})

    assert too_far.status_code == 422
    assert not_int.status_code == 422


async def test_dev_routes_404_in_prod(
    migrated_database_url: str, test_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    async with api_client(migrated_database_url, "prod", test_sessionmaker) as client:
        prod_get = await client.get("/api/dev/clock")
        prod_post = await client.post("/api/dev/clock", json={"offset_seconds": 60})
    async with api_client(migrated_database_url, "dev", test_sessionmaker) as client:
        dev_get = await client.get("/api/dev/clock")

    assert prod_get.status_code == 404
    assert prod_post.status_code == 404
    # Control: the same route exists in dev, so the 404 above is not a typo in the path.
    assert dev_get.status_code == 200


@pytest.fixture
async def committed_offset_cleanup(db_engine: AsyncEngine) -> AsyncIterator[None]:
    """The next test commits through real engines (api and worker are separate processes)."""
    yield
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM dev_clock"))


@pytest.mark.usefixtures("committed_offset_cleanup")
async def test_worker_and_api_see_same_offset(migrated_database_url: str) -> None:
    async with api_client(migrated_database_url) as client:
        posted = await client.post("/api/dev/clock", json={"offset_seconds": 7200})
    assert posted.status_code == 200

    worker_settings = Settings(_env_file=None, database_url=migrated_database_url, app_env="dev")
    async with worker_context(worker_settings) as worker:
        reading = await worker.clock.read()

    assert reading.offset_seconds == 7200
    assert reading.now - reading.system_now == timedelta(hours=2)
    _, api_now = parse_times(posted.json())
    assert abs(reading.now - api_now) < timedelta(minutes=1)
