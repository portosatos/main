"""Job handlers of the worker. `ingest_file`: an uploaded NDJSON file, batch by batch (SPEC F3);
`tz_changed`: the dates a move in the time zone history changed (SPEC F5, services/timezones.py).

Every batch is one transaction: its records, the job counters and the checkpoint (byte offset
and line number after the batch) are committed together. A resumed job starts right after the
last committed batch, so the result equals an uninterrupted run (ADR-031).

The local dates a batch makes stale are committed with the checkpoint too; their summaries are
recomputed in the batch transaction after the first batch, then at least every
`summary_flush_s` seconds, and the rest in the transaction that finishes the job — so the
summaries fill in while the file is processed and a resumed job loses no date (ADR-036).

The user's tabs hear of it in the same transactions (ADR-039): `ingest.progress` when the job
starts and after a batch at most every `progress_s` seconds, `summary.updated` with the dates of
every flush, `ingest.done` when the job is done or has failed.

The transaction that finishes the job also evaluates the user's rules on the fresh summaries
(SPEC F9, services/rules/engine.py).
"""

import asyncio
import itertools
import math
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clock import Clock
from app.models import IngestJob
from app.services.events import publish_summary_updated
from app.services.ingest.classify import ERRORS_LIMIT, Counts, ingest_records
from app.services.ingest.jobs import INGEST_FILE, JobStatus, job_counts, publish_job_event
from app.services.ingest.parser import Line, parse_lines
from app.services.rules.engine import evaluate_user
from app.services.summaries import recompute_dates
from app.services.timezones import TZ_CHANGED, apply_tz_change
from app.worker.queue import QueuedJob


@dataclass
class JobContext:
    job: QueuedJob
    sessionmaker: async_sessionmaker[AsyncSession]
    clock: Clock
    batch_size: int
    # Inside a batch transaction: keep the job and the worker alive (lock time, heartbeat).
    checkpoint: Callable[[AsyncSession, datetime], Awaitable[None]]
    # After batch k is committed: the test hooks (crash, pause) and the graceful stop.
    after_batch: Callable[[int], Awaitable[None]]
    # Stale summaries are recomputed at least this often, in seconds, and at the end of the job.
    summary_flush_s: float
    # Progress events after batches at most this often, in seconds.
    progress_s: float


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
    dirty_dates: set[date] = field(default_factory=set)

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
            set(job.dirty_dates),
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
        self.dirty_dates |= counts.dirty_dates

    def counts(self) -> dict[str, int]:
        return {
            "new": self.new,
            "duplicate": self.duplicate,
            "conflict": self.conflict,
            "invalid": self.invalid,
        }

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
            "dirty_dates": sorted(self.dirty_dates),
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
        await publish_job_event(  # a resumed job too: its tabs see it move again
            session,
            user_id=ingest.user_id,
            job_id=job_id,
            status="processing",
            bytes_done=ingest.bytes_done,
            bytes_total=ingest.bytes_total,
            counts=job_counts(ingest),
        )
        await session.commit()
    progress = Progress.of(ingest)
    path = Path(ingest.file_path or "")
    flushed_at = -math.inf  # the first batch shows its summaries at once
    reported_at = time.monotonic()

    async def flush_summaries(session: AsyncSession, now: datetime) -> None:
        nonlocal flushed_at
        await recompute_dates(session, ingest.user_id, progress.dirty_dates, now)
        if progress.dirty_dates:
            await publish_summary_updated(session, ingest.user_id, progress.dirty_dates)
        progress.dirty_dates.clear()
        flushed_at = time.monotonic()

    async def report(session: AsyncSession, status: JobStatus) -> None:
        nonlocal reported_at
        await publish_job_event(
            session,
            user_id=ingest.user_id,
            job_id=job_id,
            status=status,
            bytes_done=progress.bytes_done,
            bytes_total=ingest.bytes_total,
            counts=progress.counts(),
        )
        reported_at = time.monotonic()

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
                if time.monotonic() - flushed_at >= ctx.summary_flush_s:
                    await flush_summaries(session, now)
                if time.monotonic() - reported_at >= ctx.progress_s:
                    await report(session, "processing")
                await session.execute(
                    update(IngestJob).where(IngestJob.id == job_id).values(**progress.values())
                )
                await ctx.checkpoint(session, now)
                await session.commit()
            await ctx.after_batch(number)

    async with ctx.sessionmaker() as session:
        now = await ctx.clock.now()
        await flush_summaries(session, now)
        await evaluate_user(session, ingest.user_id, now)
        progress.bytes_done = ingest.bytes_total  # trailing blank lines yield no batch
        await report(session, "done")
        await session.execute(
            update(IngestJob)
            .where(IngestJob.id == job_id)
            .values(
                status="done",
                dirty_dates=[],
                bytes_done=ingest.bytes_total,
                finished_at=now,
            )
        )
        await session.commit()
    await asyncio.to_thread(path.unlink, missing_ok=True)


async def ingest_file_failed(session: AsyncSession, job: QueuedJob, now: datetime) -> None:
    """The report shows the failure, and the user's tabs; the file stays on the volume for a
    look."""
    failed = await session.scalar(
        update(IngestJob)
        .where(IngestJob.id == ingest_job_id(job), IngestJob.status != "done")
        .values(status="failed", finished_at=now)
        .returning(IngestJob)
    )
    if failed is not None:
        await publish_job_event(
            session,
            user_id=failed.user_id,
            job_id=failed.id,
            status="failed",
            bytes_done=failed.bytes_done,
            bytes_total=failed.bytes_total,
            counts=job_counts(failed),
        )


@dataclass(frozen=True)
class Handler:
    run: Callable[[JobContext], Awaitable[None]]
    failed: Callable[[AsyncSession, QueuedJob, datetime], Awaitable[None]]


async def tz_changed(ctx: JobContext) -> None:
    """Recompute the dates the move changed and evaluate the rules, in one transaction: a
    repeated run gives the same summaries and changes no recommendation again."""
    assert ctx.job.user_id is not None
    async with ctx.sessionmaker() as session:
        await apply_tz_change(session, ctx.job.user_id, ctx.job.payload, await ctx.clock.now())
        await session.commit()


async def tz_changed_failed(session: AsyncSession, job: QueuedJob, now: datetime) -> None:
    """Nothing to report: the error stays in jobs.last_error; the next move or `htadmin rebuild`
    recomputes the dates."""


HANDLERS: dict[str, Handler] = {
    INGEST_FILE: Handler(ingest_file, ingest_file_failed),
    TZ_CHANGED: Handler(tz_changed, tz_changed_failed),
}
