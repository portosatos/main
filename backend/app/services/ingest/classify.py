"""Classification of parsed records into new / duplicate / conflict / invalid (SPEC F4.2).

Records go in batches: a batch is copied into staging tables, compared with the stored raw
records by SQL, duplicates inside the batch are collapsed, and only `new` records are inserted.
On a conflict the first loaded record wins.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ingest.parser import Line

BATCH_SIZE = 5000
# Errors (invalid and conflicting lines) kept in the report; the counters count all of them.
ERRORS_LIMIT = 50


@dataclass(frozen=True, slots=True)
class IngestError:
    line: int
    kind: Literal["invalid", "conflict"]
    reason: str


@dataclass(slots=True)
class Counts:
    new: int = 0
    duplicate: int = 0
    conflict: int = 0
    invalid: int = 0
    errors: list[IngestError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.new + self.duplicate + self.conflict + self.invalid


async def ingest_records(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    now: datetime,
    lines: Iterable[Line],
    batch_size: int = BATCH_SIZE,
) -> Counts:
    """Classify and store the records of `lines` for the user; `now` (from Clock) becomes
    `ingested_at`. Devices are created on first sight. Does not commit."""
    raise NotImplementedError("step 3.1")
