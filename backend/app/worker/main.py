"""Worker loop.

Step 0.2 stub: logs a tick every WORKER_TICK_S seconds. The job queue arrives in step 3.2.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import structlog

from app.clock import Clock
from app.config import Settings
from app.logging import configure_logging

log = structlog.get_logger("app.worker")


@dataclass
class WorkerContext:
    clock: Clock


@asynccontextmanager
async def worker_context(settings: Settings) -> AsyncIterator[WorkerContext]:
    """Database and clock of the worker process."""
    raise NotImplementedError("step 1.1")
    yield


async def run(tick_s: float) -> None:
    log.info("worker_started", tick_s=tick_s)
    tick = 0
    while True:
        tick += 1
        log.info("worker_tick", tick=tick)
        await asyncio.sleep(tick_s)


def main() -> None:
    configure_logging()
    try:
        asyncio.run(run(float(os.environ.get("WORKER_TICK_S", "30"))))
    except KeyboardInterrupt:
        log.info("worker_stopped")
