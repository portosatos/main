"""Ingest jobs: one upload (file or stream batch) and its report (SPEC F3).

The tabs of the user follow a job by `ingest.progress` (queued, processing, after batches) and
`ingest.done` (done or failed), with the same counts as the report (ADR-039).
"""

import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IngestJob
from app.services import events
from app.worker.queue import enqueue

IngestSource = Literal["file", "stream"]
# Kind of the queue job that processes an uploaded file.
INGEST_FILE = "ingest_file"
# The worker reports progress after a batch at most this often, in seconds; SPEC F3 asks for at
# least every 2 s, which holds while a batch takes less than that.
PROGRESS_INTERVAL_S = 1.0
JobStatus = Literal["queued", "processing", "done", "failed"]


async def publish_job_event(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    status: JobStatus,
    bytes_done: int,
    bytes_total: int,
    counts: dict[str, int],
) -> None:
    """`ingest.done` for a finished job, `ingest.progress` otherwise; sent at commit.
    `counts`: new, duplicate, conflict, invalid."""
    kind = "ingest.done" if status in ("done", "failed") else "ingest.progress"
    data = {
        "job_id": str(job_id),
        "status": status,
        "bytes_done": bytes_done,
        "bytes_total": bytes_total,
        "counts": counts,
    }
    await events.publish(session, user_id, kind, data)


def job_counts(job: IngestJob) -> dict[str, int]:
    return {
        "new": job.records_new,
        "duplicate": job.records_duplicate,
        "conflict": job.records_conflict,
        "invalid": job.records_invalid,
    }


async def create_ingest_job(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    source: IngestSource,
    filename: str | None,
    now: datetime,
    job_id: uuid.UUID | None = None,
    file_path: str | None = None,
    bytes_total: int = 0,
) -> uuid.UUID:
    """Insert a queued job of the user and return its id. The caller commits."""
    job = IngestJob(
        id=job_id or uuid.uuid4(),
        user_id=user_id,
        source=source,
        filename=filename,
        file_path=file_path,
        bytes_total=bytes_total,
        created_at=now,
    )
    session.add(job)
    await session.flush()
    return job.id


async def submit_file(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    filename: str,
    file_path: str,
    bytes_total: int,
    now: datetime,
) -> None:
    """Register an uploaded file and queue its processing in one transaction (SPEC §4); the
    user's tabs see the queued job. The caller commits."""
    await create_ingest_job(
        session,
        user_id=user_id,
        source="file",
        filename=filename,
        now=now,
        job_id=job_id,
        file_path=file_path,
        bytes_total=bytes_total,
    )
    await enqueue(
        session,
        kind=INGEST_FILE,
        user_id=user_id,
        payload={"ingest_job_id": str(job_id)},
        now=now,
    )
    await publish_job_event(
        session,
        user_id=user_id,
        job_id=job_id,
        status="queued",
        bytes_done=0,
        bytes_total=bytes_total,
        counts=dict.fromkeys(("new", "duplicate", "conflict", "invalid"), 0),
    )
