"""FastAPI application factory. Run: uvicorn --factory app.main:create_app"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import dev, health
from app.clock import create_clock
from app.config import Settings
from app.db import create_engine, create_sessionmaker
from app.logging import configure_logging


def create_app(
    settings: Settings | None = None,
    *,
    sessionmaker: async_sessionmaker[AsyncSession] | None = None,
) -> FastAPI:
    """`sessionmaker` overrides the default one (tests bind it to a rolled-back connection)."""
    settings = settings or Settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = create_engine(settings)
        app.state.sessionmaker = sessionmaker or create_sessionmaker(app.state.engine)
        app.state.clock = create_clock(settings, app.state.sessionmaker)
        try:
            yield
        finally:
            await app.state.engine.dispose()

    app = FastAPI(title="Health Tracker API", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health.router)
    if settings.app_env == "dev":
        app.include_router(dev.router)
    return app
