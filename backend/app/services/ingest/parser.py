"""Streaming NDJSON parser of the `ht.v1` format (SPEC §7.2, docs/DATA_FORMAT.md).

Reads the file line by line, so memory does not depend on the file size. Every non-blank line
becomes one `Line` with its number, byte offsets and either a valid record or `Invalid` with the
reason. Timestamps are converted to UTC.

Accepted besides the plain format (ADR-030): `\\r\\n` line ends, blank lines (skipped, but they
count in line numbers), a UTF-8 BOM at the start of the file and unknown extra fields.
Reasons are in Russian: they reach the upload report in the UI.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import BinaryIO, Literal, cast

DeviceKind = Literal["watch", "phone"]

DEVICE_KINDS: tuple[DeviceKind, ...] = ("watch", "phone")
# A longer line is invalid and is skipped in chunks, never read into memory whole.
MAX_LINE_BYTES = 1 << 20
MAX_INTERVAL = timedelta(hours=24)
BPM_MIN, BPM_MAX = 30, 230
COUNT_MAX = 2**31 - 1  # steps_raw.count is int
BOM = b"\xef\xbb\xbf"


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
    offset = start_offset
    number = first_line - 1
    while raw := stream.readline(MAX_LINE_BYTES + 1):
        number += 1
        line_start = offset
        offset += len(raw)
        if len(raw) > MAX_LINE_BYTES and not raw.endswith(b"\n"):
            offset += _skip_rest_of_line(stream)
            reason = f"строка длиннее {MAX_LINE_BYTES // 1024} КиБ"
            yield Line(number, line_start, offset, Invalid(reason))
            continue
        if line_start == 0 and raw.startswith(BOM):
            raw = raw[len(BOM) :]
        body = raw.strip()
        if body:
            yield Line(number, line_start, offset, parse_line(body))


def _skip_rest_of_line(stream: BinaryIO) -> int:
    skipped = 0
    while chunk := stream.readline(MAX_LINE_BYTES):
        skipped += len(chunk)
        if chunk.endswith(b"\n"):
            break
    return skipped


def parse_line(body: bytes) -> Record:
    """One NDJSON line without its terminator."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return Invalid("строка не в кодировке UTF-8")
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        return Invalid("некорректный JSON")
    return parse_record(data)


def parse_record(data: object) -> Record:
    """A decoded JSON value checked against SPEC §7.2. Also serves stream batches (step 11.1)."""
    try:
        return _record(data)
    except _BadRecord as exc:
        return Invalid(str(exc))


class _BadRecord(Exception):
    pass


def _record(data: object) -> Record:
    if not isinstance(data, dict):
        raise _BadRecord("запись должна быть JSON-объектом")
    fields = cast(dict[str, object], data)
    kind = fields.get("type")
    if kind == "steps":
        start, end = _interval(fields)
        count = _int(fields, "count")
        if count < 0:
            raise _BadRecord("count не может быть меньше 0")
        if count > COUNT_MAX:
            raise _BadRecord(f"count больше {COUNT_MAX}")
        return Steps(_text(fields, "device"), start, end, count)
    if kind == "sleep":
        start, end = _interval(fields)
        return Sleep(_text(fields, "device"), start, end)
    if kind == "hr":
        bpm = _int(fields, "bpm")
        if not BPM_MIN <= bpm <= BPM_MAX:
            raise _BadRecord(f"bpm вне диапазона {BPM_MIN}–{BPM_MAX}: {bpm}")
        return HeartRate(_text(fields, "device"), _moment(fields, "ts"), bpm)
    if kind == "meta":
        return _meta(fields)
    if "type" not in fields:
        raise _BadRecord("нет поля «type»")
    raise _BadRecord(f"неизвестный тип записи: {json.dumps(kind, ensure_ascii=False)[:40]}")


def _meta(fields: dict[str, object]) -> Meta:
    items = _field(fields, "devices")
    if not isinstance(items, list):
        raise _BadRecord("поле «devices» должно быть списком")
    devices = []
    for item in items:
        if not isinstance(item, dict):
            raise _BadRecord("устройство в «devices» должно быть JSON-объектом")
        device = cast(dict[str, object], item)
        external_id = _text(device, "id")
        kind = device.get("kind")
        if kind not in DEVICE_KINDS:
            raise _BadRecord(f"устройство «{external_id}»: kind должен быть watch или phone")
        name = _text(device, "name") if "name" in device else external_id
        devices.append(DeviceMeta(external_id, cast(DeviceKind, kind), name))
    return Meta(tuple(devices))


def _field(fields: dict[str, object], name: str) -> object:
    if name not in fields:
        raise _BadRecord(f"нет поля «{name}»")
    return fields[name]


def _text(fields: dict[str, object], name: str) -> str:
    value = _field(fields, name)
    if not isinstance(value, str) or not value:
        raise _BadRecord(f"поле «{name}» должно быть непустой строкой")
    if "\x00" in value:
        raise _BadRecord(f"поле «{name}» содержит символ NUL")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:  # a lone surrogate from a JSON escape like "\ud800"
        raise _BadRecord(f"поле «{name}»: недопустимый символ") from None
    return value


def _int(fields: dict[str, object], name: str) -> int:
    value = _field(fields, name)
    # bool is an int in Python, but `true` is not a number in JSON.
    if type(value) is not int:
        raise _BadRecord(f"поле «{name}» должно быть целым числом")
    return value


def _moment(fields: dict[str, object], name: str) -> datetime:
    value = _field(fields, name)
    if not isinstance(value, str):
        raise _BadRecord(f"поле «{name}» должно быть строкой ISO 8601")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        raise _BadRecord(f"поле «{name}»: не метка времени ISO 8601") from None
    if moment.tzinfo is None:
        raise _BadRecord(f"поле «{name}»: метка времени без смещения (+03:00 или Z)")
    try:
        return moment.astimezone(UTC)
    except OverflowError:
        raise _BadRecord(f"поле «{name}»: метка времени вне допустимого диапазона") from None


def _interval(fields: dict[str, object]) -> tuple[datetime, datetime]:
    start = _moment(fields, "start")
    end = _moment(fields, "end")
    if end <= start:
        raise _BadRecord("end должен быть позже start")
    if end - start > MAX_INTERVAL:
        raise _BadRecord("интервал длиннее 24 ч")
    return start, end
