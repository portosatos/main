"""NDJSON output of htgen: format, determinism, period, watch and phone models (SPEC F13, 7.2)."""

from __future__ import annotations

import json
import re
import tempfile
from datetime import date, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import pytest
from conftest import (
    MSK,
    intervals,
    local_midnight,
    merge_adjacent,
    run_htgen,
    runs,
    ts,
)
from hypothesis import given, settings
from hypothesis import strategies as st

WATCH = {"id": "watch-1", "kind": "watch", "name": "Часы"}
PHONE = {"id": "phone-1", "kind": "phone", "name": "Телефон"}
ISO_WITH_OFFSET = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$")
WALK_CADENCE = 80  # steps per minute: walking; the rest of the day is well below this
FAST = ("--hr-interval", "60")  # fewer pulse points where the test does not look at them


def times_of(record: dict) -> list[datetime]:
    return [ts(record[k]) for k in ("start", "end", "ts") if k in record]


# --- plan: tests before code ------------------------------------------------------------------


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="step 2.1: not implemented")
def test_same_seed_byte_identical_output(htgen) -> None:
    args = ("--start", "2026-10-01", "--days", "2", "--seed", "42")
    first, second = htgen(*args), htgen(*args)
    assert first.path.read_bytes() == second.path.read_bytes()
    assert len(first.records) > 0
    other = htgen("--start", "2026-10-01", "--days", "2", "--seed", "43")
    assert other.path.read_bytes() != first.path.read_bytes()


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="step 2.1: not implemented")
def test_period_bounds_respected(htgen) -> None:
    out = htgen("--start", "2026-10-01", "--end", "2026-10-03", "--seed", "7", *FAST)
    lo, hi = local_midnight(date(2026, 10, 1)), local_midnight(date(2026, 10, 4))
    for record in out.records:
        for moment in times_of(record):
            assert lo <= moment <= hi, record
        if "ts" in record:
            assert ts(record["ts"]) < hi, record
    days = {times_of(r)[0].astimezone(MSK).date() for r in out.records}
    assert days == {date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)}

    short = htgen("--start", "2026-10-01", "--days", "2", "--seed", "7", *FAST)
    days = {times_of(r)[0].astimezone(MSK).date() for r in short.records}
    assert days == {date(2026, 10, 1), date(2026, 10, 2)}


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="step 2.1: not implemented")
def test_first_line_is_meta_with_devices(htgen) -> None:
    out = htgen("--start", "2026-10-01", "--days", "1", *FAST)
    assert out.meta == {
        "type": "meta",
        "schema": "ht.v1",
        "generator": "htgen 0.1",
        "devices": [WATCH, PHONE],
    }
    assert [r for r in out.records if r["type"] == "meta"] == []
    assert {r["device"] for r in out.records} == {"watch-1", "phone-1"}

    watch_only = htgen("--start", "2026-10-01", "--days", "1", "--devices", "watch", *FAST)
    assert watch_only.meta["devices"] == [WATCH]
    assert {r["device"] for r in watch_only.records} == {"watch-1"}


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="step 2.1: not implemented")
def test_every_timestamp_has_offset(htgen) -> None:
    out = htgen("--start", "2026-10-01", "--days", "1", "--unaligned", *FAST)
    assert {r["type"] for r in out.records} == {"steps", "sleep", "hr"}
    for record in out.records:
        for key in ("start", "end", "ts"):
            if key in record:
                assert ISO_WITH_OFFSET.match(record[key]), record
                assert ts(record[key]).utcoffset() == timedelta(hours=3), record  # Europe/Moscow


@settings(max_examples=25, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=2**32 - 1),
    start=st.dates(min_value=date(2024, 1, 1), max_value=date(2027, 12, 31)),
    days=st.integers(min_value=1, max_value=3),
    unaligned=st.booleans(),
)
@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="step 2.1: not implemented")
def test_steps_intervals_do_not_overlap_per_device(
    seed: int, start: date, days: int, unaligned: bool
) -> None:
    args = ["--start", start.isoformat(), "--days", str(days), "--seed", str(seed), *FAST]
    if unaligned:
        args.append("--unaligned")
    with tempfile.TemporaryDirectory() as tmp:
        out = run_htgen(Path(tmp) / "out.ndjson", *args)
    for device in ("watch-1", "phone-1"):
        steps = intervals(out.of("steps", device))
        assert steps, device
        for (s1, e1, r1), (s2, _e2, r2) in pairwise(steps):
            assert s1 < e1, r1
            assert e1 <= s2, (r1, r2)


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="step 2.1: not implemented")
def test_walks_recorded_by_both_devices_phone_90_to_97_percent(htgen) -> None:
    out = htgen("--start", "2026-10-01", "--days", "3", "--seed", "3", *FAST)
    watch = intervals(out.of("steps", "watch-1"))
    phone = intervals(out.of("steps", "phone-1"))
    walks = [run for run in runs(watch, lambda r: r["count"] >= WALK_CADENCE) if len(run) >= 10]
    assert {w[0][0].astimezone(MSK).date() for w in walks} == {
        date(2026, 10, 1),
        date(2026, 10, 2),
        date(2026, 10, 3),
    }, "a walk every day"
    for walk in walks:
        walk_start, walk_end = walk[0][0], walk[-1][1]
        slots = [(s, e, r) for s, e, r in phone if walk_start <= s and e <= walk_end]
        assert slots, f"phone did not record the walk {walk_start}–{walk_end}"
        phone_steps = sum(r["count"] for _s, _e, r in slots)
        watch_steps = sum(
            r["count"] for s, e, r in watch for ps, pe, _ in slots if ps <= s and e <= pe
        )
        assert 0.90 <= phone_steps / watch_steps <= 0.97, (walk_start, phone_steps, watch_steps)


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="step 2.1: not implemented")
def test_unaligned_produces_non_minute_boundaries(htgen) -> None:
    aligned = htgen("--start", "2026-10-01", "--days", "1", "--seed", "9", *FAST)
    unaligned = htgen("--start", "2026-10-01", "--days", "1", "--seed", "9", "--unaligned", *FAST)
    for device, length in (("watch-1", 60), ("phone-1", 300)):
        for out in (aligned, unaligned):
            durations = {(e - s).total_seconds() for s, e, _ in intervals(out.of("steps", device))}
            assert durations == {length}, (device, durations)
        assert all(
            ts(r[k]).second == 0 for r in aligned.of("steps", device) for k in ("start", "end")
        ), device
        assert any(ts(r["start"]).second != 0 for r in unaligned.of("steps", device)), device


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="step 2.1: not implemented")
def test_phone_has_no_hr(htgen) -> None:
    out = htgen("--start", "2026-10-01", "--days", "2", *FAST)
    assert out.of("hr", "phone-1") == []
    assert out.of("steps", "phone-1") and out.of("sleep", "phone-1")
    assert out.of("hr", "watch-1")


