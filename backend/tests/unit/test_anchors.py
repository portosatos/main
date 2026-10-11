"""Anchor dates of the rules (SPEC F9 «Опорная дата оценки»): services/rules/r*.py::anchor and
engine.make_facts, which takes «today» from Clock and the user's time zone history."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest

from app.clock import Clock
from app.services.localtime import TzHistory
from app.services.rules import r1, r2, r3, r4, r5, r6
from app.services.rules.base import Day, Facts, Rule
from app.services.rules.engine import LOOKBACK, RULES, make_facts


@dataclass(frozen=True)
class Zone:
    tz: str
    valid_from: datetime


def clock_at(moment: datetime) -> Clock:
    return Clock(app_env="test", system_now=lambda: moment)


def complete_day(day: date, *, night_valid: bool = True) -> Day:
    """A day with every metric and a valid night: data on a date never moves an anchor of R2–R4
    and R6."""
    start = datetime(day.year, day.month, day.day, tzinfo=UTC) - timedelta(hours=1)
    return Day(
        day,
        status="complete",
        wear_minutes=1440,
        steps=9000,
        active_minutes=40,
        sleep_minutes=480,
        sleep_start=start,
        sleep_end=start + timedelta(hours=8),
        night_valid=night_valid,
        resting_hr=60,
    )


@pytest.mark.xfail(strict=True, reason="step 8.2: not implemented")
@pytest.mark.parametrize("rule", [r2.RULE, r3.RULE, r6.RULE], ids=lambda r: r.code)
async def test_r2_r3_r6_anchor_yesterday_by_clock(rule: Rule) -> None:
    # 21:30 UTC on 10.10 is 00:30 on 11.10 in Moscow: there today is 11.10, in UTC — 10.10.
    now = await clock_at(datetime(2026, 10, 10, 21, 30, tzinfo=UTC)).now()
    days = [complete_day(date(2026, 10, 11)), complete_day(date(2026, 10, 10))]
    moscow = make_facts(days, TzHistory([Zone("Europe/Moscow", now - timedelta(days=30))]), now)
    utc = make_facts(days, TzHistory([Zone("UTC", now - timedelta(days=30))]), now)

    assert moscow.today == date(2026, 10, 11)
    assert rule.anchor(moscow) == date(2026, 10, 10)
    assert utc.today == date(2026, 10, 10)
    assert rule.anchor(utc) == date(2026, 10, 9)
    # Today's own data do not matter: today is not over yet.
    assert rule.anchor(make_facts([], TzHistory([Zone("UTC", now)]), now)) == date(2026, 10, 9)


@pytest.mark.parametrize(
    "rule",
    [
        pytest.param(r1.RULE, id="R1"),
        pytest.param(
            r5.RULE,
            id="R5",
            marks=pytest.mark.xfail(strict=True, reason="step 8.2: not implemented"),
        ),
    ],
)
def test_r1_r5_anchor_today_if_valid_night(rule: Rule) -> None:
    today = date(2026, 10, 10)
    yesterday = today - timedelta(days=1)

    assert rule.anchor(Facts([complete_day(today)], today)) == today
    assert rule.anchor(Facts([complete_day(today, night_valid=False)], today)) == yesterday
    assert rule.anchor(Facts([complete_day(yesterday)], today)) == yesterday
    # A valid night without a main session start says nothing about the bedtime (R5) or sleep.
    no_night = Day(today, status="partial", wear_minutes=600, night_valid=False)
    assert rule.anchor(Facts([no_night], today)) == yesterday


@pytest.mark.xfail(strict=True, reason="step 8.2: not implemented")
@pytest.mark.parametrize(
    ("today", "sunday"),
    [
        (date(2026, 10, 12), date(2026, 10, 11)),  # Monday: the week ended yesterday
        (date(2026, 10, 14), date(2026, 10, 11)),  # Wednesday
        (date(2026, 10, 11), date(2026, 10, 4)),  # Sunday: this week is not over yet
        (date(2027, 1, 1), date(2026, 12, 27)),  # Friday: 2026-W52 over the new year
    ],
)
def test_r4_anchor_last_complete_iso_week(today: date, sunday: date) -> None:
    anchor = r4.RULE.anchor(Facts([complete_day(today)], today))

    assert anchor == sunday
    assert anchor.isoweekday() == 7


@pytest.mark.xfail(strict=True, reason="step 8.2: not implemented")
def test_engine_evaluates_r1_to_r6_reading_three_weeks() -> None:
    """Beyond the plan: every rule is in the engine, and the dates it loads cover each anchor and
    window (R4: two weeks before a Sunday up to 7 days back)."""
    assert [rule.code for rule in RULES] == ["R1", "R2", "R3", "R4", "R5", "R6"]
    assert LOOKBACK == timedelta(days=20)
