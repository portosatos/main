"""R6 «Нет активности» (SPEC F6, F9): services/rules/r6.py. Only complete days count."""

from datetime import date, timedelta

import pytest

from app.services.rules import r6
from app.services.rules.base import Day, Facts

D = date(2026, 10, 9)  # the anchor (yesterday)


def day(days_before: int, active: int, *, status: str = "complete") -> Day:
    return Day(
        D - timedelta(days=days_before),
        status=status,  # type: ignore[arg-type]
        wear_minutes=900 if status == "complete" else 300,
        steps=2000,
        active_minutes=active,
    )


def facts(*days: Day) -> Facts:
    return Facts(days, today=D + timedelta(days=1))


def five(*active: int) -> list[Day]:
    """D−4 … D, oldest first."""
    return [day(4 - i, a) for i, a in enumerate(active)]


@pytest.mark.xfail(strict=True, reason="step 8.2: not implemented")
def test_fires_5_complete_days_under_15_active() -> None:
    fired = r6.evaluate(facts(*five(0, 14, 3, 10, 14)), D)

    assert fired.kind == "fire"
    assert fired.context["days"] == [
        {"date": "2026-10-05", "active_minutes": 0},
        {"date": "2026-10-06", "active_minutes": 14},
        {"date": "2026-10-07", "active_minutes": 3},
        {"date": "2026-10-08", "active_minutes": 10},
        {"date": "2026-10-09", "active_minutes": 14},
    ]
    # Four days are not five.
    assert r6.evaluate(facts(*five(0, 14, 3, 10, 14)[1:]), D).kind == "unknown"
    # A partial day in the window: the watch was barely worn, its 2 minutes say nothing.
    with_partial = [*five(0, 14, 3, 10, 14)[:2], day(2, 2, status="partial"), day(1, 1), day(0, 1)]
    assert r6.evaluate(facts(*with_partial), D).kind == "unknown"
    # An active day inside the window, not the anchor: neither.
    assert r6.evaluate(facts(*five(0, 14, 30, 10, 14)), D).kind == "hold"


@pytest.mark.xfail(strict=True, reason="step 8.2: not implemented")
def test_closes_on_active_day() -> None:
    assert r6.evaluate(facts(*five(0, 0, 0, 0, 15)), D).kind == "close"
    # The days before the anchor do not matter for closing.
    assert r6.evaluate(facts(day(0, 40)), D).kind == "close"
    # A partial anchor day with many active minutes does not close.
    assert r6.evaluate(facts(day(0, 90, status="partial")), D).kind == "unknown"
