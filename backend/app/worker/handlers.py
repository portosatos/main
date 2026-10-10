"""Job handlers of the worker. `ingest_file`: an uploaded NDJSON file, batch by batch (SPEC F3).

Every batch is one transaction: its records, the job counters and the checkpoint (byte offset
and line number after the batch) are committed together. A resumed job starts right after the
last committed batch, so the result equals an uninterrupted run (ADR-031).
"""

import asyncio
import itertools
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clock import Clock
from app.models import IngestJob
from app.services.ingest.classify import ERRORS_LIMIT, Counts, ingest_records
from app.services.ingest.jobs import INGEST_FILE
from app.services.ingest.parser import Line, parse_lines
from app.worker.queue import QueuedJob


@dataclass
class JobContext:
    job: QueuedJob
    sessionmaker: async_sessionmaker[AsyncSession]
    clock: Clock
    batch_size: int
    # Inside a batch transaction: keep the job and the worker alive (lock time, heartbeat).
    checkpoint: Callable[[AsyncSession, datetime], Awaitable[None]]
    # After batch k is committed: the crash test hook and the graceful stop.
    after_batch: Callable[[int], None]


@dataclass
class Progress:
    """Counters and checkpoint of an ingest job, carried between batches."""

    bytes_done: int
    lines_done: int
    new: int
    duplicate: int
    conflict: int
    invalid: int
    errors: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def of(cls, job: IngestJob) -> "Progress":
        return cls(
            job.bytes_done,
            job.lines_done,
            job.records_new,
            job.records_duplicate,
            job.records_conflict,
            job.records_invalid,
            list(job.errors),
            list(job.warnings),
        )

    def add(self, counts: Counts, last: Line) -> None:
        self.bytes_done = last.end_offset
        self.lines_done = last.number
        self.new += counts.new
        self.duplicate += counts.duplicate
        self.conflict += counts.conflict
        self.invalid += counts.invalid
        errors = self.errors + [
            {"line": e.line, "kind": e.kind, "reason": e.reason} for e in counts.errors
        ]
        self.errors = sorted(errors, key=lambda e: e["line"])[:ERRORS_LIMIT]
        self.warnings += [w for w in counts.warnings if w not in self.warnings]

    def values(self) -> dict[str, Any]:
        return {
            "bytes_done": self.bytes_done,
            "lines_done": self.lines_done,
            "records_total": self.new + self.duplicate + self.conflict + self.invalid,
            "records_new": self.new,
            "records_duplicate": self.duplicate,
            "records_conflict": self.conflict,
            "records_invalid": self.invalid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def ingest_job_id(job: QueuedJob) -> uuid.UUID:
    return uuid.UUID(job.payload["ingest_job_id"])


async def ingest_file(ctx: JobContext) -> None:
    job_id = ingest_job_id(ctx.job)
    async with ctx.sessionmaker() as session:
        ingest = await session.get(IngestJob, job_id)
        if ingest is None or ingest.status in ("done", "failed"):
            return  # already finished: a repeated run changes nothing
        if ingest.status == "queued":
            ingest.status = "processing"
            ingest.started_at = await ctx.clock.now()
            await session.commit()
    progress = Progress.of(ingest)
    path = Path(ingest.file_path or "")

    # The worker is a process of its own: reading the file in the loop blocks nobody else.
    with await asyncio.to_thread(path.open, "rb") as stream:
        stream.seek(progress.bytes_done)
        lines = parse_lines(
            stream, start_offset=progress.bytes_done, first_line=progress.lines_done + 1
        )
        for number, batch in enumerate(itertools.batched(lines, ctx.batch_size), start=1):
            async with ctx.sessionmaker() as session:
                now = await ctx.clock.now()
                counts = await ingest_records(
                    session,
                    user_id=ingest.user_id,
                    job_id=job_id,
                    now=now,
                    lines=batch,
                    batch_size=ctx.batch_size,
                )
                progress.add(counts, batch[-1])
                await session.execute(
                    update(IngestJob).where(IngestJob.id == job_id).values(**progress.values())
                )
                await ctx.checkpoint(session, now)
                await session.commit()
            ctx.after_batch(number)

    async with ctx.sessionmaker() as session:
        await session.execute(
            update(IngestJob)
            .where(IngestJob.id == job_id)
            .values(
                status="done",
                bytes_done=ingest.bytes_total,  # trailing blank lines yield no batch
                finished_at=await ctx.clock.now(),
            )
        )
        await session.commit()
    await asyncio.to_thread(path.unlink, missing_ok=True)


async def ingest_file_failed(session: AsyncSession, job: QueuedJob, now: datetime) -> None:
    """The report shows the failure; the file stays on the volume for a look."""
    await session.execute(
        update(IngestJob)
        .where(IngestJob.id == ingest_job_id(job), IngestJob.status != "done")
        .values(status="failed", finished_at=now)
    )


@dataclass(frozen=True)
class Handler:
    run: Callable[[JobContext], Awaitable[None]]
    failed: Callable[[AsyncSession, QueuedJob, datetime], Awaitable[None]]


HANDLERS: dict[str, Handler] = {INGEST_FILE: Handler(ingest_file, ingest_file_failed)}
