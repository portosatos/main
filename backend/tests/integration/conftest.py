"""Test database fixtures.

Integration tests use a separate database: TEST_DATABASE_URL, by default `health_tracker_test`
on the compose Postgres at localhost:5433. It is created on first use and migrated to the Alembic
head once per session. Start Postgres with `docker compose up -d --wait postgres` or just run
scripts/test.ps1 / scripts/test.sh.

Isolation: `db_connection` opens a transaction that is rolled back after the test, and
`test_sessionmaker` binds sessions to it, so their commits become savepoints and nothing leaks.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command
from app.db import create_sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
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


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


async def run_alembic(database_url: str, name: str, *args: str) -> None:
    """Run an Alembic command, e.g. run_alembic(url, "upgrade", "head").

    env.py calls asyncio.run(), so the command runs in a worker thread with its own event loop.
    """
    await asyncio.to_thread(getattr(command, name), alembic_config(database_url), *args)


@pytest.fixture(scope="session")
async def test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    await ensure_database(url)
    return url


@pytest.fixture(scope="session")
async def migrated_database_url(test_database_url: str) -> str:
    await run_alembic(test_database_url, "upgrade", "head")
    return test_database_url


@pytest.fixture(scope="session")
async def db_engine(migrated_database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_database_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_connection(db_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with db_engine.connect() as conn:
        transaction = await conn.begin()
        try:
            yield conn
        finally:
            await transaction.rollback()


@pytest.fixture
def test_sessionmaker(db_connection: AsyncConnection) -> async_sessionmaker[AsyncSession]:
    return create_sessionmaker(db_connection)
