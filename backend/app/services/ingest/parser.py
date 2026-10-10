"""Streaming NDJSON parser of the `ht.v1` format (SPEC §7.2, docs/DATA_FORMAT.md).

Reads the file line by line, so memory does not depend on the file size. Every non-blank line
becomes one `Line` with its number, byte offsets and either a valid record or `Invalid` with the
reason. Timestamps are converted to UTC.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, Literal

DeviceKind = Literal["watch", "phone"]


@dataclass(frozen=True, slots=True)
class DeviceMeta:
    external_id: str
    kind: DeviceKind
    name: str


@dataclass(frozen=True, slots=True)
class Meta:
    devices: tuple[DeviceMeta, ...]


@dataclass(frozen=True, slots=True)
class Steps:
    device: str
    start: datetime
    end: datetime
    count: int


@dataclass(frozen=True, slots=True)
class Sleep:
    device: str
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class HeartRate:
    device: str
    ts: datetime
    bpm: int


@dataclass(frozen=True, slots=True)
class Invalid:
    reason: str


Record = Meta | Steps | Sleep | HeartRate | Invalid


@dataclass(frozen=True, slots=True)
class Line:
    number: int  # 1-based, blank lines count too
    offset: int  # byte offset of the line start
    end_offset: int  # byte offset right after the line terminator: where the next line starts
    record: Record


def parse_lines(stream: BinaryIO, *, start_offset: int = 0, first_line: int = 1) -> Iterator[Line]:
    """Lines of `stream`, which is positioned at byte `start_offset` (the start of line
    `first_line`). Blank lines are skipped."""
    raise NotImplementedError("step 3.1")
