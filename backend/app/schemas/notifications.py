"""Schemas of /api/notifications (SPEC F8, §6.3; ADR-043)."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field

# The newest notifications GET returns by default and at most.
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
# Ids one POST /read may name: keeps the notifications.read event under the NOTIFY limit.
MAX_READ_IDS = 100


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str = Field(examples=["goal.achieved"])
    payload: dict[str, Any]
    created_at: datetime
    read_at: datetime | None


class NotificationsOut(BaseModel):
    items: list[NotificationOut] = Field(description="Newest first")
    unread: int = Field(description="All unread notifications of the user")


class NotificationsRead(BaseModel):
    """The ids to mark read; null or missing: all of the user's notifications."""

    ids: Annotated[list[uuid.UUID], Field(max_length=MAX_READ_IDS)] | None = None


class UnreadOut(BaseModel):
    unread: int
