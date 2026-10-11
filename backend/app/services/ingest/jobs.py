"""Ingest jobs: one upload (file or stream batch) and its report (SPEC F3).

A stream batch (`POST /api/ingest/batch`) is written to the ingest volume as NDJSON — the meta
line from its `devices`, then one line per record — and runs through the file pipeline. Its
meta line is line 0, so the report numbers the records as in `records`, from 1.

The tabs of the user follow a job by `ingest.progress` (queued, processing, after batches) and
`ingest.done` (done or failed), with the same counts as the report (ADR-039).
"""

import json
import uuid
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IngestJob
from app.services import events
from app.worker.queue import enqueue

IngestSource = Literal["file", "stream"]
# Kind of the queue job that processes an uploaded file.
INGEST_FILE = "ingest_file"
# Kind of the queue job that processes a stream batch: the same pipeline, rules debounced.
INGEST_BATCH = "ingest_batch"
# SPEC F3: a stream batch holds at most this many records.
BATCH_MAX_RECORDS = 5000
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
    lines_done: int = 0,
) -> uuid.UUID:
    """Insert a queued job of the user and return its id. The caller commits."""
    job = IngestJob(
        id=job_id or uuid.uuid4(),
        user_id=user_id,
        source=source,
        filename=filename,
        file_path=file_path,
        bytes_total=bytes_total,
        lines_done=lines_done,
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
    await _submit(
        session,
        kind=INGEST_FILE,
        user_id=user_id,
        job_id=job_id,
        filename=filename,
        file_path=file_path,
        bytes_total=bytes_total,
        now=now,
    )


def write_batch(path: Path, devices: Sequence[dict[str, Any]], records: Sequence[Any]) -> int:
    """Write a stream batch to `path` as NDJSON (meta line, then the records); its size."""
    with path.open("wb") as out:
        out.write(_line({"type": "meta", "schema": "ht.v1", "devices": list(devices)}))
        for record in records:
            out.write(_line(record))
        return out.tell()


def _line(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"


async def submit_batch(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    file_path: str,
    bytes_total: int,
    now: datetime,
) -> None:
    """Register a stream batch written by `write_batch` and queue it. The caller commits."""
    await _submit(
        session,
        kind=INGEST_BATCH,
        user_id=user_id,
        job_id=job_id,
        filename=None,
        file_path=file_path,
        bytes_total=bytes_total,
        now=now,
        lines_done=-1,  # the meta line is line 0
    )


async def _submit(
    session: AsyncSession,
    *,
    kind: str,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    filename: str | None,
    file_path: str,
    bytes_total: int,
    now: datetime,
    lines_done: int = 0,
) -> None:
    await create_ingest_job(
        session,
        user_id=user_id,
        source="file" if kind == INGEST_FILE else "stream",
        filename=filename,
        now=now,
        job_id=job_id,
        file_path=file_path,
        bytes_total=bytes_total,
        lines_done=lines_done,
    )
    await enqueue(
        session,
        kind=kind,
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
