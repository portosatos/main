"""NDJSON lines of docs/DATA_FORMAT.md: compact JSON, timestamps with the local offset."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from zoneinfo import ZoneInfo

from htgen import GENERATOR, SCHEMA
from htgen.config import Device


def meta_line(devices: Iterable[Device]) -> str:
    meta = {
        "type": "meta",
        "schema": SCHEMA,
        "generator": GENERATOR,
        "devices": [{"id": d.id, "kind": d.kind, "name": d.name} for d in devices],
    }
    return json.dumps(meta, ensure_ascii=False, separators=(",", ":"))


def iso(moment: datetime, zone: ZoneInfo) -> str:
    """2026-10-01T08:00:30+03:00: seconds precision, offset of the zone at that moment."""
    return moment.astimezone(zone).isoformat(timespec="seconds")
