"""jobs: the work queue of the worker in the same database (SPEC §4, §6.1, §7.1), and the
heartbeats of worker processes for /api/health."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

JOB_STATUS = Enum("queued", "running", "done", "failed", name="job_status")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        # Recompute requests of one scope merge while queued (SPEC §7.1).
        Index(
            "jobs_dedup_key_queued_key",
            "dedup_key",
            unique=True,
            postgresql_where=text("status = 'queued'"),
        ),
        # The claim query: queued jobs in id order.
        Index("ix_jobs_queued", "id", postgresql_where=text("status = 'queued'")),
    )

    # Identity: the queue order, independent of the (shiftable) Clock.
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(
        JOB_STATUS, nullable=False, default="queued", server_default=text("'queued'")
    )
    dedup_key: Mapped[str | None] = mapped_column(Text)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # Set on claim and after every checkpoint; older than 5 minutes means the worker died.
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkerHeartbeat(Base):
    """The last tick of each worker process (Clock time)."""

    __tablename__ = "worker_heartbeat"

    worker_id: Mapped[str] = mapped_column(Text, primary_key=True)
    beat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
