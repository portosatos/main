"""What to generate: period, devices and options of one htgen run."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta


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


@dataclass(frozen=True)
class Config:
    first: date  # inclusive local dates
    last: date
    seed: int = 0
    devices: tuple[Device, ...] = (WATCH, PHONE)
    hr_interval: int = 5  # seconds between watch pulse points
    unaligned: bool = False
    tz: str = DEFAULT_TZ

    def days(self) -> Iterator[date]:
        day = self.first
        while day <= self.last:
            yield day
            day += timedelta(days=1)

    def has(self, device: Device) -> bool:
        return device in self.devices
