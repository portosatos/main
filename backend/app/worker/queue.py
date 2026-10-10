"""The job queue in Postgres (SPEC §6.1, §7.1 `jobs`): enqueue in the caller's transaction,
claim with `FOR UPDATE SKIP LOCKED`, wake workers with NOTIFY, requeue stale jobs by Clock."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job

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
    job = Job(kind=kind, user_id=user_id, payload=payload, run_after=now, created_at=now)
    session.add(job)
    await session.flush()
    await session.execute(select(func.pg_notify(JOBS_CHANNEL, kind)))
    return job.id


async def requeue_stale(
    session: AsyncSession, *, now: datetime, stale_after: timedelta = STALE_AFTER
) -> int:
    """Return running jobs locked before `now - stale_after` to the queue; their number."""
    raise NotImplementedError("step 3.2")
