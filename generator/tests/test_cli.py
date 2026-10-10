"""Period options: --start / --end / --days (inclusive local dates)."""

from datetime import date
from pathlib import Path

import pytest

from htgen.cli import main, resolve_period

TODAY = date(2026, 10, 10)


def test_resolve_period_combinations() -> None:
    d = date
    assert resolve_period(d(2026, 10, 1), d(2026, 10, 7), None, TODAY) == (
        d(2026, 10, 1),
        d(2026, 10, 7),
    )
    assert resolve_period(d(2026, 10, 1), None, 3, TODAY) == (d(2026, 10, 1), d(2026, 10, 3))
    assert resolve_period(None, d(2026, 10, 7), 3, TODAY) == (d(2026, 10, 5), d(2026, 10, 7))
    # Only --days: the period ends yesterday, the last full day (no data from the future).
    assert resolve_period(None, None, 7, TODAY) == (d(2026, 10, 3), d(2026, 10, 9))
    # Nothing or only one bound: 7 days.
    assert resolve_period(None, None, None, TODAY) == (d(2026, 10, 3), d(2026, 10, 9))
    assert resolve_period(d(2026, 10, 1), None, None, TODAY) == (d(2026, 10, 1), d(2026, 10, 7))
    assert resolve_period(None, d(2026, 10, 7), None, TODAY) == (d(2026, 10, 1), d(2026, 10, 7))
    assert resolve_period(d(2026, 10, 1), d(2026, 10, 1), None, TODAY) == (d(2026, 10, 1),) * 2


@pytest.mark.parametrize(
    ("start", "end", "days"),
    [
        (date(2026, 10, 5), date(2026, 10, 1), None),  # end before start
        (date(2026, 10, 1), date(2026, 10, 7), 7),  # all three given
        (None, None, 0),  # empty period
    ],
)
def test_resolve_period_rejects_bad_combinations(
    start: date | None, end: date | None, days: int | None
) -> None:
    with pytest.raises(ValueError):
        resolve_period(start, end, days, TODAY)


def test_bad_period_is_a_usage_error(tmp_path: Path) -> None:
    out = tmp_path / "x.ndjson"
    with pytest.raises(SystemExit) as exc:
        main(["--start", "2026-10-05", "--end", "2026-10-01", "--out", str(out)])
    assert exc.value.code == 2
    assert not out.exists()
