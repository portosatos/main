"""R1 «Недосып» (SPEC F6, F9): services/rules/r1.py.

A night is the sleep of its wake day (`sleep_minutes` of the date) and counts only when valid,
whatever the day's status.
"""

from datetime import date, timedelta

import pytest

from app.services.rules import r1
from app.services.rules.base import Day, Facts
from app.services.rules.engine import plan_actions

D = date(2026, 10, 10)


def night(days_before: int, hours: float, *, valid: bool = True, status: str = "complete") -> Day:
    return Day(
        D - timedelta(days=days_before),
        status=status,  # type: ignore[arg-type]
        wear_minutes=1440 if status == "complete" else 500,
        sleep_minutes=round(hours * 60),
        night_valid=valid,
    )


def facts(*days: Day) -> Facts:
    return Facts(days, today=D)


def test_fires_on_3_valid_nights_under_6h() -> None:
    verdict = r1.evaluate(facts(night(2, 5.5), night(1, 5), night(0, 5.98)), D)

    assert verdict.kind == "fire"
    assert verdict.context["nights"] == [
        {"date": "2026-10-08", "sleep_minutes": 330},
        {"date": "2026-10-09", "sleep_minutes": 300},
        {"date": "2026-10-10", "sleep_minutes": 359},
    ]
    # Two short nights are not enough.
    assert r1.evaluate(facts(night(1, 5), night(0, 5)), D).kind != "fire"


def test_invalid_night_in_window_unknown() -> None:
    # The watch was off for a while in the middle night: its 3 h are not a short night.
    with_gap = facts(night(2, 5), night(1, 3, valid=False), night(0, 5))
    assert r1.evaluate(with_gap, D).kind == "unknown"
    # A date without data at all.
    assert r1.evaluate(facts(night(2, 5), night(0, 5)), D).kind == "unknown"
    # The anchor night itself is invalid.
    assert r1.evaluate(facts(night(2, 5), night(1, 5), night(0, 2, valid=False)), D).kind == (
        "unknown"
    )


def test_fires_on_valid_nights_of_partial_days() -> None:
    nights = facts(
        night(2, 5, status="partial"),
        night(1, 5.5, status="partial"),
        night(0, 4, status="partial"),
    )

    assert r1.evaluate(nights, D).kind == "fire"


def test_closes_on_night_ge_7h() -> None:
    assert r1.evaluate(facts(night(2, 5), night(1, 5), night(0, 7)), D).kind == "close"
    # The earlier nights do not matter for closing: one valid long night is enough.
    assert r1.evaluate(facts(night(0, 8.5)), D).kind == "close"
    # A long but invalid night does not close.
    assert r1.evaluate(facts(night(0, 8, valid=False)), D).kind == "unknown"


@pytest.mark.parametrize("hours", [6, 6.5, 6.98])
def test_6_to_7h_keeps_open(hours: float) -> None:
    window = facts(night(2, 5), night(1, 5), night(0, hours))

    verdict = r1.evaluate(window, D)

    assert verdict.kind == "hold"
    assert plan_actions([r1.RULE], window, enabled={"R1"}, open_codes={"R1"}) == []
