"""Events for the open tabs of a user (SPEC F12): publish through Postgres NOTIFY on the channel
`user_events`, every api process LISTENs and hands them to the SSE streams of that user.

Step 5.1 interface stub: the bodies come with the feature commit.
"""

import uuid
from collections.abc import Iterable
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

CHANNEL = "user_events"
# Postgres refuses a NOTIFY payload of 8000 bytes or more.
MAX_PAYLOAD_BYTES = 7900
# application_name of the api's LISTEN connection (seen in pg_stat_activity).
LISTENER_APP_NAME = "ht-events"


async def publish(
    session: AsyncSession, user_id: uuid.UUID, type: str, data: dict[str, Any]
) -> None:
    """Send the event to the user's tabs when the session's transaction commits."""
    raise NotImplementedError("step 5.1")


async def publish_summary_updated(
    session: AsyncSession, user_id: uuid.UUID, dates: Iterable[date]
) -> None:
    """`summary.updated {dates}`, split into several events if one payload would be too big."""
    raise NotImplementedError("step 5.1")
