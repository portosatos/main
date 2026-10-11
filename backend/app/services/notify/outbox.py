"""The e-mail outbox (SPEC F10, §7.1): every newly opened recommendation waits here for a digest.

`enqueue` is called by the rule engine in the transaction that opens the recommendation, so
there is never one without the other.
"""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailOutbox


async def enqueue(
    session: AsyncSession, user_id: uuid.UUID, recommendation_id: uuid.UUID, now: datetime
) -> None:
    """A `pending` outbox entry of the opened recommendation, created at `now` (Clock)."""
    session.add(
        EmailOutbox(
            user_id=user_id, recommendation_id=recommendation_id, created_at=now, status="pending"
        )
    )
    await session.flush()
