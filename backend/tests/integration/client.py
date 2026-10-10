"""An in-process API client for integration tests."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import AppEnv, Settings
from app.main import create_app

# SPEC F1: every mutating request carries this header (CSRF protection).
CSRF_HEADERS = {"X-Requested-With": "ht"}


@asynccontextmanager
async def api_client(
    database_url: str,
    app_env: AppEnv = "dev",
    sessionmaker: async_sessionmaker[AsyncSession] | None = None,
    *,
    csrf: bool = True,
) -> AsyncIterator[httpx.AsyncClient]:
    """A client of a fresh app. With `csrf=False` requests go without the CSRF header, like a
    cross-site form would."""
    settings = Settings(_env_file=None, database_url=database_url, app_env=app_env)
    app = create_app(settings, sessionmaker=sessionmaker)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            headers=CSRF_HEADERS if csrf else None,
        ) as client:
            yield client
