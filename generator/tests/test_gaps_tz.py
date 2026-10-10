"""Gaps, time zones and overlapping periods (SPEC F13, step 2.2)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path

import pytest
from conftest import ts

FAST = ("--hr-interval", "60")
GAP_FROM = ts("2026-10-02T06:00:00+03:00")
GAP_TO = ts("2026-10-03T12:00:00+03:00")
NEAR = timedelta(minutes=25)  # the phone has no pulse and sleeps +-20 min apart from the watch


def span(record: dict) -> tuple[datetime, datetime]:
    if "ts" in record:
        return ts(record["ts"]), ts(record["ts"]) + timedelta(microseconds=1)
    return ts(record["start"]), ts(record["end"])


def hits(record: dict, lo: datetime, hi: datetime) -> bool:
    start, end = span(record)
    return start < hi and end > lo


@pytest.mark.parametrize(
    ("gap", "silent"),
    [
        ("2026-10-02T06:00/2026-10-03T12:00@watch", {"watch-1"}),  # local time of --tz
        ("2026-10-02T03:00Z/2026-10-03T09:00Z@phone", {"phone-1"}),
        ("2026-10-02T06:00+03:00/2026-10-03T12:00+03:00", {"watch-1", "phone-1"}),  # all devices
    ],
)
def test_explicit_gap_has_no_records_for_device(htgen, gap: str, silent: set[str]) -> None:
    out = htgen("--start", "2026-10-01", "--days", "4", "--seed", "2", "--gap", gap, *FAST)
    for device in ("watch-1", "phone-1"):
        records = [r for r in out.records if r["device"] == device]
        inside = [r for r in records if hits(r, GAP_FROM, GAP_TO)]
        if device not in silent:
            assert inside, f"{device} keeps recording during the gap of the other device"
            continue
        assert inside == [], inside[:3]
        # The device records up to the gap and right after it: nothing else is lost.
        last_before = max(span(r)[1] for r in records if span(r)[1] <= GAP_FROM)
        first_after = min(span(r)[0] for r in records if span(r)[0] >= GAP_TO)
        assert GAP_FROM - last_before <= NEAR, (device, last_before)
        assert first_after - GAP_TO <= NEAR, (device, first_after)


@pytest.mark.parametrize(("max_hours", "prob"), [(5, 0.3), (30, 0.2)])
def test_random_gaps_bounded_by_max_hours(htgen, max_hours: int, prob: float) -> None:
    out = htgen(
        "--start", "2026-09-01", "--days", "30", "--seed", "4", "--devices", "watch",
        "--gap-prob", str(prob), "--gap-max-hours", str(max_hours), *FAST,
    )  # fmt: skip
    # The watch writes its pulse round the clock, so holes in the pulse are exactly the gaps.
    pulse = sorted(ts(r["ts"]) for r in out.of("hr", "watch-1"))
    holes = [b - a for a, b in pairwise(pulse) if b - a > timedelta(seconds=60)]
    assert len(holes) >= 3, holes  # about 30 days * prob gaps
    assert max(holes) <= timedelta(hours=max_hours, seconds=60), max(holes)
    # Nothing is written in a hole: steps and sleep stop as well.
    for a, b in pairwise(pulse):
        if b - a > timedelta(seconds=60):
            lo, hi = a + timedelta(seconds=60), b
            assert [r for r in out.records if r["type"] != "hr" and hits(r, lo, hi)] == []


def test_tz_change_switches_offset_at_instant(htgen) -> None:
    moment = ts("2026-10-02T12:00:00+00:00")
    out = htgen(
        "--start", "2026-10-01", "--days", "3", "--seed", "6", "--tz", "Europe/Moscow",
        "--tz-change", "2026-10-02T12:00Z=America/New_York", *FAST,
    )  # fmt: skip
    moscow, new_york = timedelta(hours=3), timedelta(hours=-4)  # EDT in October
    for record in out.records:
        for key in ("start", "end", "ts"):
            if key in record:
                value = ts(record[key])
                assert value.utcoffset() == (moscow if value < moment else new_york), record
    # The pulse goes on through the move: nothing is lost or doubled on the long day.
    pulse = sorted(ts(r["ts"]) for r in out.of("hr", "watch-1"))
    assert {b - a for a, b in pairwise(pulse)} == {timedelta(seconds=60)}
    assert moment - timedelta(seconds=60) in pulse and moment in pulse
    # After the move the person goes to bed at night in New York.
    after = [ts(r["start"]) for r in out.of("sleep", "watch-1") if ts(r["start"]) > moment]
    assert after and after[0].utcoffset() == new_york
    assert after[0].hour in {21, 22, 23, 0, 1}, after[0]

    tokyo = htgen("--start", "2026-10-01", "--days", "2", "--tz", "Asia/Tokyo", *FAST)
    assert {ts(r.get("ts") or r["start"]).utcoffset() for r in tokyo.records} == {
        timedelta(hours=9)
    }
    bed = [ts(r["start"]) for r in tokyo.of("sleep", "watch-1") if ts(r["start"]).hour >= 12]
    assert bed and all(b.hour in {21, 22, 23} for b in bed), bed


def test_overlapping_periods_same_seed_identical_records_in_intersection(htgen) -> None:
    common = (
        "--seed", "8", "--unaligned", "--gap-prob", "0.5", "--gap-max-hours", "30",
        "--tz-change", "2026-10-04T09:00Z=Asia/Novosibirsk", *FAST,
    )  # fmt: skip
    first = htgen("--start", "2026-10-01", "--end", "2026-10-06", *common)
    second = htgen("--start", "2026-10-04", "--end", "2026-10-09", *common)
    # Local dates 2026-10-04..06: from midnight in Moscow to midnight in Novosibirsk.
    lo, hi = ts("2026-10-04T00:00:00+03:00"), ts("2026-10-07T00:00:00+07:00")

    def common_part(path: Path) -> list[str]:
        lines = path.read_text(encoding="utf-8").splitlines()[1:]
        return [line for line in lines if lo <= span(json.loads(line))[0] < hi]

    left, right = common_part(first.path), common_part(second.path)
    assert len(left) > 1000
    assert left == right
