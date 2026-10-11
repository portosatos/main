"""Sleep sessions, the wake day and night validity (SPEC F4.4, F5, F6): services/sleep.py.

The input is minutes after the device merge: the asleep minutes and the minutes some device
covers. The user lives in Europe/Moscow (+03:00).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from app.services.localtime import TzHistory
from app.services.merge import device_order, merge_sleep
from app.services.sleep import NO_SLEEP, DaySleep, SleepSession, sleep_sessions, summarize_sleep

pytestmark = pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="step 4.3: not implemented"
)

MSK = timezone(timedelta(hours=3))
MINUTE = timedelta(minutes=1)
D = date(2026, 10, 5)
EVE = D - timedelta(days=1)


@dataclass(frozen=True)
class Tz:
    tz: str
    valid_from: datetime


HISTORY = TzHistory([Tz("Europe/Moscow", datetime(2026, 1, 1, tzinfo=UTC))])


@dataclass(frozen=True)
class Dev:
    id: uuid.UUID
    kind: str
    external_id: str
    created_at: datetime


def at(hour: int, minute: int = 0, day: date = D) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=MSK)


def span(start: datetime, end: datetime) -> set[datetime]:
    """Minute starts (UTC) of [start, end)."""
    count = (end - start) // MINUTE
    return {(start + i * MINUTE).astimezone(UTC) for i in range(count)}


WHOLE_TIME = span(at(0, day=D - timedelta(days=3)), at(0, day=D + timedelta(days=3)))


def test_sleep_2340_0710_attributed_to_wake_day() -> None:
    # SPEC F5, §8 stage 4, §9 #17: sleep 23:40–07:10 belongs to the day of waking up.
    asleep = span(at(23, 40, EVE), at(7, 10))
    covered = span(at(22, 0, EVE), at(9, 0))

    assert summarize_sleep(D, HISTORY, asleep, covered) == DaySleep(
        sleep_minutes=450, sleep_start=at(23, 40, EVE), sleep_end=at(7, 10), night_valid=True
    )
    assert summarize_sleep(EVE, HISTORY, asleep, covered) == NO_SLEEP
    assert summarize_sleep(D + timedelta(days=1), HISTORY, asleep, covered) == NO_SLEEP


@pytest.mark.parametrize(
    ("gap", "sessions"),
    [
        (30, [SleepSession(at(1), at(3, 30), 120)]),
        (31, [SleepSession(at(1), at(2), 60), SleepSession(at(2, 31), at(3, 31), 60)]),
    ],
)
def test_gap_le_30_min_merged_gt_30_split(gap: int, sessions: list[SleepSession]) -> None:
    # SPEC F5: a session is asleep minutes with gaps of at most 30 minutes; the gap does not
    # count as sleep.
    second = at(2) + gap * MINUTE
    asleep = span(at(1), at(2)) | span(second, second + 60 * MINUTE)

    assert sleep_sessions(asleep) == sessions


@pytest.mark.parametrize(("nap", "total"), [(29, 420), (30, 450)])
def test_session_under_30_min_ignored(nap: int, total: int) -> None:
    # SPEC F5 (assumption): sessions from 30 minutes count. Night 23:00–06:00 (420) and a nap.
    asleep = span(at(23, 0, EVE), at(6)) | span(at(14), at(14) + nap * MINUTE)

    day = summarize_sleep(D, HISTORY, asleep, WHOLE_TIME)

    assert day.sleep_minutes == total
    assert (day.sleep_start, day.sleep_end) == (at(23, 0, EVE), at(6))
    alone = summarize_sleep(D, HISTORY, span(at(14), at(14) + nap * MINUTE), WHOLE_TIME)
    assert alone.sleep_minutes == (None if nap < 30 else 30)


def test_main_session_is_longest() -> None:
    # SPEC F5, F7: the day's sleep is all its sessions, start and end are the main session's.
    night_and_nap = span(at(23, 0, EVE), at(6)) | span(at(13), at(14, 30))
    assert summarize_sleep(D, HISTORY, night_and_nap, WHOLE_TIME) == DaySleep(
        sleep_minutes=510, sleep_start=at(23, 0, EVE), sleep_end=at(6), night_valid=True
    )
    # A nap longer than a broken night is the main session.
    short_night_long_nap = span(at(3), at(4)) | span(at(13), at(15))
    day = summarize_sleep(D, HISTORY, short_night_long_nap, WHOLE_TIME)
    assert (day.sleep_minutes, day.sleep_start, day.sleep_end) == (180, at(13), at(15))
    # Assumption: on a tie the later session is the main one.
    tie = span(at(1), at(2)) | span(at(5), at(6))
    day = summarize_sleep(D, HISTORY, tie, WHOLE_TIME)
    assert (day.sleep_start, day.sleep_end) == (at(5), at(6))


NIGHT = span(at(23, 0, EVE), at(7))
HOLE_30 = span(at(2), at(2, 30))
HOLE_31 = span(at(2), at(2, 31))


@pytest.mark.parametrize(
    ("asleep", "covered", "valid"),
    [
        (NIGHT, span(at(22, 0, EVE), at(8)), True),
        # the windows of 60 minutes around the session may have data gaps of up to 30 minutes
        (NIGHT, span(at(22, 30, EVE), at(8)), True),
        (NIGHT, span(at(22, 31, EVE), at(8)), False),
        (NIGHT, span(at(22, 0, EVE), at(7, 30)), True),
        (NIGHT, span(at(22, 0, EVE), at(7, 29)), False),
        # no data before the session: the watch may have been put on asleep
        (NIGHT, span(at(23, 0, EVE), at(8)), False),
        # no data after the session: the watch may have been taken off asleep
        (NIGHT, span(at(22, 0, EVE), at(7)), False),
        # the watch is off for 30 minutes at 02:00: one session, 450 minutes, valid
        (NIGHT - HOLE_30, span(at(22, 0, EVE), at(8)) - HOLE_30, True),
        # off for 31 minutes: the night splits, the main session 02:31–07:00 is next to the hole
        (NIGHT - HOLE_31, span(at(22, 0, EVE), at(8)) - HOLE_31, False),
    ],
    ids=[
        "data-all-around",
        "data-from-22:30",
        "data-from-22:31",
        "data-to-07:30",
        "data-to-07:29",
        "nothing-before",
        "nothing-after",
        "hole-30-inside",
        "hole-31-inside",
    ],
)
def test_night_valid_requires_data_60_min_around_and_no_inner_gap_over_30(
    asleep: set[datetime], covered: set[datetime], valid: bool
) -> None:
    # SPEC F6 (assumption, refined): the main session exists and [start − 60 min, end + 60 min)
    # has no data gap longer than 30 minutes.
    assert summarize_sleep(D, HISTORY, asleep, covered).night_valid is valid


def test_watch_removed_mid_night_makes_night_invalid() -> None:
    # SPEC F6: the watch taken off at 03:00 does not turn into a 4-hour "short sleep".
    # The watch: on from 21:00, asleep 23:00–03:00, back on at 09:00. The phone: steps in the
    # evening and from 07:20, nothing at night.
    registered = datetime(2026, 9, 1, tzinfo=UTC)
    watch = Dev(uuid.uuid4(), "watch", "watch-1", registered)
    phone = Dev(uuid.uuid4(), "phone", "phone-1", registered)
    order = device_order([phone, watch])
    coverage = {
        watch.id: span(at(21, 0, EVE), at(3)) | span(at(9), at(12)),
        phone.id: span(at(18, 0, EVE), at(22, 30, EVE)) | span(at(7, 20), at(12)),
    }
    sleep = {watch.id: span(at(23, 0, EVE), at(3)), phone.id: set()}

    merged = merge_sleep(order, coverage, sleep)
    asleep = {m for m, s in merged.items() if s.value}

    assert summarize_sleep(D, HISTORY, asleep, set(merged)) == DaySleep(
        sleep_minutes=240, sleep_start=at(23, 0, EVE), sleep_end=at(3), night_valid=False
    )

    # The phone slept too (23:10–07:20): after 03:00 its sleep fills in, the night is whole.
    coverage[phone.id] |= span(at(23, 10, EVE), at(7, 20))
    sleep[phone.id] = span(at(23, 10, EVE), at(7, 20))

    merged = merge_sleep(order, coverage, sleep)
    asleep = {m for m, s in merged.items() if s.value}

    assert merged[at(2, 59).astimezone(UTC)].source_device_id == watch.id
    assert merged[at(3).astimezone(UTC)].source_device_id == phone.id
    assert summarize_sleep(D, HISTORY, asleep, set(merged)) == DaySleep(
        sleep_minutes=500, sleep_start=at(23, 0, EVE), sleep_end=at(7, 20), night_valid=True
    )
