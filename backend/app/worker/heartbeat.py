"""Worker heartbeats: every worker process records its last tick (Clock time); /api/health shows
the latest one (SPEC §4 «Наблюдаемость»)."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WorkerHeartbeat


async def beat(session: AsyncSession, worker_id: str, now: datetime) -> None:
    """Upsert the worker's last tick. The caller commits."""
    stmt = insert(WorkerHeartbeat).values(worker_id=worker_id, beat_at=now)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[WorkerHeartbeat.worker_id], set_={"beat_at": stmt.excluded.beat_at}
        )
    )


async def last_beat(session: AsyncSession) -> datetime | None:
    """The latest tick of any worker, or None when no worker has ticked yet."""
    return await session.scalar(select(func.max(WorkerHeartbeat.beat_at)))
