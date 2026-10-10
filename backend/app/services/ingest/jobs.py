"""Ingest jobs: one upload (file or stream batch) and its report (SPEC F3)."""

import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IngestJob

IngestSource = Literal["file", "stream"]


async def create_ingest_job(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    source: IngestSource,
    filename: str | None,
    now: datetime,
) -> uuid.UUID:
    """Insert a queued job of the user and return its id. The caller commits."""
    job = IngestJob(user_id=user_id, source=source, filename=filename, created_at=now)
    session.add(job)
    await session.flush()
    return job.id
