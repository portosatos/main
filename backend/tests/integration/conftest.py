"""Test database fixture.

Integration tests use a separate database: TEST_DATABASE_URL, by default `health_tracker_test`
on the compose Postgres at localhost:5433. It is created on first use. Start Postgres with
`docker compose up -d --wait postgres` or just run scripts/test.ps1 / scripts/test.sh.
"""

import os

import asyncpg
import pytest
from sqlalchemy.engine import make_url

DEFAULT_TEST_DATABASE_URL = "postgresql+asyncpg://health:health@localhost:5433/health_tracker_test"


async def ensure_database(url: str) -> None:
    """Create the database from `url` if it does not exist yet (connects to the `postgres` db)."""
    parsed = make_url(url)
    try:
        conn = await asyncpg.connect(
            user=parsed.username,
            password=parsed.password,
            host=parsed.host,
            port=parsed.port,
            database="postgres",
            timeout=5,
        )
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.fail(
            f"Test Postgres is unreachable at {parsed.host}:{parsed.port} ({exc!r}). "
            "Start it: docker compose up -d --wait postgres",
            pytrace=False,
        )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", parsed.database
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{parsed.database}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
async def test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    await ensure_database(url)
    return url
