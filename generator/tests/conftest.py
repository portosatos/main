"""Helpers: run htgen in-process and read its NDJSON output."""

from __future__ import annotations

import json
import math
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from htgen.cli import main

MSK = ZoneInfo("Europe/Moscow")  # default --tz of the generator
MINUTE = timedelta(minutes=1)


@dataclass(frozen=True)
class Output:
    path: Path
    lines: list[dict]

    @property
    def meta(self) -> dict:
        return self.lines[0]

    @property
    def records(self) -> list[dict]:
        return [r for r in self.lines if r.get("type") != "meta"]

    def of(self, type_: str, device: str | None = None) -> list[dict]:
        return [
            r
            for r in self.records
            if r["type"] == type_ and (device is None or r["device"] == device)
        ]


def run_htgen(out: Path, *args: str) -> Output:
    assert main([*args, "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    return Output(out, [json.loads(line) for line in text.splitlines()])


@pytest.fixture
def htgen(tmp_path: Path) -> Callable[..., Output]:
    counter = iter(range(1_000_000))

    def run(*args: str) -> Output:
        return run_htgen(tmp_path / f"out-{next(counter)}.ndjson", *args)

    return run


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def local_midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=MSK)


def intervals(records: list[dict]) -> list[tuple[datetime, datetime, dict]]:
    """(start, end, record) sorted by start."""
    return sorted(((ts(r["start"]), ts(r["end"]), r) for r in records), key=lambda x: x[0])


def merge_adjacent(spans: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Join intervals that touch or overlap (sleep may be split into several records)."""
    merged: list[tuple[datetime, datetime]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def runs(
    items: list[tuple[datetime, datetime, dict]], keep: Callable[[dict], bool]
) -> list[list[tuple[datetime, datetime, dict]]]:
    """Maximal runs of back-to-back intervals whose records satisfy keep()."""
    result: list[list[tuple[datetime, datetime, dict]]] = []
    for item in items:
        if not keep(item[2]):
            continue
        if result and result[-1][-1][1] == item[0]:
            result[-1].append(item)
        else:
            result.append([item])
    return result


# --- daily metrics as the backend will compute them (SPEC F5, F7), for the scenario tests --------

SESSION_JOIN = timedelta(minutes=30)  # sleep records with a smaller break form one session
ACTIVE_STEPS = 100  # steps per minute of an active minute


def sleep_sessions(
    out: Output, first: date, last: date, device: str = "watch-1"
) -> dict[date, tuple[datetime, datetime]]:
    """Main (longest) sleep session per local wake date; sessions cut by the period are skipped."""
    lo, hi = local_midnight(first), local_midnight(last + timedelta(days=1))
    sessions: list[tuple[datetime, datetime]] = []
    for start, end, _ in intervals(out.of("sleep", device)):
        if sessions and start - sessions[-1][1] <= SESSION_JOIN:
            sessions[-1] = (sessions[-1][0], max(sessions[-1][1], end))
        else:
            sessions.append((start, end))
    by_day: dict[date, tuple[datetime, datetime]] = {}
    for start, end in sessions:
        if start <= lo or end >= hi:
            continue
        day = end.astimezone(MSK).date()
        if day not in by_day or end - start > by_day[day][1] - by_day[day][0]:
            by_day[day] = (start, end)
    return by_day


def daily_steps(out: Output, device: str) -> dict[date, int]:
    totals: dict[date, int] = {}
    for record in out.of("steps", device):
        day = ts(record["start"]).astimezone(MSK).date()
        totals[day] = totals.get(day, 0) + record["count"]
    return totals


def active_minutes(out: Output, day: date) -> int:
    """Watch minutes with >= 100 steps (aligned output: one watch interval is one minute)."""
    return sum(
        1
        for r in out.of("steps", "watch-1")
        if r["count"] >= ACTIVE_STEPS and ts(r["start"]).astimezone(MSK).date() == day
    )


def resting_hr(out: Output, day: date) -> float | None:
    """10th percentile of the watch pulse in minutes without steps; None below 60 such minutes."""
    moving = {
        ts(r["start"]).replace(second=0) for r in out.of("steps", "watch-1") if r["count"] > 0
    }
    points: dict[datetime, list[int]] = {}
    for r in out.of("hr", "watch-1"):
        moment = ts(r["ts"])
        minute = moment.replace(second=0)
        if moment.astimezone(MSK).date() == day and minute not in moving:
            points.setdefault(minute, []).append(r["bpm"])
    if len(points) < 60:
        return None
    return statistics.quantiles([bpm for values in points.values() for bpm in values], n=10)[0]


def circular_stdev_minutes(moments: list[datetime]) -> float:
    """Stdev of the local time of day on the 24 h circle: 23:30 and 00:30 are 60 min apart."""
    angles = [
        2 * math.pi * (m.astimezone(MSK).hour * 60 + m.astimezone(MSK).minute) / 1440
        for m in moments
    ]
    c = sum(math.cos(a) for a in angles) / len(angles)
    s = sum(math.sin(a) for a in angles) / len(angles)
    return math.sqrt(-2 * math.log(math.hypot(c, s))) * 1440 / (2 * math.pi)