# --- beyond the plan --------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="step 2.1: not implemented")
def test_records_pass_data_format_validation(htgen) -> None:
    """SPEC 7.2: end > start, count >= 0, 30 <= bpm <= 230, interval <= 24 h; LF UTF-8 lines."""
    out = htgen("--start", "2026-10-01", "--days", "2", "--unaligned")
    raw = out.path.read_bytes()
    assert raw.endswith(b"\n") and b"\r" not in raw
    keys = {
        "steps": {"type", "device", "start", "end", "count"},
        "sleep": {"type", "device", "start", "end"},
        "hr": {"type", "device", "ts", "bpm"},
    }
    for line in raw.decode("utf-8").splitlines()[1:]:
        record = json.loads(line)
        assert set(record) == keys[record["type"]], record
        if "start" in record:
            length = ts(record["end"]) - ts(record["start"])
            assert timedelta(0) < length <= timedelta(hours=24), record
        if record["type"] == "steps":
            assert isinstance(record["count"], int) and record["count"] >= 0, record
        if record["type"] == "hr":
            assert isinstance(record["bpm"], int) and 30 <= record["bpm"] <= 230, record


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="step 2.1: not implemented")
@pytest.mark.parametrize(("args", "step"), [((), 5), (("--hr-interval", "30"), 30)])
def test_watch_hr_every_hr_interval_seconds(htgen, args: tuple[str, ...], step: int) -> None:
    out = htgen("--start", "2026-10-01", "--days", "1", *args)
    points = sorted(ts(r["ts"]) for r in out.of("hr", "watch-1"))
    assert {(b - a).total_seconds() for a, b in pairwise(points)} == {step}
    assert len(points) == 24 * 3600 // step  # the watch is worn all day (no gaps before step 2.2)


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="step 2.1: not implemented")
def test_daily_profile_sleep_walks_and_sedentary(htgen) -> None:
    out = htgen("--start", "2026-10-01", "--days", "4", "--seed", "5", *FAST)
    lo, hi = local_midnight(date(2026, 10, 1)), local_midnight(date(2026, 10, 5))
    nights = [
        (s, e)
        for s, e in merge_adjacent([(s, e) for s, e, _ in intervals(out.of("sleep", "watch-1"))])
        if lo < s and e < hi  # the period cuts the first and the last night
    ]
    assert len(nights) == 3
    for start, end in nights:
        assert timedelta(hours=6) <= end - start <= timedelta(hours=9), (start, end)
        assert start.astimezone(MSK).hour in {21, 22, 23, 0, 1}, start

    watch = intervals(out.of("steps", "watch-1"))
    walks = [run for run in runs(watch, lambda r: r["count"] >= WALK_CADENCE) if len(run) >= 10]
    sitting = [run for run in runs(watch, lambda r: r["count"] == 0) if len(run) >= 60]
    for day in (date(2026, 10, d) for d in range(1, 5)):
        assert any(w[0][0].astimezone(MSK).date() == day for w in walks), day
        assert any(s[0][0].astimezone(MSK).date() == day for s in sitting), day


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="step 2.1: not implemented")
def test_phone_sleep_within_20_minutes_of_watch(htgen) -> None:
    out = htgen("--start", "2026-10-01", "--days", "6", "--seed", "11", *FAST)
    lo, hi = local_midnight(date(2026, 10, 1)), local_midnight(date(2026, 10, 7))

    def nights(device: str) -> list[tuple[datetime, datetime]]:
        spans = [(s, e) for s, e, _ in intervals(out.of("sleep", device))]
        return [(s, e) for s, e in merge_adjacent(spans) if lo < s and e < hi]

    watch, phone = nights("watch-1"), nights("phone-1")
    assert len(watch) == len(phone) == 5
    tolerance = timedelta(minutes=20)
    for (ws, we), (ps, pe) in zip(watch, phone, strict=True):
        assert abs(ps - ws) <= tolerance and abs(pe - we) <= tolerance, ((ws, we), (ps, pe))
    assert watch != phone, "the phone is less accurate than the watch"
