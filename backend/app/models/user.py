"""users and user_timezones (SPEC §7.1, F1, F5)."""

import uuid
from datetime import datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Quiet hours prefilled for new users; switched off until the user enables them (ADR-026).
DEFAULT_QUIET_START = time(22, 0)
DEFAULT_QUIET_END = time(8, 0)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # The login. citext: unique regardless of letter case.
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # Address for digests; defaults to the login, NULL means "do not send" (SPEC F10).
    notify_email: Mapped[str | None] = mapped_column(Text)
    quiet_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    quiet_start: Mapped[time] = mapped_column(
        Time, nullable=False, default=DEFAULT_QUIET_START, server_default=text("'22:00'")
    )
    quiet_end: Mapped[time] = mapped_column(
        Time, nullable=False, default=DEFAULT_QUIET_END, server_default=text("'08:00'")
    )
    # Set from Clock (not the database now()), so the dev offset applies.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserTimezone(Base):
    """History of the user's time zones: `tz` is in effect from `valid_from` on."""

    __tablename__ = "user_timezones"
    __table_args__ = (UniqueConstraint("user_id", "valid_from"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tz: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
