"""ingest_jobs and the raw telemetry tables, the source of truth (SPEC F3, F4.1, §7.1).

Raw records are stored as they came, in UTC; derived minute tables are rebuilt from them.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

INGEST_SOURCE = Enum("file", "stream", name="ingest_source")
INGEST_STATUS = Enum("queued", "processing", "done", "failed", name="ingest_status")


class IngestJob(Base):
    """One upload, its progress, checkpoint and report (SPEC F3)."""

    __tablename__ = "ingest_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(INGEST_SOURCE, nullable=False)
    filename: Mapped[str | None] = mapped_column(Text)
    # The uploaded file on the ingest volume; deleted once the job is done.
    file_path: Mapped[str | None] = mapped_column(Text)
    bytes_total: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    # Checkpoint: bytes and lines processed and committed together with their records.
    bytes_done: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    # A stream batch starts at -1: its meta line is line 0, its records are numbered from 1.
    lines_done: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(
        INGEST_STATUS, nullable=False, default="queued", server_default=text("'queued'")
    )
    records_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    records_new: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    records_duplicate: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    records_conflict: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    records_invalid: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # The first 50 invalid and conflicting lines: [{"line", "kind", "reason"}].
    errors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # Devices created without meta (SPEC §7.2), as text for the report.
    warnings: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # Local dates whose summaries are stale, committed with the checkpoint until they are
    # recomputed: a resumed job recomputes them too (services/summaries.py).
    dirty_dates: Mapped[list[date]] = mapped_column(
        ARRAY(Date), nullable=False, server_default=text("'{}'::date[]")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class _Origin:
    """Where a raw record came from (SPEC F4.1)."""

    ingest_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingest_jobs.id"), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StepsRaw(_Origin, Base):
    """Steps over [start_utc, end_utc). Intervals of one device never overlap; neighbours may
    touch (the exclusion constraint on half-open ranges)."""

    __tablename__ = "steps_raw"
    __table_args__ = (
        ExcludeConstraint(
            ("device_id", "="),
            (func.tstzrange(text("start_utc"), text("end_utc"), text("'[)'")), "&&"),
            using="gist",
            name="steps_raw_no_overlap",
        ),
        CheckConstraint("end_utc > start_utc", name="steps_raw_positive_interval"),
        CheckConstraint("count >= 0", name="steps_raw_count_not_negative"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    end_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)


class SleepRaw(_Origin, Base):
    """Sleep over [start_utc, end_utc). Intervals of one device may overlap: sleep is merged as
    a set of minutes later."""

    __tablename__ = "sleep_raw"
    __table_args__ = (CheckConstraint("end_utc > start_utc", name="sleep_raw_positive_interval"),)

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    end_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)


class HrPoint(_Origin, Base):
    __tablename__ = "hr_point"
    __table_args__ = (CheckConstraint("bpm BETWEEN 30 AND 230", name="hr_point_bpm_range"),)

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    ts_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    bpm: Mapped[int] = mapped_column(SmallInteger, nullable=False)
