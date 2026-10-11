"""R5 «Нерегулярный отбой» (SPEC F9): services/rules/r5.py.

A bedtime is the start of the night's main session, as the local wall-clock time in the zone in
effect at it; times of day are compared on the circle of the day.
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services.rules import r5
from app.services.rules.base import Day, Facts

D = date(2026, 10, 10)  # the anchor
MOSCOW = ZoneInfo("Europe/Moscow")  # UTC+3


def night(days_before: int, bed: str | None, *, valid: bool = True) -> Day:
    """The night that ends on the morning of D − days_before; `bed` — local bedtime "HH:MM"
    (from 12:00 on — the evening before), None — no row."""
    wake_day = D - timedelta(days=days_before)
    hours, minutes = map(int, (bed or "23:00").split(":"))
    evening = wake_day - timedelta(days=1) if hours >= 12 else wake_day
    start = datetime(evening.year, evening.month, evening.day, hours, minutes, tzinfo=MOSCOW)
    return Day(
        wake_day,
        status="complete",
        wear_minutes=1200,
        sleep_minutes=450,
        sleep_start=start.astimezone(UTC),
        sleep_end=(start + timedelta(minutes=450)).astimezone(UTC),
        night_valid=valid,
    )


def week(*beds: str | None, invalid: tuple[int, ...] = ()) -> list[Day]:
    """The 7 nights D−6 … D, oldest first."""
    assert len(beds) == 7
    return [
        night(6 - i, bed, valid=i not in invalid) for i, bed in enumerate(beds) if bed is not None
    ]


def facts(days: list[Day]) -> Facts:
    return Facts(days, today=D, local_time=lambda ts: ts.astimezone(MOSCOW))


@pytest.mark.xfail(strict=True, reason="step 8.2: not implemented")
def test_circular_stdev_2330_vs_0030_is_60() -> None:
    assert r5.circular_diff(23 * 60 + 30, 30) == 60
    assert r5.circular_diff(30, 23 * 60 + 30) == 60
    # 60 min apart, so the spread is that of 12:00 and 13:00 (population stdev: 30 min).
    assert r5.circular_stdev([23 * 60 + 30, 30]) == pytest.approx(30)
    assert r5.circular_stdev([12 * 60, 13 * 60]) == pytest.approx(30)
    # The bedtimes the generator makes for «irregular»: every hour from 20:30 to 02:30.
    spread = [(m + 1440) % 1440 for m in (-30, 150, -210, 90, -90, 30, -150)]
    assert r5.circular_stdev(spread) == pytest.approx(120)

    # Alternating 23:30 / 00:30 local is a regular bedtime: closes, does not fire.
    verdict = r5.evaluate(facts(week(*["23:30", "00:30"] * 3, "23:30")), D)
    assert verdict.kind == "close"


@pytest.mark.xfail(strict=True, reason="step 8.2: not implemented")
def test_requires_5_of_7_valid_nights() -> None:
    wild = ["20:30", "02:30", "21:30", "01:30", "22:30", "00:30", "23:30"]

    four_rows = wild[:4] + [None] * 3
    assert r5.evaluate(facts(week(*four_rows)), D).kind == "unknown"
    two_invalid = week(*wild[:6], None, invalid=(1, 3))
    assert r5.evaluate(facts(two_invalid), D).kind == "unknown"
    # Five valid nights of seven are enough; the invalid ones are left out of the spread.
    five = r5.evaluate(facts(week(*wild[:5], None, "23:00", invalid=(6,))), D)
    assert five.kind == "fire"
    assert [n["bedtime"] for n in five.context["nights"]] == [
        "20:30",
        "02:30",
        "21:30",
        "01:30",
        "22:30",
    ]


@pytest.mark.xfail(strict=True, reason="step 8.2: not implemented")
def test_fires_over_90_closes_under_60() -> None:
    def spread_of(stdev: float) -> list[str]:
        # 7 bedtimes symmetric around midnight with the given population stdev:
        # offsets ±a, ±a, ±a and 0 → stdev = a·√(6/7).
        a = round(stdev / (6 / 7) ** 0.5)
        beds = [-a, a, -a, a, -a, a, 0]
        return [f"{(m // 60) % 24:02d}:{m % 60:02d}" for m in beds]

    fired = r5.evaluate(facts(week(*spread_of(120))), D)
    assert fired.kind == "fire"
    assert fired.context["stdev_minutes"] == pytest.approx(120, abs=1)
    assert fired.context["threshold_minutes"] == 90
    assert r5.evaluate(facts(week(*spread_of(85))), D).kind == "hold"
    assert r5.evaluate(facts(week(*spread_of(65))), D).kind == "hold"
    assert r5.evaluate(facts(week(*spread_of(55))), D).kind == "close"
    assert r5.evaluate(facts(week(*["23:00"] * 7)), D).kind == "close"
