"""Metrics of a user's local day from the merged minutes (SPEC F6, F7).

A minute belongs to the local date of its start (services/localtime.py). The day's minutes are
merged across devices (services/merge.py), then:
- `wear_minutes` — minutes covered by at least one device; `status` — no_data (0), partial (1–719),
  complete (720 and more);
- `steps` — the sum of the merged minutes; `active_minutes` — merged minutes with at least 100
  steps; both are None on a no_data day: no data is not zero;
- `resting_hr` — the 10th percentile of the minute pulse over minutes without steps, None if there
  are fewer than 60 such minutes; `peak_hr` — the maximum of the minute pulse. The pulse of a minute
  is the median of its points, so a single spike does not make the peak.

Sleep and storing the day in daily_summaries come in step 4.3.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

COMPLETE_WEAR_MINUTES = 12 * 60
ACTIVE_MINUTE_STEPS = 100
REST_MINUTES_MIN = 60
RESTING_PERCENTILE = 0.1


@dataclass(frozen=True, slots=True)
class DayMetrics:
    local_date: date
    status: str  # no_data | partial | complete
    wear_minutes: int
    steps: int | None
    active_minutes: int | None
    resting_hr: float | None
    peak_hr: float | None


async def day_metrics(session: AsyncSession, user_id: uuid.UUID, day: date) -> DayMetrics:
    """Metrics of the user's local date `day` from the minute tables and pulse points."""
    raise NotImplementedError("step 4.2")
