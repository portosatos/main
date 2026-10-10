"""What to generate: period, devices and options of one htgen run."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from htgen.gaps import Gap
from htgen.scenarios import Scenarios
from htgen.timeline import Timeline


@dataclass(frozen=True)
class Device:
    id: str
    kind: str
    name: str


WATCH = Device("watch-1", "watch", "Часы")
PHONE = Device("phone-1", "phone", "Телефон")
DEVICES = {"watch": WATCH, "phone": PHONE}

DEFAULT_TZ = "Europe/Moscow"
DEFAULT_DAYS = 7
DEFAULT_GAP_MAX_HOURS = 30.0


@dataclass(frozen=True)
class Config:
    first: date  # inclusive local dates
    last: date
    seed: int = 0
    devices: tuple[Device, ...] = (WATCH, PHONE)
    hr_interval: int = 5  # seconds between watch pulse points
    unaligned: bool = False
    tz: str = DEFAULT_TZ
    tz_changes: tuple[tuple[datetime, str], ...] = ()  # (instant, IANA zone from then on)
    gaps: tuple[Gap, ...] = ()  # explicit, --gap
    gap_prob: float = 0.0  # random gaps: chance that a gap of a device starts on a date
    gap_max_hours: float = DEFAULT_GAP_MAX_HOURS
    scenarios: frozenset[str] = frozenset()  # --scenario names

    def days(self) -> Iterator[date]:
        day = self.first
        while day <= self.last:
            yield day
            day += timedelta(days=1)

    def timeline(self) -> Timeline:
        return Timeline(self.tz, self.tz_changes)

    def scenario_plan(self) -> Scenarios:
        return Scenarios(self.scenarios, self.first, self.last)

    def has(self, device: Device) -> bool:
        return device in self.devices
