"""Sleep of a local day from the merged minutes (SPEC F5, F6, F7).

Pure functions over sets of minute starts (UTC):
- a session is a run of asleep minutes in which no gap without sleep is longer than 30 minutes;
  its length is the number of asleep minutes (gaps do not count); sessions under 30 minutes are
  ignored;
- a session belongs to the local date of its last asleep minute — the wake day;
- the day's `sleep_minutes` is the sum over its sessions, the main session is the longest one
  (on a tie the later one) and gives `sleep_start` and `sleep_end`; a day without sessions has
  no sleep data (None), not 0;
- `night_valid`: the main session exists and no data gap (minutes no device covers) longer than
  30 minutes falls into [start − 60 min, end + 60 min).
"""

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.services.localtime import TzHistory

MINUTE = timedelta(minutes=1)
GAP_MAX_MINUTES = 30
SESSION_MIN_MINUTES = 30
NIGHT_WINDOW = timedelta(minutes=60)
DATA_GAP_MAX_MINUTES = 30


@dataclass(frozen=True, slots=True)
class SleepSession:
    start: datetime  # the first asleep minute
    end: datetime  # the end of the last asleep minute
    minutes: int  # asleep minutes; gaps inside the session do not count


@dataclass(frozen=True, slots=True)
class DaySleep:
    sleep_minutes: int | None
    sleep_start: datetime | None
    sleep_end: datetime | None
    night_valid: bool


NO_SLEEP = DaySleep(None, None, None, False)


def sleep_sessions(asleep: Iterable[datetime]) -> list[SleepSession]:
    """Every session of the asleep minutes, whatever its length, in time order."""
    raise NotImplementedError("step 4.3")


def night_valid(session: SleepSession, covered: Collection[datetime]) -> bool:
    """No run of uncovered minutes longer than 30 inside [start − 60 min, end + 60 min)."""
    raise NotImplementedError("step 4.3")


def summarize_sleep(
    day: date, history: TzHistory, asleep: Collection[datetime], covered: Collection[datetime]
) -> DaySleep:
    """Sleep of the local date `day` from the merged asleep minutes and the covered minutes
    (by any device) around it."""
    raise NotImplementedError("step 4.3")
