"""Sleep of a local day from the merged minutes (SPEC F5, F6, F7).

Pure functions over sets of minute starts (UTC):
- a session is a run of asleep minutes in which no gap without sleep is longer than 30 minutes;
  its length is the number of asleep minutes (gaps do not count); sessions under 30 minutes are
  ignored;
- a session belongs to the local date of its last asleep minute — the wake day; a session with
  no data after its end (from any device: the edge of the user's data) is unfinished and belongs
  to no day until its continuation or later data come (SPEC F5, ADR-046);
- the day's `sleep_minutes` is the sum over its sessions, the main session is the longest one
  (on a tie the later one) and gives `sleep_start` and `sleep_end`; a day without sessions has
  no sleep data (None), not 0;
- `night_valid`: the main session exists and no data gap (minutes no device covers) longer than
  30 minutes falls into [start − 60 min, end + 60 min); a gap at the edge counts only inside the
  window (SPEC F6, ADR-035).
"""

from collections.abc import Iterable
from collections.abc import Set as AbstractSet
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
    joined = (GAP_MAX_MINUTES + 1) * MINUTE  # the next asleep minute after a gap of 30 minutes
    sessions: list[SleepSession] = []
    start = last = None
    count = 0
    for minute in sorted(asleep):
        if last is not None and minute - last <= joined:
            count += 1
        else:
            if start is not None and last is not None:
                sessions.append(SleepSession(start, last + MINUTE, count))
            start, count = minute, 1
        last = minute
    if start is not None and last is not None:
        sessions.append(SleepSession(start, last + MINUTE, count))
    return sessions


def night_valid(session: SleepSession, covered: AbstractSet[datetime]) -> bool:
    """No run of uncovered minutes longer than 30 inside [start − 60 min, end + 60 min)."""
    minute, end = session.start - NIGHT_WINDOW, session.end + NIGHT_WINDOW
    run = 0
    while minute < end:
        run = 0 if minute in covered else run + 1
        if run > DATA_GAP_MAX_MINUTES:
            return False
        minute += MINUTE
    return True


def summarize_sleep(
    day: date,
    history: TzHistory,
    asleep: Iterable[datetime],
    covered: AbstractSet[datetime],
    data_end: datetime | None = None,
) -> DaySleep:
    """Sleep of the local date `day` from the merged asleep minutes and the covered minutes
    (by any device) around it. `data_end` — the end of the last minute any device of the user
    covers; by default the end of the last minute of `covered`."""
    if data_end is None and covered:
        data_end = max(covered) + MINUTE
    sessions = [
        s
        for s in sleep_sessions(asleep)
        if s.minutes >= SESSION_MIN_MINUTES
        and (data_end is None or s.end < data_end)  # else unfinished: the data end with it
        and history.local_date(s.end - MINUTE) == day
    ]
    if not sessions:
        return NO_SLEEP
    main = max(sessions, key=lambda s: (s.minutes, s.end))
    return DaySleep(
        sleep_minutes=sum(s.minutes for s in sessions),
        sleep_start=main.start,
        sleep_end=main.end,
        night_valid=night_valid(main, covered),
    )
