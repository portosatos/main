"""Receiving an uploaded file: the `file` part of a multipart body goes straight to disk (SPEC F3).

The body is parsed while it streams in, so neither memory nor a temporary copy grows with the
file; the size limit is checked on the bytes actually received.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

import anyio
from python_multipart import MultipartParser
from python_multipart.multipart import parse_options_header

FILE_FIELD = "file"


class UploadError(Exception):
    """The body is not a multipart form with a `file` part."""


class UploadTooLarge(Exception):
    """The file is larger than the limit."""


@dataclass(frozen=True)
class ReceivedFile:
    filename: str
    size: int


def multipart_boundary(content_type: str) -> bytes:
    kind, params = parse_options_header(content_type)
    boundary = params.get(b"boundary")
    if kind != b"multipart/form-data" or not boundary:
        raise UploadError("Ожидается multipart/form-data с полем file")
    return boundary


@dataclass
class _Parts:
    """State of the parser callbacks: which part we are in and the file bytes not yet written."""

    header_field: bytearray = field(default_factory=bytearray)
    header_value: bytearray = field(default_factory=bytearray)
    headers: dict[str, str] = field(default_factory=dict)
    in_file: bool = False
    seen_file: bool = False
    filename: str = ""
    pending: list[bytes] = field(default_factory=list)

    def callbacks(self) -> dict:
        return {
            "on_part_begin": self.part_begin,
            "on_header_field": lambda d, s, e: self.header_field.extend(d[s:e]),
            "on_header_value": lambda d, s, e: self.header_value.extend(d[s:e]),
            "on_header_end": self.header_end,
            "on_headers_finished": self.headers_finished,
            "on_part_data": self.part_data,
            "on_part_end": self.part_end,
        }

    def part_begin(self) -> None:
        self.headers = {}

    def header_end(self) -> None:
        name = self.header_field.decode("latin-1").lower()
        self.headers[name] = self.header_value.decode("utf-8", "replace")
        self.header_field.clear()
        self.header_value.clear()

    def headers_finished(self) -> None:
        _, params = parse_options_header(self.headers.get("content-disposition", ""))
        is_file = params.get(b"name") == FILE_FIELD.encode() and not self.seen_file
        self.in_file = is_file
        if is_file:
            self.seen_file = True
            self.filename = Path(params.get(b"filename", b"").decode("utf-8", "replace")).name

    def part_data(self, data: bytes, start: int, end: int) -> None:
        if self.in_file:
            self.pending.append(bytes(data[start:end]))

    def part_end(self) -> None:
        self.in_file = False


async def receive_file(
    chunks: AsyncIterator[bytes], *, boundary: bytes, target: Path, max_bytes: int
) -> ReceivedFile:
    """Write the `file` part of the multipart body in `chunks` to `target`.

    Raises UploadTooLarge as soon as more than `max_bytes` file bytes arrive and UploadError
    when there is no `file` part; `target` may then be left partially written (the caller
    deletes it)."""
    parts = _Parts()
    parser = MultipartParser(boundary, parts.callbacks())
    size = 0
    async with await anyio.open_file(target, "wb") as out:
        async for chunk in chunks:
            parser.write(chunk)
            for piece in parts.pending:
                size += len(piece)
                if size > max_bytes:
                    raise UploadTooLarge
                await out.write(piece)
            parts.pending.clear()
        parser.finalize()
    if not parts.seen_file:
        raise UploadError("В запросе нет поля file")
    return ReceivedFile(parts.filename, size)
