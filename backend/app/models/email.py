"""email_outbox: the opened recommendations waiting for a digest; email_digests: the planned and
the sent digests (SPEC F10, §7.1; ADR-050).

An outbox entry is written in the transaction that opens its recommendation. A digest row with
`sent_at` NULL is the user's planned digest — at most one, moved by the dispatcher every tick;
a sent one keeps the letter. At most one digest is sent per local date: the partial unique index
stops a second one even if two dispatchers race.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, Identity, Index, Text, Uuid
from sqlalchemy import text as sql
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

OUTBOX_STATUS = Enum("pending", "sent", "skipped", name="email_outbox_status")
PLAN_REASON = Enum("window", "max_delay", "daily_limit", "quiet_hours", name="digest_plan_reason")
SENT = sql("sent_at IS NOT NULL")
PLANNED = sql("sent_at IS NULL")
PENDING = sql("status = 'pending'")


class EmailDigest(Base):
    __tablename__ = "email_digests"
    __table_args__ = (
        Index("uq_email_digests_sent", "user_id", "local_date", unique=True, postgresql_where=SENT),
        Index("uq_email_digests_planned", "user_id", unique=True, postgresql_where=PLANNED),
        Index("ix_email_digests_user_id_planned_at", "user_id", "planned_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The local date of `planned_at` (of the send, once sent): one sent digest per date.
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    # The letter: set when it is sent.
    to_email: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    # From Clock.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    plan_reason: Mapped[str] = mapped_column(PLAN_REASON, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The last failed send (cleared by a successful one).
    error: Mapped[str | None] = mapped_column(Text)


class EmailOutbox(Base):
    __tablename__ = "email_outbox"
    __table_args__ = (Index("ix_email_outbox_pending", "user_id", postgresql_where=PENDING),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # From Clock: when the recommendation was opened.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(OUTBOX_STATUS, nullable=False)
    # The digest that took it (status sent); a skipped entry has none.
    digest_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("email_digests.id", ondelete="SET NULL")
    )
