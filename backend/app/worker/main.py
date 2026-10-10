"""Worker loop.

Still a stub: logs a tick (with Clock time) every WORKER_TICK_S seconds. The job queue arrives
in step 3.2.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.clock import Clock, create_clock
from app.config import Settings
from app.db import create_engine, create_sessionmaker
from app.logging import configure_logging
from app.services.ingest.classify import BATCH_SIZE
from app.worker.queue import STALE_AFTER, QueuedJob

log = structlog.get_logger("app.worker")


@dataclass
class WorkerContext:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    clock: Clock


class SimulatedCrash(BaseException):
    """Test hook: the worker "dies" after batch k. A BaseException, so the job is not marked
    failed and stays locked, as after a real crash."""


@dataclass
class ClaimedJob:
    """A job taken by this worker: running, its user's advisory lock held until processed."""

    job: QueuedJob

    @property
    def payload(self) -> dict:
        return self.job.payload


class Worker:
    """Takes jobs from the queue and runs them; one job of a user at a time (advisory lock)."""

    def __init__(
        self,
        engine: AsyncEngine,
        clock: Clock,
        *,
        worker_id: str = "worker",
        tick_s: float = 30.0,
        batch_size: int = BATCH_SIZE,
        stale_after: timedelta = STALE_AFTER,
        crash_after_batch: int | None = None,
    ) -> None:
        self.engine = engine
        self.clock = clock
        self.worker_id = worker_id
        self.tick_s = tick_s
        self.batch_size = batch_size
        self.stale_after = stale_after
        self.crash_after_batch = crash_after_batch
        self.listening = asyncio.Event()

    async def tick(self) -> None:
        """Heartbeat (for /api/health) and return of stale jobs to the queue."""
        raise NotImplementedError("step 3.2")

    async def claim(self) -> ClaimedJob | None:
        """The oldest queued job whose user is not busy with another job, or None."""
        raise NotImplementedError("step 3.2")

    async def process(self, claimed: ClaimedJob) -> None:
        """Run the job, mark it done or failed, release the user's lock."""
        raise NotImplementedError("step 3.2")

    async def run_until_idle(self) -> int:
        """Claim and process jobs until none is available; the number processed."""
        raise NotImplementedError("step 3.2")

    async def run(self, stop: asyncio.Event) -> None:
        """The worker loop: wakes on NOTIFY or every tick_s, until `stop` is set."""
        raise NotImplementedError("step 3.2")


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
