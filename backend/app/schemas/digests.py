"""Schemas of /api/digests (SPEC F10, §6.3; ADR-050)."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# The digests GET returns by default and at most.
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class DigestOut(BaseModel):
    id: uuid.UUID
    status: Literal["planned", "sent"]
    local_date: date = Field(description="Local date of the planned time; of the send once sent")
    planned_at: datetime
    plan_reason: Literal["window", "max_delay", "daily_limit", "quiet_hours"]
    sent_at: datetime | None
    to_email: str | None = Field(description="Set when sent")
    subject: str | None = Field(description="Set when sent")
    recommendations: int = Field(description="Pending entries (planned) or entries in the letter")
    error: str | None = Field(description="The last failed send, retried by the next tick")


class DigestsOut(BaseModel):
    notify_email: str | None
    warning: Literal["no_notify_email"] | None = Field(
        description="no_notify_email: no address for digests, nothing is sent"
    )
    pending: int = Field(description="Opened recommendations waiting for a digest")
    items: list[DigestOut] = Field(
        description="The planned digest first, then the sent, newest first"
    )
