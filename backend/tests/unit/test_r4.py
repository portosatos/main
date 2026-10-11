"""R4 «Сон хуже, чем на прошлой неделе» (SPEC F7, F9): services/rules/r4.py.

The anchor is the Sunday of the last complete ISO week; it is compared with the week before.
The means are over valid nights only, whatever the day's status.
"""

from datetime import date, timedelta

from app.services.rules import r4
from app.services.rules.base import Day, Facts

SUNDAY = date(2026, 10, 4)  # the end of 2026-W40; W39 is 2026-09-21 … 2026-09-27


def week(sunday: date, *minutes: int | None, invalid: tuple[int, ...] = ()) -> list[Day]:
    """Nights Monday … Sunday of the week ending `sunday`: minutes of sleep, None — no row;
    `invalid` — indexes of nights that are not valid."""
    assert len(minutes) == 7
    return [
        Day(
            sunday - timedelta(days=6 - i),
            status="partial",
            wear_minutes=600,
            sleep_minutes=m,
            night_valid=i not in invalid,
        )
        for i, m in enumerate(minutes)
        if m is not None
    ]


def facts(last: list[Day], before: list[Day]) -> Facts:
    return Facts([*before, *last], today=SUNDAY + timedelta(days=3))


PREVIOUS = week(SUNDAY - timedelta(days=7), *[480] * 7)


def test_requires_5_valid_nights_each_week() -> None:
    four_last = week(SUNDAY, 300, 300, 300, 300, None, None, None)
    assert r4.evaluate(facts(four_last, PREVIOUS), SUNDAY).kind == "unknown"
    # Five rows, but one night is not valid.
    one_invalid = week(SUNDAY, 300, 300, 300, 300, 300, None, None, invalid=(2,))
    assert r4.evaluate(facts(one_invalid, PREVIOUS), SUNDAY).kind == "unknown"
    # The week before has four valid nights.
    four_before = week(SUNDAY - timedelta(days=7), 480, 480, 480, 480, None, None, None)
    assert r4.evaluate(facts(week(SUNDAY, *[300] * 7), four_before), SUNDAY).kind == "unknown"
    # Five valid nights: known; the invalid long night is not in the mean.
    five = week(SUNDAY, 400, 400, 900, 400, 420, 410, None, invalid=(2,))
    verdict = r4.evaluate(facts(five, PREVIOUS), SUNDAY)
    assert verdict.kind == "fire"
    assert verdict.context["weeks"] == [
        {"week": "2026-W39", "avg_sleep_minutes": 480, "nights": 7},
        {"week": "2026-W40", "avg_sleep_minutes": 406, "nights": 5},
    ]


def test_fires_on_drop_ge_60() -> None:
    fired = r4.evaluate(facts(week(SUNDAY, *[420] * 7), PREVIOUS), SUNDAY)

    assert fired.kind == "fire"
    assert fired.context["drop_minutes"] == 60
    # 59 minutes less: not enough to open.
    assert r4.evaluate(facts(week(SUNDAY, *[421] * 7), PREVIOUS), SUNDAY).kind == "hold"


def test_closes_under_30() -> None:
    assert r4.evaluate(facts(week(SUNDAY, *[451] * 7), PREVIOUS), SUNDAY).kind == "close"
    # Sleeping more than the week before closes as well.
    assert r4.evaluate(facts(week(SUNDAY, *[540] * 7), PREVIOUS), SUNDAY).kind == "close"
    # Exactly 30 less: neither.
    assert r4.evaluate(facts(week(SUNDAY, *[450] * 7), PREVIOUS), SUNDAY).kind == "hold"
    # Too few nights: an open recommendation is not closed.
    few = week(SUNDAY, 480, 480, None, None, None, None, 480)
    assert r4.evaluate(facts(few, PREVIOUS), SUNDAY).kind == "unknown"
