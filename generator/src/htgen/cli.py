"""Command line interface: htgen --days 7 --seed 1 --out sample.ndjson"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date


def resolve_period(
    start: date | None, end: date | None, days: int | None, today: date
) -> tuple[date, date]:
    """Inclusive local dates [first, last] of the generated period."""
    raise NotImplementedError("step 2.1")


def main(argv: Sequence[str] | None = None) -> int:
    raise NotImplementedError("step 2.1")
