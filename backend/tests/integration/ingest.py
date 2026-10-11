"""Helpers of the ingest tests: a user, NDJSON bytes and one upload through the parser and
the classifier."""

import io
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserTimezone
from app.services.ingest.classify import BATCH_SIZE, Counts, ingest_records
from app.services.ingest.jobs import create_ingest_job
from app.services.ingest.parser import parse_lines

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


async def make_user(
    session: AsyncSession, email: str = "ingest@example.com", tz: str | None = "UTC"
) -> uuid.UUID:
    """A user registered at NOW in the zone `tz` (the first zone also covers the earlier data);
    tz=None: the test writes the time zone history itself."""
    # A dummy hash: these tests never log in.
    user = User(email=email, password_hash="x", notify_email=email, created_at=NOW)
    session.add(user)
    await session.flush()
    if tz is not None:
        session.add(UserTimezone(user_id=user.id, tz=tz, valid_from=NOW, created_at=NOW))
        await session.flush()
    return user.id


def ndjson(*records: dict[str, Any]) -> bytes:
    return b"".join(json.dumps(r, ensure_ascii=False).encode() + b"\n" for r in records)


async def upload(
    session: AsyncSession,
    user_id: uuid.UUID,
    data: bytes,
    *,
    batch_size: int = BATCH_SIZE,
) -> tuple[uuid.UUID, Counts]:
    """One upload of `data` as a new job: parse, classify, store. Returns the job id and counts."""
    job_id = await create_ingest_job(
        session, user_id=user_id, source="file", filename="test.ndjson", now=NOW
    )
    counts = await ingest_records(
        session,
        user_id=user_id,
        job_id=job_id,
        now=NOW,
        lines=parse_lines(io.BytesIO(data)),
        batch_size=batch_size,
    )
    return job_id, counts


async def rows(session: AsyncSession, query: str, **params: Any) -> list[tuple]:
    return [tuple(row) for row in (await session.execute(text(query), params)).all()]


async def steps_rows(session: AsyncSession, user_id: uuid.UUID) -> list[tuple]:
    """(external_id, start_utc, end_utc, count) of the user's stored step intervals."""
    return await rows(
        session,
        "SELECT d.external_id, s.start_utc, s.end_utc, s.count FROM steps_raw s "
        "JOIN devices d ON d.id = s.device_id WHERE d.user_id = :u ORDER BY 1, 2",
        u=user_id,
    )


async def sleep_rows(session: AsyncSession, user_id: uuid.UUID) -> list[tuple]:
    return await rows(
        session,
        "SELECT d.external_id, s.start_utc, s.end_utc FROM sleep_raw s "
        "JOIN devices d ON d.id = s.device_id WHERE d.user_id = :u ORDER BY 1, 2, 3",
        u=user_id,
    )


async def hr_rows(session: AsyncSession, user_id: uuid.UUID) -> list[tuple]:
    return await rows(
        session,
        "SELECT d.external_id, h.ts_utc, h.bpm FROM hr_point h "
        "JOIN devices d ON d.id = h.device_id WHERE d.user_id = :u ORDER BY 1, 2",
        u=user_id,
    )


async def device_rows(session: AsyncSession, user_id: uuid.UUID) -> list[tuple]:
    """(external_id, kind, name) of the user's devices."""
    return await rows(
        session,
        "SELECT external_id, kind::text, name FROM devices WHERE user_id = :u ORDER BY 1",
        u=user_id,
    )


# Derived minute tables (step 3.3), keyed by the device's external id.


async def steps_minute_rows(session: AsyncSession, user_id: uuid.UUID) -> dict[tuple, float]:
    """{(external_id, minute_utc): steps} of the user's devices."""
    found = await rows(
        session,
        "SELECT d.external_id, m.minute_utc, m.steps FROM steps_minute m "
        "JOIN devices d ON d.id = m.device_id WHERE d.user_id = :u",
        u=user_id,
    )
    return {(external_id, minute): steps for external_id, minute, steps in found}


async def sleep_minute_rows(session: AsyncSession, user_id: uuid.UUID) -> set[tuple]:
    """{(external_id, minute_utc)} of the user's devices."""
    return set(
        await rows(
            session,
            "SELECT d.external_id, m.minute_utc FROM sleep_minute m "
            "JOIN devices d ON d.id = m.device_id WHERE d.user_id = :u",
            u=user_id,
        )
    )


async def coverage_minute_rows(session: AsyncSession, user_id: uuid.UUID) -> set[tuple]:
    """{(external_id, minute_utc)} of the user's devices."""
    return set(
        await rows(
            session,
            "SELECT d.external_id, m.minute_utc FROM coverage_minute m "
            "JOIN devices d ON d.id = m.device_id WHERE d.user_id = :u",
            u=user_id,
        )
    )


DERIVED_TABLES = {
    "steps_minute": "format('%s|%s|%s', d.external_id, m.minute_utc, m.steps)",
    "sleep_minute": "format('%s|%s', d.external_id, m.minute_utc)",
    "coverage_minute": "format('%s|%s', d.external_id, m.minute_utc)",
}


async def derived_hashes(session: AsyncSession, user_id: uuid.UUID) -> dict[str, tuple[int, str]]:
    """{table: (row count, md5 of the ordered rows)} of the user's derived minute tables."""
    result = {}
    for table, row in DERIVED_TABLES.items():
        [(count, digest)] = await rows(
            session,
            f"SELECT count(*), md5(coalesce(string_agg({row}, ',' "
            f"ORDER BY d.external_id, m.minute_utc), '')) FROM {table} m "
            "JOIN devices d ON d.id = m.device_id WHERE d.user_id = :u",
            u=user_id,
        )
        result[table] = (count, digest)
    return result
