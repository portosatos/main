"""The time zone history of a user (SPEC F5, F11; ADR-051): its entries, and the job `tz_changed`
that recomputes what a move changed.

A move adds an entry: its zone is in effect from `valid_from` until the next entry, or from then on
for the last one. A move in the past never removes the later entries, and changes nothing before
its `valid_from` (ADR-051). The first entry also covers the time before it (ADR-033), so a move
earlier than the whole history would take that time too: the zone it had is kept in an entry from
HISTORY_START, shown as «с начала» (`valid_from` null in the api). The api queues `tz_changed` with
the range the move changed, [valid_from, valid_to); valid_to is the next entry's `valid_from`.

The worker recomputes the dates of the range by the new history, and the existing summaries the
old history could have dated there: a local date is at most 12 hours behind UTC and 14 ahead, so
they are among the rows of [(valid_from − 12 h).date(), (valid_to + 14 h).date()]. The old
history itself is not needed — so jobs of quick successive moves cover each other whatever order
they run in. The range is cut to the user's data: dates without data have no rows. Then the rules
are evaluated: the days, and today, may have moved (SPEC F9).
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CoverageMinute, DailySummary, Device, UserTimezone
from app.services.events import publish_summary_updated
from app.services.localtime import load_tz_history
from app.services.rules.engine import evaluate_user
from app.services.sleep import MINUTE
from app.services.summaries import recompute_dates

# Kind of the queue job that recomputes after a move.
TZ_CHANGED = "tz_changed"
# How far a local date may be from the UTC date: Etc/GMT+12 is 12 hours behind, Kiritimati 14 ahead.
MAX_BEHIND = timedelta(hours=12)
MAX_AHEAD = timedelta(hours=14)
# The start of the history: the entry from then on is in effect since always. A move must be later.
HISTORY_START = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class Entry:
    tz: str
    # None: in effect since always (HISTORY_START).
    valid_from: datetime | None
    # The next entry's valid_from; None for the last one.
    valid_to: datetime | None
    # In effect at `now`.
    current: bool


def entries(records: Sequence[UserTimezone], now: datetime) -> list[Entry]:
    """The history, newest first. The entry in effect at `now` is the last one that started by
    then; the first entry also covers the time before it (services/localtime.py)."""
    ordered = sorted(records, key=lambda r: r.valid_from)
    started = [i for i, r in enumerate(ordered) if r.valid_from <= now]
    current = started[-1] if started else 0
    found = [
        Entry(
            r.tz,
            None if r.valid_from <= HISTORY_START else r.valid_from,
            ordered[i + 1].valid_from if i + 1 < len(ordered) else None,
            i == current,
        )
        for i, r in enumerate(ordered)
    ]
    return found[::-1]


def job_payload(valid_from: datetime, valid_to: datetime | None) -> dict[str, Any]:
    return {
        "valid_from": valid_from.isoformat(),
        "valid_to": None if valid_to is None else valid_to.isoformat(),
    }


async def changed_dates(
    session: AsyncSession, user_id: uuid.UUID, valid_from: datetime, valid_to: datetime | None
) -> set[date]:
    """The local dates whose summary a move over [valid_from, valid_to) may change."""
    first, last = (
        await session.execute(
            select(func.min(CoverageMinute.minute_utc), func.max(CoverageMinute.minute_utc))
            .join(Device, Device.id == CoverageMinute.device_id)
            .where(Device.user_id == user_id)
        )
    ).one()
    if first is None:
        return set()
    start = max(valid_from, first)
    stop = last + MINUTE if valid_to is None else min(valid_to, last + MINUTE)
    if start >= stop:
        return set()
    history = await load_tz_history(session, user_id)
    dates = history.dates_between(start, stop)
    before = await session.scalars(
        select(DailySummary.local_date).where(
            DailySummary.user_id == user_id,
            DailySummary.local_date.between(
                (start - MAX_BEHIND).date(),
                (stop - timedelta(microseconds=1) + MAX_AHEAD).date(),
            ),
        )
    )
    return dates | set(before)


async def apply_tz_change(
    session: AsyncSession, user_id: uuid.UUID, payload: dict[str, Any], now: datetime
) -> set[date]:
    """The job `tz_changed`: recompute the changed dates, tell the tabs, evaluate the rules; in
    the caller's transaction (the worker's, under the user lock). The dates recomputed."""
    valid_from = datetime.fromisoformat(payload["valid_from"])
    valid_to = payload.get("valid_to")
    dates = await changed_dates(
        session, user_id, valid_from, None if valid_to is None else datetime.fromisoformat(valid_to)
    )
    await recompute_dates(session, user_id, dates, now)
    if dates:
        await publish_summary_updated(session, user_id, dates)
    await evaluate_user(session, user_id, now)
    return dates
