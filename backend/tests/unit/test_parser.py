"""Streaming NDJSON parser (SPEC §7.2, docs/DATA_FORMAT.md)."""

import io
import json
from datetime import UTC, datetime, timedelta

import pytest

from app.services.ingest.parser import (
    DeviceMeta,
    HeartRate,
    Invalid,
    Line,
    Meta,
    Sleep,
    Steps,
    parse_lines,
)

META = {
    "type": "meta",
    "schema": "ht.v1",
    "generator": "htgen 0.1",
    "devices": [
        {"id": "watch-1", "kind": "watch", "name": "Часы"},
        {"id": "phone-1", "kind": "phone", "name": "Телефон"},
    ],
}
STEPS = {
    "type": "steps",
    "device": "watch-1",
    "start": "2026-10-01T08:00:30+03:00",
    "end": "2026-10-01T08:01:30+03:00",
    "count": 112,
}
SLEEP = {
    "type": "sleep",
    "device": "watch-1",
    "start": "2026-09-30T23:41:00+03:00",
    "end": "2026-10-01T07:12:00+03:00",
}
HR = {"type": "hr", "device": "watch-1", "ts": "2026-10-01T08:00:05Z", "bpm": 96}


def dump(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False)


def parse(text: str | bytes) -> list[Line]:
    data = text.encode("utf-8") if isinstance(text, str) else text
    return list(parse_lines(io.BytesIO(data)))


def records(text: str) -> list:
    return [line.record for line in parse(text)]


def only_record(record: dict):
    [parsed] = records(dump(record) + "\n")
    return parsed


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_valid_lines_parsed() -> None:
    text = "\n".join(dump(r) for r in (META, STEPS, SLEEP, HR)) + "\n"
    lines = parse(text)

    assert [line.number for line in lines] == [1, 2, 3, 4]
    assert [line.record for line in lines] == [
        Meta(
            devices=(
                DeviceMeta(external_id="watch-1", kind="watch", name="Часы"),
                DeviceMeta(external_id="phone-1", kind="phone", name="Телефон"),
            )
        ),
        Steps(
            device="watch-1",
            start=utc(2026, 10, 1, 5, 0, 30),
            end=utc(2026, 10, 1, 5, 1, 30),
            count=112,
        ),
        Sleep(device="watch-1", start=utc(2026, 9, 30, 20, 41), end=utc(2026, 10, 1, 4, 12)),
        HeartRate(device="watch-1", ts=utc(2026, 10, 1, 8, 0, 5), bpm=96),
    ]
    # Timestamps are in UTC whatever the offset in the file.
    steps = lines[1].record
    assert steps.start.utcoffset() == timedelta(0)
    # The last line may go without a terminator; CRLF and blank lines are accepted.
    assert records(dump(HR)) == [lines[3].record]
    crlf = parse(dump(STEPS) + "\r\n\r\n   \r\n" + dump(HR) + "\r\n")
    assert [(line.number, line.record) for line in crlf] == [
        (1, lines[1].record),
        (4, lines[3].record),
    ]
    # count 0 and the bpm bounds are valid; unknown extra fields are ignored.
    assert only_record({**STEPS, "count": 0}).count == 0
    assert only_record({**HR, "bpm": 30}).bpm == 30
    assert only_record({**HR, "bpm": 230}).bpm == 230
    assert isinstance(only_record({**HR, "extra": [1, 2]}), HeartRate)


def raw(record: dict) -> bytes:
    return dump(record).encode()


