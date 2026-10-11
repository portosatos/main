"""The digest planner (SPEC F10): services/notify/planner.py::plan_send and plan_send_time.

«Now» comes from a fixed Clock. Most cases are in Moscow (UTC+3 all year), so local times read
as they are written.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

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
