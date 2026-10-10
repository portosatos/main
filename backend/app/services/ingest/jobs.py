"""Ingest jobs: one upload (file or stream batch) and its report (SPEC F3)."""

import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IngestJob
from app.worker.queue import enqueue

IngestSource = Literal["file", "stream"]
# Kind of the queue job that processes an uploaded file.
INGEST_FILE = "ingest_file"


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
    """Register an uploaded file and queue its processing in one transaction (SPEC §4).
    The caller commits."""
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
