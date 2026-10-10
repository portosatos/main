"""Worker loop.

Still a stub: logs a tick (with Clock time) every WORKER_TICK_S seconds. The job queue arrives
in step 3.2.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.clock import Clock, create_clock
from app.config import Settings
from app.db import create_engine, create_sessionmaker
from app.logging import configure_logging

log = structlog.get_logger("app.worker")


@dataclass
class WorkerContext:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    clock: Clock


@asynccontextmanager
async def worker_context(settings: Settings) -> AsyncIterator[WorkerContext]:
    """Database and clock of the worker process (the same wiring as the api's)."""
    engine = create_engine(settings)
    sessionmaker = create_sessionmaker(engine)
    try:
        yield WorkerContext(engine, sessionmaker, create_clock(settings, sessionmaker))
    finally:
        await engine.dispose()


async def run(settings: Settings, tick_s: float) -> None:
    async with worker_context(settings) as ctx:
        log.info("worker_started", tick_s=tick_s, app_env=settings.app_env)
        tick = 0
        while True:
            tick += 1
            try:
                reading = await ctx.clock.read()
            except Exception as exc:  # a DB hiccup must not kill the worker loop
                log.warning("worker_tick_clock_failed", tick=tick, error=repr(exc))
            else:
                log.info(
                    "worker_tick",
                    tick=tick,
                    now=reading.now.isoformat(),
                    offset_seconds=reading.offset_seconds,
                )
            await asyncio.sleep(tick_s)


def main() -> None:
    configure_logging()
    try:
        asyncio.run(run(Settings(), float(os.environ.get("WORKER_TICK_S", "30"))))
    except KeyboardInterrupt:
        log.info("worker_stopped")
