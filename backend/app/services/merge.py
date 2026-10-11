"""Merging the devices of a user minute by minute: the watch beats the phone (SPEC F4.4, ADR-007).

Every merged minute takes its value from exactly one device and says which one
(`source_device_id`), so the "never a sum" invariant can be checked.
- Steps: the minute's source is the first device in priority order that covers the minute
  (coverage_minute); its value is that device's steps, or 0 if it has no steps there.
  A minute that no device covers has no data and is absent from the result.
- Pulse: the minute's source is the first device in priority order that has pulse in that minute,
  so phone points are used only where no watch has any.
- Priority: watches before phones; among devices of one kind the earlier registered one.
"""

import uuid
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class DeviceLike(Protocol):
    """A device of the user. Device rows fit."""

    @property
    def id(self) -> uuid.UUID: ...

    @property
    def kind(self) -> str: ...

    @property
    def external_id(self) -> str: ...

    @property
    def created_at(self) -> datetime: ...


@dataclass(frozen=True, slots=True)
class Merged[T]:
    """The merged value of a minute and the one device it was taken from."""

    value: T
    source_device_id: uuid.UUID


def device_order(devices: Iterable[DeviceLike]) -> list[uuid.UUID]:
    """Device ids from the highest priority to the lowest."""
    raise NotImplementedError("step 4.2")


def merge_steps(
    order: Sequence[uuid.UUID],
    coverage: Mapping[uuid.UUID, Collection[datetime]],
    steps: Mapping[uuid.UUID, Mapping[datetime, float]],
) -> dict[datetime, Merged[float]]:
    """Steps of every covered minute: {minute_utc: Merged(steps, source)}."""
    raise NotImplementedError("step 4.2")


def merge_hr[T](
    order: Sequence[uuid.UUID], hr: Mapping[uuid.UUID, Mapping[datetime, T]]
) -> dict[datetime, Merged[T]]:
    """Pulse of every minute that has any: {minute_utc: Merged(pulse of the minute, source)}."""
    raise NotImplementedError("step 4.2")
