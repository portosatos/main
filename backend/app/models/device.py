"""devices: the user's watches and phones, created on first sight in the data (SPEC F2)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

DEVICE_KIND = Enum("watch", "phone", name="device_kind")


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("user_id", "external_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The id from the data ("watch-1"): unique per user, not globally.
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(DEVICE_KIND, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # From Clock. Among devices of one kind the earlier registered one wins the merge (SPEC F4.4).
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
