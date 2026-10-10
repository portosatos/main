"""--scenario: ready-made data for every rule of SPEC F9, anchored to the end of the period."""

from __future__ import annotations

import statistics
from datetime import date, timedelta

import pytest
from conftest import (
    active_minutes,
    circular_stdev_minutes,
    daily_steps,
    local_midnight,
    resting_hr,
    sleep_sessions,
    ts,
)

FAST = ("--hr-interval", "60")
STEPS_GOAL = 8000  # SPEC F8 default
END = date(2026, 10, 8)  # Thursday: the last complete ISO week is 2026-09-28..10-04


def dates(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def run(htgen, first: date, seed: int, *scenario: str):
    args = ("--start", first.isoformat(), "--end", END.isoformat(), "--seed", str(seed), *FAST)
    return htgen(*args, *scenario)


def sleep_hours(out, first: date) -> dict[date, float]:
    return {
        day: (end - start).total_seconds() / 3600
        for day, (start, end) in sleep_sessions(out, first, END).items()
    }


def lines_before(out, moment) -> list[str]:
    """Lines of the dates before the moment: a scenario does not touch them."""
    lines = out.path.read_text(encoding="utf-8").splitlines()[1:]
    return [
        line
        for line, record in zip(lines, out.records, strict=True)
        if ts(record.get("ts") or record["start"]) < moment
    ]


def test_scenario_short_sleep_last_3_nights_under_6h(htgen) -> None:
    first = date(2026, 10, 1)
    out, plain = run(htgen, first, 12, "--scenario", "short-sleep"), run(htgen, first, 12)
    hours, normal = sleep_hours(out, first), sleep_hours(plain, first)
    last3 = dates(END - timedelta(days=2), END)
    assert all(day in hours and hours[day] < 6 for day in last3), hours
    assert all(normal[day] >= 6 for day in last3), normal
    assert all(hours[day] >= 6 for day in hours if day not in last3), hours
    assert lines_before(out, local_midnight(last3[0] - timedelta(days=1))) == lines_before(
        plain, local_midnight(last3[0] - timedelta(days=1))
    )


def test_scenario_sedentary_steps_and_active_minutes_low(htgen) -> None:
    first = date(2026, 10, 1)
    out, plain = run(htgen, first, 13, "--scenario", "sedentary"), run(htgen, first, 13)
    last5 = dates(END - timedelta(days=4), END)
    for device in ("watch-1", "phone-1"):
        steps = daily_steps(out, device)
        assert all(steps[day] < STEPS_GOAL / 2 for day in last5), (device, steps)  # R2
    assert all(active_minutes(out, day) < 15 for day in last5)  # R6
    normal = daily_steps(plain, "watch-1")
    assert all(normal[day] >= STEPS_GOAL / 2 for day in last5), normal
    assert lines_before(out, local_midnight(last5[0])) == lines_before(
        plain, local_midnight(last5[0])
    )


def test_scenario_high_rhr_last_2_days_elevated(htgen) -> None:
    first = END - timedelta(days=15)  # 14 days of the base and 2 elevated days
    out, plain = run(htgen, first, 14, "--scenario", "high-rhr"), run(htgen, first, 14)
    for data, elevated in ((out, True), (plain, False)):
        values = {day: resting_hr(data, day) for day in dates(first, END)}
        base_days = dates(first, END - timedelta(days=2))
        assert all(values[day] is not None for day in values), values
        base = statistics.mean(values[day] for day in base_days)
        last2 = [values[END - timedelta(days=1)], values[END]]
        assert all((v >= base + 7) == elevated for v in last2), (base, last2)


def test_scenario_irregular_bedtime_stdev_over_90(htgen) -> None:
    first = END - timedelta(days=8)
    out, plain = run(htgen, first, 15, "--scenario", "irregular"), run(htgen, first, 15)
    last7 = dates(END - timedelta(days=6), END)
    for data, irregular in ((out, True), (plain, False)):
        sessions = sleep_sessions(data, first, END)
        assert all(day in sessions for day in last7), sessions.keys()
        stdev = circular_stdev_minutes([sessions[day][0] for day in last7])
        assert (stdev > 90) == irregular, stdev
        assert irregular or stdev < 60, stdev


def test_scenario_worse_week_avg_sleep_drop_over_60(htgen) -> None:
    first = date(2026, 9, 21)  # Monday: two complete ISO weeks before END
    previous_week = dates(first, date(2026, 9, 27))
    last_week = dates(date(2026, 9, 28), date(2026, 10, 4))
    out, plain = run(htgen, first, 16, "--scenario", "worse-week"), run(htgen, first, 16)
    for data, worse in ((out, True), (plain, False)):
        hours = sleep_hours(data, first)
        before = [hours[day] for day in previous_week if day in hours]
        after = [hours[day] for day in last_week if day in hours]
        assert len(before) >= 5 and len(after) >= 5, hours  # R4 needs 5 valid nights a week
        drop = (statistics.mean(before) - statistics.mean(after)) * 60
        assert (drop >= 60) == worse, drop


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_scenario_recovery_fixes_each_condition(htgen, seed: int) -> None:
    first = END - timedelta(days=20)
    out = run(htgen, first, seed, "--scenario", "recovery")
    hours = sleep_hours(out, first)
    sessions = sleep_sessions(out, first, END)
    # R1: a night of 7 h or more.
    assert hours[END] >= 7, hours[END]
    # R2 and R6: a full day with the steps goal met and 15+ active minutes.
    assert daily_steps(out, "watch-1")[END] >= STEPS_GOAL
    assert active_minutes(out, END) >= 15
    # R3: resting pulse of the last day below the base + 4.
    values = {day: resting_hr(out, day) for day in dates(first, END)}
    base_days = dates(END - timedelta(days=14), END - timedelta(days=1))
    base = statistics.mean(values[day] for day in base_days)
    assert values[END] < base + 4, (values[END], base)
    # R5: regular bedtime over the last 7 nights.
    last7 = dates(END - timedelta(days=6), END)
    assert circular_stdev_minutes([sessions[day][0] for day in last7]) < 60
    # R4: the last complete ISO week sleeps no worse than 30 min below the previous one.
    before = [hours[d] for d in dates(date(2026, 9, 21), date(2026, 9, 27)) if d in hours]
    after = [hours[d] for d in dates(date(2026, 9, 28), date(2026, 10, 4)) if d in hours]
    assert (statistics.mean(before) - statistics.mean(after)) * 60 < 30
