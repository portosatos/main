"""R2 «Мало шагов» (SPEC F6, F8, F9): services/rules/r2.py.

Only complete days count; each day is compared with the steps goal in effect on that day.
"""

from datetime import date, timedelta

from app.services.goals import GoalKind
from app.services.rules import r2
from app.services.rules.base import Day, Facts

D = date(2026, 10, 9)


def day(days_before: int, steps: int, *, status: str = "complete") -> Day:
    return Day(
        D - timedelta(days=days_before),
        status=status,  # type: ignore[arg-type]
        wear_minutes=900 if status == "complete" else 400,
        steps=steps,
    )


def facts(*days: Day, goal: dict[date, float] | None = None) -> Facts:
    """Days with the default steps goal (8000) or, with `goal`, the targets in effect from the
    given dates on."""
    changes = sorted((goal or {}).items())

    def target(kind: GoalKind, on: date) -> float:
        assert kind == "steps"
        current = 8000.0
        for start, value in changes:
            if start <= on:
                current = value
        return current

    return Facts(days, today=D + timedelta(days=1), goal=target)


def test_fires_on_3_complete_days_under_half_goal() -> None:
    verdict = r2.evaluate(facts(day(2, 3000), day(1, 3999), day(0, 120)), D)

    assert verdict.kind == "fire"
    assert verdict.context["days"] == [
        {"date": "2026-10-07", "steps": 3000, "goal": 8000},
        {"date": "2026-10-08", "steps": 3999, "goal": 8000},
        {"date": "2026-10-09", "steps": 120, "goal": 8000},
    ]
    # Exactly half of the goal is not «under half».
    assert r2.evaluate(facts(day(2, 3000), day(1, 4000), day(0, 120)), D).kind == "hold"


def test_partial_day_in_window_unknown() -> None:
    # Few steps on a day the watch was barely worn are not «few steps».
    with_partial = facts(day(2, 3000), day(1, 500, status="partial"), day(0, 1000))
    assert r2.evaluate(with_partial, D).kind == "unknown"
    # A date without data.
    assert r2.evaluate(facts(day(2, 3000), day(1, 3000)), D).kind == "unknown"
    # A partial anchor day with the goal met does not close either.
    assert r2.evaluate(facts(day(0, 9000, status="partial")), D).kind == "unknown"


def test_closes_on_goal_met_day() -> None:
    assert r2.evaluate(facts(day(2, 3000), day(1, 3000), day(0, 8000)), D).kind == "close"
    # The days before the anchor do not matter for closing.
    assert r2.evaluate(facts(day(0, 12000)), D).kind == "close"
    # Over half, under the goal: neither.
    assert r2.evaluate(facts(day(2, 3000), day(1, 3000), day(0, 7999)), D).kind == "hold"


def test_uses_goal_valid_on_that_day() -> None:
    # The goal fell from 8000 to 4000 on D−1: half of it is 4000 on D−2 and 2000 since D−1.
    lowered = {D - timedelta(days=1): 4000.0}

    fired = r2.evaluate(facts(day(2, 3500), day(1, 1900), day(0, 1500), goal=lowered), D)
    assert fired.kind == "fire"
    assert [d["goal"] for d in fired.context["days"]] == [8000, 4000, 4000]
    # 2500 on D−1 is over half of that day's goal.
    held = r2.evaluate(facts(day(2, 3500), day(1, 2500), day(0, 1500), goal=lowered), D)
    assert held.kind == "hold"
    # The anchor day meets its own (lowered) goal.
    assert r2.evaluate(facts(day(0, 4000), goal=lowered), D).kind == "close"
