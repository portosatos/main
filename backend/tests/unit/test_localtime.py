"""Local dates by the time zone history (SPEC F5, ADR-009): services/localtime.py."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from itertools import pairwise
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.localtime import TzHistory, UtcRange

NOT_IMPLEMENTED = pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="step 4.1: not implemented"
)

MSK = "Europe/Moscow"  # +03:00, no DST
NYC = "America/New_York"  # -04:00 in October 2026 (EDT), DST ends 2026-11-01
REGISTERED = datetime(2026, 9, 1, tzinfo=UTC)
TICK = timedelta(microseconds=1)

# Zones for the property tests: DST at 02:00/03:00 and at midnight (Santiago, Havana, Beirut),
# half-hour DST (Lord Howe), :45 offsets (Kathmandu, Chatham), ±14 h (Kiritimati, Honolulu).
ZONES = [
    "UTC",
    MSK,
    NYC,
    "Europe/Berlin",
    "America/Santiago",
    "America/Havana",
    "Asia/Beirut",
    "Australia/Lord_Howe",
    "Asia/Kathmandu",
    "Pacific/Chatham",
    "America/St_Johns",
    "Pacific/Kiritimati",
    "Pacific/Honolulu",
]
# DST transitions of these zones in 2026; the generated windows start two days before one of them.
TRANSITIONS = [
    date(2026, 3, 8),  # US, Havana
    date(2026, 3, 29),  # EU, Beirut
    date(2026, 4, 5),  # Santiago, Lord Howe, Chatham
    date(2026, 9, 6),  # Santiago
    date(2026, 9, 27),  # Chatham
    date(2026, 10, 4),  # Lord Howe
    date(2026, 10, 25),  # EU, Beirut
    date(2026, 11, 1),  # US, Havana
]
SPAN_S = 5 * 24 * 3600  # history records and windows fall within 5 days


@dataclass(frozen=True)
class Rec:
    tz: str
    valid_from: datetime


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def history(first_tz: str, *moves: tuple[datetime, str]) -> TzHistory:
    """`first_tz` from REGISTERED, then each (moment, tz) of `moves`."""
    return TzHistory([Rec(first_tz, REGISTERED), *(Rec(tz, at) for at, tz in moves)])


def hours(ranges: list[UtcRange]) -> float:
    return sum((end - start for start, end in ranges), timedelta()) / timedelta(hours=1)


def assert_sorted_not_touching(ranges: list[UtcRange]) -> None:
    for start, end in ranges:
        assert start.utcoffset() == timedelta(0)
        assert start < end
    for (_, end), (next_start, _) in pairwise(ranges):
        assert end < next_start


@st.composite
def histories(draw: st.DrawFn) -> tuple[list[Rec], datetime]:
    """1–4 records with unique second-precision `valid_from` around a DST transition; the base."""
    day = draw(st.sampled_from(TRANSITIONS))
    base = datetime(day.year, day.month, day.day, tzinfo=UTC) - timedelta(days=2)
    raw = draw(
        st.lists(
            st.tuples(st.sampled_from(ZONES), st.integers(0, SPAN_S)),
            min_size=1,
            max_size=4,
            unique_by=lambda r: r[1],
        )
    )
    return [Rec(tz, base + timedelta(seconds=s)) for tz, s in raw], base


@NOT_IMPLEMENTED
def test_local_date_uses_tz_active_at_event() -> None:
    move = utc(2026, 10, 5, 22)  # 01:00 Oct 6 in Moscow = 18:00 Oct 5 in New York
    h = history(MSK, (move, NYC))

    # Moscow before the move: 01:00 Oct 5 (in New York it would still be Oct 4).
    assert h.local_date(utc(2026, 10, 4, 22)) == date(2026, 10, 5)
    assert h.zone_at(move - TICK) == ZoneInfo(MSK)
    assert h.local_date(move - TICK) == date(2026, 10, 6)
    # From the move on, New York: the clock goes back to Oct 5.
    assert h.zone_at(move) == ZoneInfo(NYC)
    assert h.local_date(move) == date(2026, 10, 5)
    assert h.local_date(utc(2026, 10, 6, 2)) == date(2026, 10, 5)  # 22:00 in NY, 05:00 Oct 6 in MSK
    # The offset the instant is written with does not matter, only the instant.
    plus_five = timezone(timedelta(hours=5))
    assert h.local_date(utc(2026, 10, 6, 2).astimezone(plus_five)) == date(2026, 10, 5)


@NOT_IMPLEMENTED
def test_msk_to_nyc_move_day_is_31h() -> None:
    h = history(MSK, (utc(2026, 10, 5, 12), NYC))  # 15:00 in Moscow = 08:00 in New York

    # Oct 5 starts at midnight in Moscow and ends at midnight in New York: one 31-hour piece.
    assert h.ranges_for_date(date(2026, 10, 5)) == [(utc(2026, 10, 4, 21), utc(2026, 10, 6, 4))]
    assert hours(h.ranges_for_date(date(2026, 10, 5))) == 31
    assert h.ranges_for_date(date(2026, 10, 4)) == [(utc(2026, 10, 3, 21), utc(2026, 10, 4, 21))]
    assert h.ranges_for_date(date(2026, 10, 6)) == [(utc(2026, 10, 6, 4), utc(2026, 10, 7, 4))]


@NOT_IMPLEMENTED
def test_westward_move_after_midnight_splits_day_into_two_ranges() -> None:
    # 02:00 Oct 6 in Moscow = 19:00 Oct 5 in New York: the move takes the clock back over midnight.
    h = history(MSK, (utc(2026, 10, 5, 23), NYC))

    oct5 = h.ranges_for_date(date(2026, 10, 5))
    oct6 = h.ranges_for_date(date(2026, 10, 6))
    assert oct5 == [
        (utc(2026, 10, 4, 21), utc(2026, 10, 5, 21)),  # Moscow, whole day
        (utc(2026, 10, 5, 23), utc(2026, 10, 6, 4)),  # New York, 19:00–24:00
    ]
    assert oct6 == [
        (utc(2026, 10, 5, 21), utc(2026, 10, 5, 23)),  # Moscow, 00:00–02:00
        (utc(2026, 10, 6, 4), utc(2026, 10, 7, 4)),  # New York, whole day
    ]
    assert (hours(oct5), hours(oct6)) == (29, 26)
    # Together they cover Oct 4 21:00Z – Oct 7 04:00Z exactly once.
    assert hours(oct5) + hours(oct6) == (utc(2026, 10, 7, 4) - utc(2026, 10, 4, 21)) / timedelta(
        hours=1
    )


@NOT_IMPLEMENTED
def test_eastward_move_short_day() -> None:
    h = history(NYC, (utc(2026, 10, 5, 12), MSK))  # 08:00 in New York = 15:00 in Moscow

    # Oct 5 starts at midnight in New York and ends at midnight in Moscow: 17 hours.
    assert h.ranges_for_date(date(2026, 10, 5)) == [(utc(2026, 10, 5, 4), utc(2026, 10, 5, 21))]
    assert hours(h.ranges_for_date(date(2026, 10, 5))) == 17
    assert h.ranges_for_date(date(2026, 10, 4)) == [(utc(2026, 10, 4, 4), utc(2026, 10, 5, 4))]
    assert h.ranges_for_date(date(2026, 10, 6)) == [(utc(2026, 10, 5, 21), utc(2026, 10, 6, 21))]


@NOT_IMPLEMENTED
@settings(deadline=None)
@given(
    data=histories(),
    start_min=st.integers(0, SPAN_S // 60),
    length_min=st.integers(1, 3 * 24 * 60),
)
def test_every_minute_maps_to_exactly_one_date(
    data: tuple[list[Rec], datetime], start_min: int, length_min: int
) -> None:
    records, base = data
    h = TzHistory(records)
    start = base + timedelta(minutes=start_min)
    end = start + timedelta(minutes=length_min)
    minutes = [start + timedelta(minutes=i) for i in range(length_min)]
    dates = {h.local_date(m) for m in minutes}

    # The pieces of all nearby dates, clipped to the window, tile it: no gaps, no overlaps.
    first, last = min(dates) - timedelta(days=2), max(dates) + timedelta(days=2)
    pieces: list[tuple[datetime, datetime, date]] = []
    day = first
    while day <= last:
        ranges = h.ranges_for_date(day)
        assert_sorted_not_touching(ranges)
        for r_start, r_end in ranges:
            if r_start < end and r_end > start:
                pieces.append((max(r_start, start), min(r_end, end), day))
        day += timedelta(days=1)
    pieces.sort()
    assert pieces[0][0] == start
    assert pieces[-1][1] == end
    for (_, p_end, _), (next_start, _, _) in pairwise(pieces):
        assert p_end == next_start

    # Each minute lies in exactly one piece, and that piece's date is the minute's local date.
    i = 0
    for m in minutes:
        while pieces[i][1] <= m:
            i += 1
        assert pieces[i][0] <= m
        assert pieces[i][2] == h.local_date(m), m


@NOT_IMPLEMENTED
def test_dst_transition_23h_and_25h_days() -> None:
    berlin = TzHistory([Rec("Europe/Berlin", utc(2026, 1, 1))])
    assert berlin.ranges_for_date(date(2026, 3, 29)) == [
        (utc(2026, 3, 28, 23), utc(2026, 3, 29, 22))
    ]
    assert hours(berlin.ranges_for_date(date(2026, 3, 29))) == 23
    assert hours(berlin.ranges_for_date(date(2026, 3, 28))) == 24
    assert berlin.ranges_for_date(date(2026, 10, 25)) == [
        (utc(2026, 10, 24, 22), utc(2026, 10, 25, 23))
    ]
    assert hours(berlin.ranges_for_date(date(2026, 10, 25))) == 25

    # Santiago changes the clock at midnight: 00:00 Sep 6 does not exist, the day starts at 01:00.
    santiago = TzHistory([Rec("America/Santiago", utc(2026, 1, 1))])
    assert santiago.ranges_for_date(date(2026, 9, 6)) == [(utc(2026, 9, 6, 4), utc(2026, 9, 7, 3))]
    assert hours(santiago.ranges_for_date(date(2026, 9, 6))) == 23
    assert hours(santiago.ranges_for_date(date(2026, 4, 4))) == 25  # 23:00–24:00 Apr 4 twice


@NOT_IMPLEMENTED
@settings(deadline=None, max_examples=300)
@given(data=histories(), offset_s=st.integers(0, SPAN_S))
def test_ranges_for_date_roundtrip(data: tuple[list[Rec], datetime], offset_s: int) -> None:
    records, base = data
    h = TzHistory(records)
    ts = base + timedelta(seconds=offset_s)
    day = h.local_date(ts)

    ranges = h.ranges_for_date(day)

    assert_sorted_not_touching(ranges)
    assert sum(start <= ts < end for start, end in ranges) == 1
    for start, end in ranges:
        # Every range is all `day` and cannot be widened: the instants just outside are other dates.
        assert h.local_date(start) == day
        assert h.local_date(end - TICK) == day
        assert h.local_date(start - TICK) != day
        assert h.local_date(end) != day


@NOT_IMPLEMENTED
def test_before_first_record_first_tz_applies() -> None:
    """Допущение: data from before registration (the first record) is dated in the first zone."""
    h = history(MSK)

    assert h.zone_at(REGISTERED - timedelta(days=90)) == ZoneInfo(MSK)
    assert h.local_date(utc(2026, 6, 1, 22)) == date(2026, 6, 2)  # 01:00 Jun 2 in Moscow
    assert h.ranges_for_date(date(2026, 6, 2)) == [(utc(2026, 6, 1, 21), utc(2026, 6, 2, 21))]
    # The registration day is an ordinary day.
    assert h.ranges_for_date(date(2026, 9, 1)) == [(utc(2026, 8, 31, 21), utc(2026, 9, 1, 21))]


@NOT_IMPLEMENTED
def test_records_order_and_validation() -> None:
    records = [Rec(MSK, REGISTERED), Rec(NYC, utc(2026, 10, 5, 12)), Rec(MSK, utc(2026, 10, 20))]
    forward, backward = TzHistory(records), TzHistory(reversed(records))
    for day in (date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 20)):
        assert forward.ranges_for_date(day) == backward.ranges_for_date(day)

    with pytest.raises(ValueError, match="empty"):
        TzHistory([])
    with pytest.raises(ValueError, match="aware"):
        TzHistory([Rec(MSK, datetime(2026, 9, 1))])
    with pytest.raises(ValueError, match="aware"):
        forward.local_date(datetime(2026, 10, 5, 12))
    with pytest.raises(ZoneInfoNotFoundError):
        TzHistory([Rec("Mars/Olympus_Mons", REGISTERED)])
