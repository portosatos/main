"""The digest planner (SPEC F10): services/notify/planner.py::plan_send and plan_send_time.

«Now» comes from a fixed Clock. Most cases are in Moscow (UTC+3 all year), so local times read
as they are written.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from app.clock import Clock
from app.services.localtime import TzHistory
from app.services.notify.planner import QuietHours, SendPlan, plan_send, plan_send_time

MSK = ZoneInfo("Europe/Moscow")
NY = ZoneInfo("America/New_York")  # UTC−4 in October 2026
TOKYO = ZoneInfo("Asia/Tokyo")  # UTC+9

QUIET_22_08 = QuietHours(enabled=True, start=time(22), end=time(8))
QUIET_OFF = QuietHours(enabled=False, start=time(22), end=time(8))


@dataclass(frozen=True)
class Zone:
    tz: str
    valid_from: datetime


MOSCOW = TzHistory([Zone("Europe/Moscow", datetime(2026, 1, 1, tzinfo=UTC))])


def at(zone: ZoneInfo, day: int, hour: int, minute: int = 0) -> datetime:
    """An instant given as local time on `day` of October 2026."""
    return datetime(2026, 10, day, hour, minute, tzinfo=zone)


def msk(day: int, hour: int, minute: int = 0) -> datetime:
    return at(MSK, day, hour, minute)


async def plan(
    pending: list[datetime],
    *,
    now: datetime | None = None,
    last: date | None = None,
    history: TzHistory = MOSCOW,
    quiet: QuietHours = QUIET_22_08,
) -> SendPlan:
    """plan_send with «now» from a fixed Clock; by default now is the last addition."""
    moment = now if now is not None else max(pending)
    clock_now = await Clock(app_env="test", system_now=lambda: moment).now()
    return plan_send(pending, last, history, quiet, clock_now)


async def test_three_recs_within_window_send_15_min_after_last() -> None:
    result = await plan([msk(11, 12, 5), msk(11, 12, 0), msk(11, 12, 10)])

    assert result == SendPlan(msk(11, 12, 25), "window")


async def test_recs_every_10_min_capped_60_min_after_first() -> None:
    every_10_min = [msk(11, 12, m) for m in range(0, 60, 10)]  # 12:00 … 12:50

    # Each addition moves the send by 15 minutes …
    assert await plan(every_10_min[:3]) == SendPlan(msk(11, 12, 35), "window")
    assert await plan(every_10_min[:5]) == SendPlan(msk(11, 12, 55), "window")
    # … but not past 60 minutes after the first one.
    assert await plan(every_10_min) == SendPlan(msk(11, 13, 0), "max_delay")


async def test_after_todays_digest_new_rec_goes_tomorrow() -> None:
    rec = [msk(11, 15, 0)]

    assert await plan(rec, last=date(2026, 10, 11), quiet=QUIET_OFF) == SendPlan(
        msk(12, 0, 0), "daily_limit"
    )
    # Yesterday's digest does not hold today's back.
    assert await plan(rec, last=date(2026, 10, 10), quiet=QUIET_OFF) == SendPlan(
        msk(11, 15, 15), "window"
    )


async def test_tomorrow_shift_hits_quiet_hours_sends_at_quiet_end() -> None:
    result = await plan([msk(11, 15, 0)], last=date(2026, 10, 11), quiet=QUIET_22_08)

    assert result == SendPlan(msk(12, 8, 0), "quiet_hours")


async def test_rec_in_quiet_hours_sends_at_quiet_end() -> None:
    # Before midnight: the end of the quiet hours is tomorrow.
    assert await plan([msk(11, 23, 30)]) == SendPlan(msk(12, 8, 0), "quiet_hours")
    # After midnight: the same morning.
    assert await plan([msk(12, 6, 0)]) == SendPlan(msk(12, 8, 0), "quiet_hours")
    # Added before the quiet hours, but the window ends inside them.
    assert await plan([msk(11, 21, 50)]) == SendPlan(msk(12, 8, 0), "quiet_hours")


async def test_quiet_hours_across_midnight() -> None:
    quiet = QuietHours(enabled=True, start=time(23), end=time(7))

    async def send_at(t: datetime) -> SendPlan:
        """The plan of one recommendation whose window ends exactly at `t`."""
        return await plan([t - timedelta(minutes=15)], quiet=quiet)

    assert await send_at(msk(11, 22, 59)) == SendPlan(msk(11, 22, 59), "window")
    assert await send_at(msk(11, 23, 0)) == SendPlan(msk(12, 7, 0), "quiet_hours")
    assert await send_at(msk(12, 0, 30)) == SendPlan(msk(12, 7, 0), "quiet_hours")
    assert await send_at(msk(12, 6, 59)) == SendPlan(msk(12, 7, 0), "quiet_hours")
    assert await send_at(msk(12, 7, 0)) == SendPlan(msk(12, 7, 0), "window")
    # Quiet hours inside one day do not wrap around midnight.
    daytime = QuietHours(enabled=True, start=time(13), end=time(14))
    assert await plan([msk(11, 13, 15)], quiet=daytime) == SendPlan(msk(11, 14, 0), "quiet_hours")
    assert await plan([msk(11, 23, 45)], quiet=daytime) == SendPlan(msk(12, 0, 0), "window")


# The user got a digest in Tokyo on 12.10 and flew to New York, where it is still 11.10.
TOKYO_THEN_NY = TzHistory(
    [
        Zone("Asia/Tokyo", datetime(2026, 9, 1, tzinfo=UTC)),
        Zone("America/New_York", at(NY, 11, 22, 0)),
    ]
)
TOKYO_DIGEST_DATE = date(2026, 10, 12)  # sent at 08:00 on 12.10 in Tokyo


async def test_daily_limit_rechecked_after_quiet_shift() -> None:
    # 23:30 on 11.10 in New York is quiet; their end, 08:00 on 12.10, falls on the date that
    # already has the Tokyo digest, so the digest waits for the next date and its quiet hours.
    result = await plan(
        [at(NY, 11, 23, 15)], last=TOKYO_DIGEST_DATE, history=TOKYO_THEN_NY, quiet=QUIET_22_08
    )

    assert result == SendPlan(at(NY, 13, 8, 0), "quiet_hours")


async def test_daily_limit_uses_local_date_after_tz_change() -> None:
    # The digest of 11.10 went out in New York; at 21:55 UTC the user moved to Moscow (00:55 12.10).
    ny_then_moscow = TzHistory(
        [
            Zone("America/New_York", datetime(2026, 9, 1, tzinfo=UTC)),
            Zone("Europe/Moscow", datetime(2026, 10, 11, 21, 55, tzinfo=UTC)),
        ]
    )
    sent_in_ny = date(2026, 10, 11)

    # Added in New York at 17:50 on 11.10, sent at 01:05 on 12.10 in Moscow: the date of the send
    # counts, and 12.10 has no digest yet.
    added_in_ny = datetime(2026, 10, 11, 21, 50, tzinfo=UTC)
    result = await plan(
        [added_in_ny],
        now=datetime(2026, 10, 11, 21, 56, tzinfo=UTC),
        last=sent_in_ny,
        history=ny_then_moscow,
        quiet=QUIET_OFF,
    )
    assert result == SendPlan(msk(12, 1, 5), "window")

    # In a zone where it is still 11.10 at the send time the digest waits for 00:00 on 12.10.
    still_11th = await plan([msk(11, 23, 0)], last=sent_in_ny, quiet=QUIET_OFF)
    assert still_11th == SendPlan(msk(12, 0, 0), "daily_limit")


async def test_quiet_disabled_ignored() -> None:
    assert await plan([msk(11, 23, 30)], quiet=QUIET_OFF) == SendPlan(msk(11, 23, 45), "window")


async def test_quiet_start_equals_end_treated_as_disabled() -> None:
    # Assumption (ADR-017): start == end means the quiet hours are off, not quiet all day.
    same = QuietHours(enabled=True, start=time(22), end=time(22))

    assert await plan([msk(11, 21, 50)], quiet=same) == SendPlan(msk(11, 22, 5), "window")
    assert await plan([msk(12, 3, 0)], quiet=same) == SendPlan(msk(12, 3, 15), "window")


@pytest.mark.parametrize(
    ("pending", "last", "quiet", "expected"),
    [
        ([msk(11, 12, 0)], None, QUIET_22_08, SendPlan(msk(11, 12, 15), "window")),
        (
            [msk(11, 12, 0), msk(11, 12, 50)],
            None,
            QUIET_22_08,
            SendPlan(msk(11, 13, 0), "max_delay"),
        ),
        ([msk(11, 12, 0)], date(2026, 10, 11), QUIET_OFF, SendPlan(msk(12, 0, 0), "daily_limit")),
        ([msk(11, 23, 0)], None, QUIET_22_08, SendPlan(msk(12, 8, 0), "quiet_hours")),
        # The cap set the time, then the quiet hours moved it: the last move is the reason.
        (
            [msk(11, 21, 0), msk(11, 21, 50)],
            None,
            QUIET_22_08,
            SendPlan(msk(12, 8, 0), "quiet_hours"),
        ),
    ],
    ids=["window", "max_delay", "daily_limit", "quiet_hours", "last_move_wins"],
)
async def test_plan_reason_reported(
    pending: list[datetime], last: date | None, quiet: QuietHours, expected: SendPlan
) -> None:
    assert await plan(pending, last=last, quiet=quiet) == expected


# Beyond the plan: decisions of step 9.1 (ADR-049).


async def test_local_date_going_back_after_move_west_still_limited() -> None:
    # ADR-049: a digest goes out only on a local date after the last digest's one. In New York
    # it is 11.10 again after the Tokyo digest of 12.10; 12.10 in New York is skipped as well,
    # so the dates of digests only grow (and UNIQUE(user_id, local_date) never fires).
    result = await plan(
        [at(NY, 11, 22, 30)], last=TOKYO_DIGEST_DATE, history=TOKYO_THEN_NY, quiet=QUIET_OFF
    )

    assert result == SendPlan(at(NY, 13, 0, 0), "daily_limit")


async def test_overdue_plan_moves_to_now_and_respects_quiet_hours() -> None:
    # ADR-049: a time already in the past becomes «now» (the worker was down), and the rules
    # apply to it: an overdue digest does not go out in the quiet hours.
    assert await plan([msk(11, 12, 0)], now=msk(11, 14, 0), quiet=QUIET_OFF) == SendPlan(
        msk(11, 14, 0), "window"
    )
    # Nothing moves it further: the reason stays the one of the window or the cap.
    capped = [msk(11, 12, 0), msk(11, 12, 50)]
    assert await plan(capped, now=msk(11, 14, 0), quiet=QUIET_OFF) == SendPlan(
        msk(11, 14, 0), "max_delay"
    )
    assert await plan([msk(11, 12, 0)], now=msk(11, 23, 0)) == SendPlan(
        msk(12, 8, 0), "quiet_hours"
    )


async def test_plan_send_time_returns_planned_time() -> None:
    # The signature of SPEC F10 returns only the time of plan_send.
    now = await Clock(app_env="test", system_now=lambda: msk(11, 15, 0)).now()
    args = ([msk(11, 15, 0)], date(2026, 10, 11), MOSCOW, QUIET_22_08, now)

    assert plan_send_time(*args) == msk(12, 8, 0)
    assert plan_send_time(*args) == plan_send(*args).at


# Regression tests after step 9.1 (a bug of _quiet_end in the nights the clocks change, found by
# the user): the plan is never before the window or the cap, never before now, and never inside
# the quiet hours, when the clocks go back and when they go forward.

NEW_YORK = TzHistory([Zone("America/New_York", datetime(2026, 1, 1, tzinfo=UTC))])


def utc(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


async def test_quiet_end_in_repeated_hour_after_clocks_go_back() -> None:
    # New York, Nov 1 2026: 02:00 EDT becomes 01:00 EST at 06:00 UTC, 01:00–02:00 happens twice.
    # The window gives 06:10 UTC = 01:10 EST (the second pass), in the quiet hours 22:00–01:30:
    # they end at 01:30 EST = 06:30 UTC, not at 01:30 EDT = 05:30 UTC of the first pass.
    quiet = QuietHours(enabled=True, start=time(22), end=time(1, 30))
    added = utc(11, 1, 5, 55)

    result = await plan([added], now=added, history=NEW_YORK, quiet=quiet)

    assert result == SendPlan(utc(11, 1, 6, 30), "quiet_hours")


async def test_quiet_end_in_first_pass_of_repeated_hour() -> None:
    # The same night, 01:10 EDT (the first pass): the quiet hours end at 01:30 EDT = 05:30 UTC.
    quiet = QuietHours(enabled=True, start=time(22), end=time(1, 30))
    added = utc(11, 1, 4, 55)

    result = await plan([added], now=added, history=NEW_YORK, quiet=quiet)

    assert result == SendPlan(utc(11, 1, 5, 30), "quiet_hours")


async def test_quiet_end_in_skipped_hour_after_clocks_go_forward() -> None:
    # New York, Mar 8 2026: 02:00 EST becomes 03:00 EDT at 07:00 UTC, 02:30 never happens.
    # The window gives 06:25 UTC = 01:25 EST, in the quiet hours 22:00–02:30: they end when the
    # clock jumps past 02:30, at 03:00 EDT = 07:00 UTC.
    quiet = QuietHours(enabled=True, start=time(22), end=time(2, 30))
    added = utc(3, 8, 6, 10)

    result = await plan([added], now=added, history=NEW_YORK, quiet=quiet)

    assert result == SendPlan(utc(3, 8, 7, 0), "quiet_hours")


@pytest.mark.xfail(strict=True, reason="step 9.2: not implemented")
async def test_skipped_hour_swallows_all_free_time_quiet_ends_next_day() -> None:
    # Found by the property test below: Santiago, Sep 6 2026, 00:00 −04 becomes 01:00 −03 at
    # 04:00 UTC. Quiet hours 00:15–00:00 leave only 00:00–00:15 free, and that night it is
    # skipped: from 23:44 on Sep 5 the quiet hours end at 00:00 on Sep 7 (03:00 UTC).
    santiago = TzHistory([Zone("America/Santiago", datetime(2026, 1, 1, tzinfo=UTC))])
    quiet = QuietHours(enabled=True, start=time(0, 15), end=time(0, 0))
    added = utc(9, 6, 3, 44)

    result = await plan([added], now=added, history=santiago, quiet=quiet)

    assert result == SendPlan(utc(9, 7, 3, 0), "quiet_hours")


# Zones whose clocks change in 2026: an hour back and forward (New York, London), half an hour
# (Lord Howe), at midnight (Santiago).
DST_ZONES = ["America/New_York", "Europe/London", "Australia/Lord_Howe", "America/Santiago"]


def clock_changes(tz: str) -> list[datetime]:
    """The instants of 2026 when the UTC offset of `tz` changes (to the minute)."""
    zone = ZoneInfo(tz)
    found, moment = [], datetime(2026, 1, 1, tzinfo=UTC)
    while moment.year == 2026:
        step = moment + timedelta(hours=1)
        if moment.astimezone(zone).utcoffset() != step.astimezone(zone).utcoffset():
            change = moment
            while change.astimezone(zone).utcoffset() == moment.astimezone(zone).utcoffset():
                change += timedelta(minutes=1)
            found.append(change)
        moment = step
    return found


CHANGES = [(tz, change) for tz in DST_ZONES for change in clock_changes(tz)]
QUARTERS = st.integers(min_value=0, max_value=24 * 4 - 1).map(lambda q: time(q // 4, q % 4 * 15))


def wall_near(change: datetime, tz: str, quarters: int) -> time:
    """The local wall time just before the clock change, moved by `quarters` of an hour."""
    before = (change - timedelta(minutes=1)).astimezone(ZoneInfo(tz))
    moved = datetime.combine(date(2026, 1, 1), time(before.hour)) + timedelta(minutes=15 * quarters)
    return moved.time()


def in_quiet(moment: datetime, history: TzHistory, quiet: QuietHours) -> bool:
    clock = moment.astimezone(history.zone_at(moment)).time()
    if not quiet.enabled or quiet.start == quiet.end:
        return False
    if quiet.start < quiet.end:
        return quiet.start <= clock < quiet.end
    return clock >= quiet.start or clock < quiet.end


@pytest.mark.xfail(strict=True, reason="step 9.2: not implemented")
@settings(max_examples=1000, deadline=None)
@given(
    case=st.sampled_from(CHANGES),
    first_min=st.integers(min_value=-4 * 60, max_value=4 * 60),
    gaps=st.lists(st.integers(min_value=0, max_value=20), max_size=4),
    late_min=st.integers(min_value=0, max_value=90),
    start=QUARTERS,
    end_quarters=st.none() | st.integers(min_value=-4, max_value=8),
    random_end=QUARTERS,
    last_days=st.none() | st.integers(min_value=-2, max_value=1),
)
# Found by this test: the skipped hour swallows all the free time of the night (Santiago).
@example(
    case=("America/Santiago", datetime(2026, 9, 6, 4, 0, tzinfo=UTC)),
    first_min=-16,
    gaps=[],
    late_min=0,
    start=time(0, 15),
    end_quarters=None,
    random_end=time(0, 0),
    last_days=None,
)
def test_plan_never_before_window_or_now_and_never_quiet(
    case: tuple[str, datetime],
    first_min: int,
    gaps: list[int],
    late_min: int,
    start: time,
    end_quarters: int | None,
    random_end: time,
    last_days: int | None,
) -> None:
    # Pending entries within 4 hours of a clock change; the end of the quiet hours either random
    # or near the local time of the change, where the repeated or skipped wall times are.
    tz, change = case
    history = TzHistory([Zone(tz, datetime(2025, 1, 1, tzinfo=UTC))])
    end = random_end if end_quarters is None else wall_near(change, tz, end_quarters)
    quiet = QuietHours(enabled=True, start=start, end=end)
    pending = [change + timedelta(minutes=first_min)]
    for gap in gaps:
        pending.append(pending[-1] + timedelta(minutes=gap))
    now = pending[-1] + timedelta(minutes=late_min)
    last = None if last_days is None else history.local_date(now) + timedelta(days=last_days)

    result = plan_send(pending, last, history, quiet, now)

    by_window = min(max(pending) + timedelta(minutes=15), min(pending) + timedelta(minutes=60))
    assert result.at >= by_window
    assert result.at >= now
    assert not in_quiet(result.at, history, quiet)
    if last is not None:
        assert history.local_date(result.at) > last
