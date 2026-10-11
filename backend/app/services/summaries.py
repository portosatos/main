"""daily_summaries: storing the day metrics and finding the dates to recompute (SPEC F3, F7).

A summary row is derived like the minute tables: `recompute_dates` computes the given local
dates from the minutes (services/metrics.py) and replaces their rows; a no_data date has no row.
`affected_dates` turns the minute ranges a batch touched into the local dates whose summary may
have changed; the ingest collects them and recomputes them at least every ~2 s and at the end
of the job. `rebuild_summaries` recomputes every date of a user (`htadmin rebuild`).
"""

import uuid
from collections.abc import Iterable
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.minutes import DirtyMinutes

# The ingest recomputes stale summaries at least this often, in seconds (SPEC F3).
FLUSH_INTERVAL_S = 2.0


async def affected_dates(
    session: AsyncSession, user_id: uuid.UUID, dirty: DirtyMinutes
) -> set[date]:
    """Local dates whose summary may change because the minutes of `dirty` changed."""
    raise NotImplementedError("step 4.3")


async def recompute_dates(
    session: AsyncSession, user_id: uuid.UUID, dates: Iterable[date], now: datetime
) -> None:
    """Compute the user's summaries of `dates` and replace their rows; `now` (from Clock)
    becomes `computed_at`."""
    raise NotImplementedError("step 4.3")


async def rebuild_summaries(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> int:
    """Drop the user's summaries and compute every date that has data; the number of rows."""
    raise NotImplementedError("step 4.3")
