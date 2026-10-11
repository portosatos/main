"""Schemas of the ingest api (SPEC F3, §6.3)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models import IngestJob


class UploadAccepted(BaseModel):
    job_id: uuid.UUID


class BatchDevice(BaseModel):
    """A device of a stream batch, as in the meta line of a file (docs/DATA_FORMAT.md)."""

    id: str = Field(min_length=1)
    kind: Literal["watch", "phone"]
    name: str | None = None  # without a name the device is named by its id


class BatchIn(BaseModel):
    """A stream batch: up to 5000 records of the NDJSON format. A record that is not valid is
    counted as `invalid` in the report and does not reject the batch."""

    devices: list[BatchDevice] = []
    records: list[Any]


class IngestCounts(BaseModel):
    total: int
    new: int
    duplicate: int
    conflict: int
    invalid: int


class IngestErrorOut(BaseModel):
    line: int
    kind: Literal["invalid", "conflict"]
    reason: str


class IngestJobOut(BaseModel):
    id: uuid.UUID
    source: Literal["file", "stream"]
    filename: str | None
    status: Literal["queued", "processing", "done", "failed"]
    bytes_total: int
    bytes_done: int
    progress: float  # processed bytes / file size, 0..1
    counts: IngestCounts
    errors: list[IngestErrorOut]  # the first 50 invalid and conflicting lines
    warnings: list[str]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def of(cls, job: IngestJob) -> "IngestJobOut":
        if job.bytes_total:
            progress = min(job.bytes_done / job.bytes_total, 1.0)
        else:
            progress = 1.0 if job.status == "done" else 0.0
        return cls(
            id=job.id,
            source=job.source,
            filename=job.filename,
            status=job.status,
            bytes_total=job.bytes_total,
            bytes_done=job.bytes_done,
            progress=progress,
            counts=IngestCounts(
                total=job.records_total,
                new=job.records_new,
                duplicate=job.records_duplicate,
                conflict=job.records_conflict,
                invalid=job.records_invalid,
            ),
            errors=[IngestErrorOut(**error) for error in job.errors],
            warnings=job.warnings,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )
