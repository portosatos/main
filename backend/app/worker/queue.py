"""The job queue in Postgres (SPEC §6.1, §7.1 `jobs`): enqueue in the caller's transaction,
claim with `FOR UPDATE SKIP LOCKED`, wake workers with NOTIFY, requeue stale jobs by Clock.

Jobs of one user run one at a time: the claiming worker holds a session-level advisory lock on
the user for the whole job (SPEC F3). A crashed worker's connection closes and frees the lock;
its job stays `running` until `requeue_stale` returns it to the queue.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ARRAY, Uuid, bindparam, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.models import Job

# Channel of NOTIFY on every enqueue; the worker LISTENs on it.
JOBS_CHANNEL = "jobs"
# SPEC §4: a job locked longer than this is back in the queue (the worker died).
STALE_AFTER = timedelta(minutes=5)
# First key of the two-key advisory locks on users, so other advisory locks cannot clash.
USER_LOCK_NAMESPACE = 32


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
    result = await session.execute(
        update(Job)
        .where(Job.status == "running", Job.locked_at < now - stale_after)
        .values(status="queued", locked_at=None)
        .returning(Job.id)
    )
    return len(result.all())


# The oldest queued job not of a busy user, taken in one statement; SKIP LOCKED lets concurrent
# workers pass each other's candidate rows instead of waiting on them.
CLAIM = text("""
UPDATE jobs SET status = 'running', locked_at = :now, attempts = attempts + 1
WHERE id = (
    SELECT id FROM jobs
    WHERE status = 'queued' AND run_after <= :now
      AND (user_id IS NULL OR user_id <> ALL(:busy))
    ORDER BY id
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id, kind, user_id, payload, attempts""").bindparams(bindparam("busy", type_=ARRAY(Uuid)))


async def claim(conn: AsyncConnection, *, now: datetime) -> QueuedJob | None:
    """Take the oldest available job and lock its user on `conn` (session level: the lock
    outlives the claiming transaction and is held until `unlock_users`). Users locked by other
    workers are skipped; their jobs stay queued."""
    busy: list[uuid.UUID] = []
    while True:
        async with conn.begin() as transaction:
            row = (await conn.execute(CLAIM, {"now": now, "busy": busy})).first()
            if row is None:
                return None
            job = QueuedJob(row.id, row.kind, row.user_id, row.payload, row.attempts)
            if job.user_id is None or await conn.scalar(
                select(
                    func.pg_try_advisory_lock(USER_LOCK_NAMESPACE, func.hashtext(str(job.user_id)))
                )
            ):
                return job
            # Another worker is running a job of this user: undo the claim, look further.
            await transaction.rollback()
            busy.append(job.user_id)


async def lock_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Wait for the user's running job (if any) and keep its jobs off until this transaction
    ends: the transaction-level twin of the lock `claim` takes."""
    await session.execute(
        select(func.pg_advisory_xact_lock(USER_LOCK_NAMESPACE, func.hashtext(str(user_id))))
    )


async def try_lock_user(session: AsyncSession, user_id: uuid.UUID) -> bool:
    """Like `lock_user`, but without waiting: False if a job of the user is running."""
    locked = await session.scalar(
        select(func.pg_try_advisory_xact_lock(USER_LOCK_NAMESPACE, func.hashtext(str(user_id))))
    )
    return bool(locked)


async def unlock_users(conn: AsyncConnection) -> None:
    """Release the user locks taken by `claim` on this connection."""
    await conn.execute(select(func.pg_advisory_unlock_all()))
    await conn.commit()


async def touch(session: AsyncSession, job_id: int, now: datetime) -> None:
    """The job is alive: move its lock time, so it is not taken for stale."""
    await session.execute(update(Job).where(Job.id == job_id).values(locked_at=now))


async def finish(session: AsyncSession, job_id: int, status: str, error: str | None = None) -> None:
    """Mark the job done or failed. The caller commits."""
    await session.execute(
        update(Job).where(Job.id == job_id).values(status=status, last_error=error)
    )


async def release(session: AsyncSession, job_id: int) -> None:
    """Put an interrupted job back in the queue right away (graceful worker stop)."""
    await session.execute(
        update(Job).where(Job.id == job_id).values(status="queued", locked_at=None)
    )
