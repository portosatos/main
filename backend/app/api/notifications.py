"""Notification routes (SPEC F8, §6.3): the bell's feed and marking it read.

Only the session user's notifications are read or marked; an id of another user's is ignored as
a missing one. Marking tells the user's other tabs with `notifications.read` (ADR-043).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ClockDep, SessionDep
from app.auth.deps import CurrentUserDep
from app.models import Notification
from app.schemas.notifications import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    NotificationOut,
    NotificationsOut,
    NotificationsRead,
    UnreadOut,
)
from app.services import events

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


async def _unread(session: AsyncSession, user_id: uuid.UUID) -> int:
    query = select(func.count()).where(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    )
    return (await session.scalar(query)) or 0


@router.get("")
async def list_notifications(
    user: CurrentUserDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> NotificationsOut:
    """The newest notifications and the number of unread ones."""
    rows = await session.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id)
        .limit(limit)
    )
    items = [NotificationOut.model_validate(n, from_attributes=True) for n in rows]
    return NotificationsOut(items=items, unread=await _unread(session, user.id))


@router.post("/read")
async def mark_read(
    body: NotificationsRead, user: CurrentUserDep, session: SessionDep, clock: ClockDep
) -> UnreadOut:
    """Mark the given notifications (or all) read; the number of unread ones left."""
    query = update(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None)
    )
    if body.ids is not None:
        query = query.where(Notification.id.in_(body.ids))
    now = await clock.now()
    marked = set(await session.scalars(query.values(read_at=now).returning(Notification.id)))
    if marked:
        if body.ids is None:
            data: dict = {"all": True}
        else:
            data = {"ids": [str(i) for i in dict.fromkeys(body.ids) if i in marked]}
        await events.publish(session, user.id, "notifications.read", data)
        await session.commit()
    return UnreadOut(unread=await _unread(session, user.id))