@pytest.mark.parametrize(
    "line",
    [
        b"{bad json",
        b"[1, 2, 3]",
        b'"steps"',
        b'{"type": "hr", "device": "w\xff", "ts": "2026-10-01T08:00:05Z", "bpm": 96}',  # not UTF-8
        raw({**STEPS, "type": "calories"}),
        raw({k: v for k, v in STEPS.items() if k != "count"}),
        raw({k: v for k, v in SLEEP.items() if k != "end"}),
        raw({k: v for k, v in HR.items() if k != "device"}),
        raw({**STEPS, "device": ""}),
        raw({**STEPS, "device": 7}),
        raw({**STEPS, "device": "a\x00b"}),  # Postgres text cannot hold NUL
        raw({**STEPS, "count": -1}),
        raw({**STEPS, "count": 1.5}),
        raw({**STEPS, "count": "12"}),
        raw({**STEPS, "count": True}),
        raw({**STEPS, "count": 2**31}),  # does not fit the int column
        raw({**HR, "bpm": 96.0}),
        raw({**STEPS, "start": "not a date"}),
        raw({**STEPS, "start": 1759294830}),
        raw({**META, "devices": [{"id": "w", "kind": "tablet", "name": "x"}]}),
        raw({**META, "devices": "watch-1"}),
    ],
)
def test_invalid_json_is_invalid(line: bytes) -> None:
    lines = list(parse_lines(io.BytesIO(line + b"\n" + raw(HR) + b"\n")))

    assert len(lines) == 2
    bad, good = lines
    assert bad.number == 1
    assert isinstance(bad.record, Invalid)
    assert bad.record.reason
    # A broken line does not stop the parser: the next line is read as usual.
    assert good.number == 2
    assert isinstance(good.record, HeartRate)


@pytest.mark.parametrize(
    "record",
    [
        {**STEPS, "start": "2026-10-01T08:00:30"},
        {**SLEEP, "end": "2026-10-01T07:12:00"},
        {**HR, "ts": "2026-10-01T08:00:05"},
        {**HR, "ts": "2026-10-01"},
    ],
)
def test_timestamp_without_offset_invalid(record: dict) -> None:
    parsed = only_record(record)
    assert isinstance(parsed, Invalid)
    assert "смещ" in parsed.reason


@pytest.mark.parametrize("kind", [STEPS, SLEEP])
def test_end_not_after_start_invalid(kind: dict) -> None:
    equal = only_record({**kind, "end": kind["start"]})
    reversed_ = only_record({**kind, "start": kind["end"], "end": kind["start"]})
    # The same instant in different offsets is still "end == start".
    same_instant = only_record(
        {**kind, "start": "2026-10-01T08:00:00+03:00", "end": "2026-10-01T05:00:00Z"}
    )
    for parsed in (equal, reversed_, same_instant):
        assert isinstance(parsed, Invalid)
        assert "end" in parsed.reason


@pytest.mark.parametrize("bpm", [0, 29, 231, 400, -5])
def test_bpm_out_of_range_invalid(bpm: int) -> None:
    parsed = only_record({**HR, "bpm": bpm})
    assert isinstance(parsed, Invalid)
    assert "bpm" in parsed.reason


@pytest.mark.parametrize("kind", [STEPS, SLEEP])
def test_interval_over_24h_invalid(kind: dict) -> None:
    start = "2026-10-01T00:00:00+03:00"
    exactly_24h = only_record({**kind, "start": start, "end": "2026-10-02T00:00:00+03:00"})
    over_24h = only_record({**kind, "start": start, "end": "2026-10-02T00:00:01+03:00"})
    # 24 h of real time across an offset change: 00:00+03:00 -> 21:00-04:00 is 28 h.
    over_by_offset = only_record({**kind, "start": start, "end": "2026-10-01T21:00:00-04:00"})

    assert not isinstance(exactly_24h, Invalid)
    for parsed in (over_24h, over_by_offset):
        assert isinstance(parsed, Invalid)
        assert "24" in parsed.reason


def test_byte_offsets_tracked() -> None:
    # Multi-byte UTF-8 (Cyrillic names), CRLF, a blank line and a UTF-8 BOM at the start.
    chunks = [
        "﻿".encode() + dump(META).encode() + b"\r\n",
        dump(STEPS).encode() + b"\n",
        b"\n",
        b"{oops\n",
        dump(HR).encode(),  # no terminator at the end of the file
    ]
    data = b"".join(chunks)
    lines = parse(data)

    starts = [sum(len(c) for c in chunks[:i]) for i in range(len(chunks) + 1)]
    assert [(ln.number, ln.offset, ln.end_offset) for ln in lines] == [
        (1, starts[0], starts[1]),
        (2, starts[1], starts[2]),
        (4, starts[3], starts[4]),
        (5, starts[4], starts[5]),
    ]
    assert lines[-1].end_offset == len(data)

    # Resuming from a saved offset (a checkpoint) gives the same lines as reading from the start.
    resumed_from = lines[1].end_offset
    stream = io.BytesIO(data)
    stream.seek(resumed_from)
    resumed = list(parse_lines(stream, start_offset=resumed_from, first_line=3))
    assert resumed == lines[2:]
