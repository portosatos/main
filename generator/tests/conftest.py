"""Helpers: run htgen in-process and read its NDJSON output."""

from __future__ import annotations

import json
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
