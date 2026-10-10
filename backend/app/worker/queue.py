"""The job queue in Postgres (SPEC §6.1, §7.1 `jobs`): enqueue in the caller's transaction,
claim with `FOR UPDATE SKIP LOCKED`, wake workers with NOTIFY, requeue stale jobs by Clock."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

# Channel of NOTIFY on every enqueue; the worker LISTENs on it.
JOBS_CHANNEL = "jobs"
# SPEC §4: a job locked longer than this is back in the queue (the worker died).
STALE_AFTER = timedelta(minutes=5)


@dataclass(frozen=True)
class QueuedJob:
    id: int
    kind: str
    user_id: uuid.UUID | None
    payload: dict[str, Any]
    attempts: int


async def enqueue(
    session: AsyncSession,
    *,
    kind: str,
    user_id: uuid.UUID | None,
    payload: dict[str, Any],
    now: datetime,
) -> int:
    """Insert a queued job and NOTIFY (delivered at commit). The caller commits."""
    raise NotImplementedError("step 3.2")


async def requeue_stale(
    session: AsyncSession, *, now: datetime, stale_after: timedelta = STALE_AFTER
) -> int:
    """Return running jobs locked before `now - stale_after` to the queue; their number."""
    raise NotImplementedError("step 3.2")
