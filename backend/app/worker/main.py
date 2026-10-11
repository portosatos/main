"""The worker process: python -m app.worker (SPEC §6.1).

Takes jobs from the queue in Postgres and runs them. Wakes on NOTIFY from `enqueue` and, as a
fallback, every WORKER_TICK_S seconds; every tick records a heartbeat and returns stale jobs to
the queue. Jobs of one user run one at a time (advisory lock), jobs of different users in
parallel when several workers run.
"""

import asyncio
import os
import signal
import socket
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from app.clock import Clock, create_clock
from app.config import Settings
from app.db import create_engine, create_sessionmaker
from app.logging import configure_logging
from app.services.ingest.classify import BATCH_SIZE
from app.services.ingest.jobs import PROGRESS_INTERVAL_S
from app.services.summaries import FLUSH_INTERVAL_S
from app.worker import queue
from app.worker.handlers import HANDLERS, JobContext
from app.worker.heartbeat import beat
from app.worker.queue import JOBS_CHANNEL, STALE_AFTER, QueuedJob

log = structlog.get_logger("app.worker")

# SPEC F9: the rules are evaluated every hour as well, in case the local date has changed.
RULES_TICK_S = 3600.0


class SimulatedCrash(BaseException):
    """Test hook: the worker "dies" after batch k. A BaseException, so the job is not marked
    failed and stays locked, as after a real crash."""


class JobInterrupted(Exception):
    """The worker is stopping: the job goes back to the queue after its last committed batch."""


