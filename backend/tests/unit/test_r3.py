"""R3 «Повышенный пульс в покое» (SPEC F9): services/rules/r3.py.

The two days end with the anchor; the baseline is the mean resting pulse of the 14 dates before
them (at least 7 values); closing compares the anchor day with the same baseline.
"""

from datetime import date, timedelta

import pytest

from app.services.rules import r3
from app.services.rules.base import Day, Facts

D = date(2026, 10, 10)  # the anchor


def day(days_before: int, resting_hr: float | None) -> Day:
    return Day(
        D - timedelta(days=days_before),
        status="complete",
        wear_minutes=1200,
        steps=8000,
        resting_hr=resting_hr,
    )


def baseline(*values: float | None) -> list[Day]:
    """The 14 dates before the two days (D−15 … D−2), oldest first; None — not computed."""
    assert len(values) == 14
    return [day(15 - i, v) for i, v in enumerate(values)]


def facts(*days: Day) -> Facts:
    return Facts(days, today=D + timedelta(days=1))


FLAT_60 = baseline(*[60.0] * 14)


def test_baseline_requires_7_values() -> None:
    six = baseline(*[60.0] * 6, *[None] * 8)
    seven = baseline(*[60.0] * 7, *[None] * 7)

    assert r3.evaluate(facts(*six, day(1, 70), day(0, 70)), D).kind == "unknown"
    fired = r3.evaluate(facts(*seven, day(1, 70), day(0, 70)), D)
    assert fired.kind == "fire"
    assert fired.context["baseline"] == 60
    assert fired.context["baseline_values"] == 7
    # The mean is over the computed values only; dates without a row count as missing too.
    mixed = baseline(*[58.0, 62.0] * 4, *[None] * 6)
    assert r3.evaluate(facts(*mixed, day(1, 67), day(0, 67)), D).context["baseline"] == 60
    assert r3.evaluate(facts(*mixed[:6], day(1, 70), day(0, 70)), D).kind == "unknown"


def test_fires_2_days_ge_baseline_plus_7() -> None:
    fired = r3.evaluate(facts(*FLAT_60, day(1, 67), day(0, 71.5)), D)

    assert fired.kind == "fire"
    assert fired.context["days"] == [
        {"date": "2026-10-09", "resting_hr": 67},
        {"date": "2026-10-10", "resting_hr": 71.5},
    ]
    assert fired.context["rise_bpm"] == 7
    # One of the two under baseline + 7: no.
    assert r3.evaluate(facts(*FLAT_60, day(1, 66.9), day(0, 75)), D).kind == "hold"
    assert r3.evaluate(facts(*FLAT_60, day(1, 75), day(0, 66.9)), D).kind == "hold"
    # The day before the anchor has no resting pulse: the pair is unknown.
    assert r3.evaluate(facts(*FLAT_60, day(1, None), day(0, 75)), D).kind == "unknown"
    assert r3.evaluate(facts(*FLAT_60, day(0, 75)), D).kind == "unknown"


@pytest.mark.parametrize(("anchor_hr", "kind"), [(63.9, "close"), (55, "close"), (64, "hold")])
def test_closes_below_baseline_plus_4(anchor_hr: float, kind: str) -> None:
    # Yesterday was high, the anchor day is back under baseline + 4 (hysteresis: 4 < 7).
    verdict = r3.evaluate(facts(*FLAT_60, day(1, 72), day(0, anchor_hr)), D)

    assert verdict.kind == kind
    # Closing looks at the anchor day only: the day before does not matter.
    assert r3.evaluate(facts(*FLAT_60, day(0, 63)), D).kind == "close"
    # No resting pulse on the anchor day: unknown, an open recommendation stays.
    assert r3.evaluate(facts(*FLAT_60, day(1, 63), day(0, None)), D).kind == "unknown"
    # Too few baseline values: unknown as well.
    few = baseline(*[60.0] * 6, *[None] * 8)
    assert r3.evaluate(facts(*few, day(0, 61)), D).kind == "unknown"
