from collections.abc import AsyncIterator

import asyncpg
import pytest
from sqlalchemy.engine import make_url

from tests.integration.conftest import ensure_database, run_alembic

TABLES_SQL = "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"


async def fetch(url: str, query: str) -> list[asyncpg.Record]:
    parsed = make_url(url)
    conn = await asyncpg.connect(
        user=parsed.username,
        password=parsed.password,
        host=parsed.host,
        port=parsed.port,
        database=parsed.database,
    )
    try:
        return await conn.fetch(query)
    finally:
        await conn.close()


async def tables(url: str) -> set[str]:
    return {row["tablename"] for row in await fetch(url, TABLES_SQL)} - {"alembic_version"}


async def current_revision(url: str) -> str | None:
    if "alembic_version" not in {row["tablename"] for row in await fetch(url, TABLES_SQL)}:
        return None
    rows = await fetch(url, "SELECT version_num FROM alembic_version")
    return rows[0]["version_num"] if rows else None


@pytest.fixture
async def scratch_database_url(test_database_url: str) -> AsyncIterator[str]:
    """A database of its own, so downgrading does not disturb the shared migrated test DB."""
    url = make_url(test_database_url)
    scratch = url.set(database=f"{url.database}_migrations").render_as_string(hide_password=False)
    await ensure_database(scratch)
    await run_alembic(scratch, "downgrade", "base")
    yield scratch


async def test_upgrade_downgrade_upgrade_head(scratch_database_url: str) -> None:
    url = scratch_database_url

    await run_alembic(url, "upgrade", "head")
    after_first_upgrade = await tables(url)
    head = await current_revision(url)
    assert "dev_clock" in after_first_upgrade
    assert head is not None

    await run_alembic(url, "downgrade", "base")
    assert await tables(url) == set(), "downgrade to base must drop everything it created"
    assert await current_revision(url) is None

    await run_alembic(url, "upgrade", "head")
    assert await tables(url) == after_first_upgrade
    assert await current_revision(url) == head
