"""Database engine, session factory and connectivity check."""

import asyncio

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings

log = structlog.get_logger(__name__)


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"timeout": settings.db_health_timeout_s},
    )


def create_sessionmaker(bind: AsyncEngine | AsyncConnection) -> async_sessionmaker[AsyncSession]:
    """Sessions for request handlers and services. Tests bind it to a connection whose
    transaction is rolled back after each test (commits become savepoints)."""
    return async_sessionmaker(
        bind=bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


async def check_db(engine: AsyncEngine, timeout_s: float) -> bool:
    """True if `SELECT 1` succeeds within `timeout_s`. Never raises."""
    try:
        async with asyncio.timeout(timeout_s), engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # any failure means "unreachable" for the health check
        log.warning("db_check_failed", error=repr(exc))
        return False
    return True
