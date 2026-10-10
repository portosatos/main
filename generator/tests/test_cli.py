"""Period options: --start / --end / --days (inclusive local dates)."""

import subprocess
import sys
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


def test_closed_stdout_pipe_is_not_an_error() -> None:
    """htgen ... | head: the reader closes the pipe early (regression test, added after code)."""
    args = ["--start", "2026-10-01", "--days", "3", "--hr-interval", "5"]
    proc = subprocess.Popen(
        [sys.executable, "-m", "htgen", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    assert proc.stdout is not None and proc.stderr is not None
    assert proc.stdout.readline().startswith(b'{"type":"meta"')
    proc.stdout.close()
    stderr = proc.stderr.read()
    assert proc.wait(timeout=60) == 0
    assert stderr == b""


PERIOD = ("--start", "2026-10-01", "--days", "20")


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((*PERIOD, "--gap", "2026-10-02T06:00"), "--gap"),  # no end
        ((*PERIOD, "--gap", "2026-10-03T00:00/2026-10-02T00:00@watch"), "раньше начала"),
        ((*PERIOD, "--gap", "2026-10-02T00:00/2026-10-03T00:00@tablet"), "watch или phone"),
        ((*PERIOD, "--gap", "вчера/сегодня"), "--gap"),
        ((*PERIOD, "--gap-prob", "1.5"), "--gap-prob"),
        ((*PERIOD, "--gap-max-hours", "0"), "--gap-max-hours"),
        ((*PERIOD, "--tz", "Mars/Olympus"), "Mars/Olympus"),
        ((*PERIOD, "--tz-change", "2026-10-02T12:00Z"), "МОМЕНТ=ПОЯС"),
        ((*PERIOD, "--tz-change", "2026-10-02T12:00=Asia/Tokyo"), "со смещением"),
        (
            (
                *PERIOD,
                "--tz-change",
                "2026-10-02T12:00Z=Asia/Tokyo",
                "--tz-change",
                "2026-10-02T15:00+03:00=Europe/Paris",
            ),
            "в один и тот же момент",
        ),
        ((*PERIOD, "--scenario", "nope"), "сценарии"),
        ((*PERIOD, "--scenario", "recovery,short-sleep"), "не сочетается"),
        (("--start", "2026-10-01", "--days", "8", "--scenario", "high-rhr"), "не меньше 9 дней"),
        (("--start", "2026-10-01", "--days", "10", "--scenario", "worse-week"), "ISO-недели"),
    ],
)
def test_bad_gap_tz_and_scenario_options_are_usage_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], args: tuple[str, ...], message: str
) -> None:
    """Added after the code of step 2.2: before it the options were unknown and exited 2 anyway."""
    out = tmp_path / "x.ndjson"
    with pytest.raises(SystemExit) as exc:
        main([*args, "--out", str(out)])
    assert exc.value.code == 2
    assert message in capsys.readouterr().err
    assert not out.exists()
