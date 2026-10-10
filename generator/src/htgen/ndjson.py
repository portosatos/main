"""Meta line of docs/DATA_FORMAT.md: compact JSON (records are written by htgen.devices)."""

from __future__ import annotations

import json
from collections.abc import Iterable

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
