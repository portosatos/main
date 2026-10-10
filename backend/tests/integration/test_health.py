import time

import httpx

from app.config import Settings
from app.main import create_app

# Nothing listens on port 1: connection is refused right away.
UNREACHABLE_DB_URL = "postgresql+asyncpg://health:health@127.0.0.1:1/health_tracker"


async def get_health(database_url: str) -> httpx.Response:
    app = create_app(Settings(_env_file=None, database_url=database_url))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/health")


async def test_health_ok_when_db_up(test_database_url: str) -> None:
    response = await get_health(test_database_url)

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["db"]) == ("ok", "ok")
    assert body["worker"]["status"] in ("ok", "stale", "unknown")  # see test_ingest_jobs.py


async def test_health_503_when_db_unreachable() -> None:
    started = time.monotonic()
    response = await get_health(UNREACHABLE_DB_URL)
    elapsed = time.monotonic() - started

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "db": "unreachable"}
    assert elapsed < 5, f"health must answer fast when the DB is down, took {elapsed:.1f}s"