@dataclass
class ClaimedJob:
    """A job taken by this worker: running, its user's advisory lock held on `conn`."""

    job: QueuedJob
    conn: AsyncConnection

    @property
    def payload(self) -> dict:
        return self.job.payload

    async def close(self) -> None:
        """Free the user lock and the connection."""
        try:
            await queue.unlock_users(self.conn)
        finally:
            await self.conn.close()


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
        on_batch: Callable[[int], Awaitable[None]] | None = None,
        summary_flush_s: float = FLUSH_INTERVAL_S,
        progress_s: float = PROGRESS_INTERVAL_S,
        rules_tick_s: float = RULES_TICK_S,
    ) -> None:
        self.engine = engine
        self.clock = clock
        self.worker_id = worker_id
        self.tick_s = tick_s
        self.batch_size = batch_size
        self.stale_after = stale_after
        self.crash_after_batch = crash_after_batch
        # Test hook: awaited after every committed batch, e.g. to pause the job after batch k.
        self.on_batch = on_batch
        self.summary_flush_s = summary_flush_s
        self.progress_s = progress_s
        self.rules_tick_s = rules_tick_s
        self.listening = asyncio.Event()
        self._sessionmaker = create_sessionmaker(engine)
        self._stop: asyncio.Event | None = None

    async def tick(self) -> None:
        """Heartbeat (for /api/health) and return of stale jobs to the queue."""
        now = await self.clock.now()
        async with self._sessionmaker() as session:
            requeued = await queue.requeue_stale(session, now=now, stale_after=self.stale_after)
            await beat(session, self.worker_id, now)
            await session.commit()
        if requeued:
            log.warning("jobs_requeued", count=requeued)
        log.info("worker_tick", now=now.isoformat())

    async def rules_tick(self) -> None:
        """Evaluate the rules of the users with recent data: the anchors move with the day."""
        raise NotImplementedError("step 8.2")

    async def claim(self) -> ClaimedJob | None:
        """The oldest queued job whose user is not busy with another job, or None."""
        conn = await self.engine.connect()
        try:
            job = await queue.claim(conn, now=await self.clock.now())
        except BaseException:
            await conn.close()
            raise
        if job is None:
            await conn.close()
            return None
        return ClaimedJob(job, conn)

    async def process(self, claimed: ClaimedJob) -> None:
        """Run the job, mark it done or failed, release the user's lock."""
        job = claimed.job
        bound = log.bind(job_id=job.id, kind=job.kind, user_id=str(job.user_id))
        handler = HANDLERS.get(job.kind)
        try:
            bound.info("job_started", attempt=job.attempts)
            if handler is None:
                raise LookupError(f"unknown job kind {job.kind!r}")
            await handler.run(self._context(job))
        except JobInterrupted:
            async with self._sessionmaker() as session:
                await queue.release(session, job.id)
                await session.commit()
            bound.info("job_interrupted")
        except Exception as exc:
            bound.exception("job_failed")
            async with self._sessionmaker() as session:
                await queue.finish(session, job.id, "failed", repr(exc))
                if handler is not None:
                    await handler.failed(session, job, await self.clock.now())
                await session.commit()
        else:
            async with self._sessionmaker() as session:
                await queue.finish(session, job.id, "done")
                await session.commit()
            bound.info("job_done")
        finally:
            await claimed.close()

    async def run_until_idle(self) -> int:
        """Claim and process jobs until none is available; the number processed."""
        processed = 0
        while not self._stopping() and (claimed := await self.claim()) is not None:
            await self.process(claimed)
            processed += 1
        return processed

    async def run(self, stop: asyncio.Event) -> None:
        """The worker loop: wakes on NOTIFY or every tick_s, until `stop` is set."""
        self._stop = stop
        wake = asyncio.Event()
        listener = await self.engine.connect()
        try:
            driver = (await listener.get_raw_connection()).driver_connection
            await driver.add_listener(JOBS_CHANNEL, lambda *_: wake.set())
            self.listening.set()
            log.info("worker_started", worker_id=self.worker_id, tick_s=self.tick_s)
            next_tick = 0.0
            while not stop.is_set():
                if time.monotonic() >= next_tick:
                    next_tick = time.monotonic() + self.tick_s
                    await self._guarded(self.tick())
                wake.clear()
                await self._guarded(self.run_until_idle())
                await _wait_any(wake, stop, seconds=max(next_tick - time.monotonic(), 0))
        finally:
            self.listening.clear()
            await listener.close()
            log.info("worker_stopped", worker_id=self.worker_id)

    def _context(self, job: QueuedJob) -> JobContext:
        async def checkpoint(session: AsyncSession, now: datetime) -> None:
            await queue.touch(session, job.id, now)
            await beat(session, self.worker_id, now)

        async def after_batch(number: int) -> None:
            if self.crash_after_batch == number:
                raise SimulatedCrash(f"after batch {number}")
            if self.on_batch is not None:
                await self.on_batch(number)
            if self._stopping():
                raise JobInterrupted

        return JobContext(
            job,
            self._sessionmaker,
            self.clock,
            self.batch_size,
            checkpoint,
            after_batch,
            self.summary_flush_s,
            self.progress_s,
        )

    def _stopping(self) -> bool:
        return self._stop is not None and self._stop.is_set()

    async def _guarded(self, step: Awaitable[object]) -> None:
        """A failed tick or claim (database restart, ...) must not kill the loop."""
        try:
            await step
        except Exception as exc:
            log.warning("worker_step_failed", error=repr(exc))


async def _wait_any(*events: asyncio.Event, seconds: float) -> None:
    waiters = [asyncio.ensure_future(event.wait()) for event in events]
    try:
        await asyncio.wait(waiters, timeout=seconds, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for waiter in waiters:
            waiter.cancel()


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
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGTERM, signal.SIGINT):
            # Not on Windows; there Ctrl+C raises KeyboardInterrupt.
            with suppress(NotImplementedError):
                loop.add_signal_handler(signum, stop.set)
        worker = Worker(
            ctx.engine,
            ctx.clock,
            worker_id=f"{socket.gethostname()}-{os.getpid()}",
            tick_s=tick_s,
        )
        log.info("worker_starting", app_env=settings.app_env)
        await worker.run(stop)


def main() -> None:
    configure_logging()
    try:
        asyncio.run(run(Settings(), float(os.environ.get("WORKER_TICK_S", "30"))))
    except KeyboardInterrupt:
        log.info("worker_stopped")
