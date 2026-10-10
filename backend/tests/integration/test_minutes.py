"""Derived minute tables: steps_minute, sleep_minute, coverage_minute (SPEC F4.3).

Uploads go through the classifier, which recomputes the touched minutes after every batch.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services import minutes
from app.services.ingest.classify import BATCH_SIZE
from tests.integration.ingest import (
    coverage_minute_rows,
    derived_hashes,
    make_user,
    ndjson,
    rows,
    sleep_minute_rows,
    steps_minute_rows,
    upload,
)

META = {
    "type": "meta",
    "schema": "ht.v1",
    "devices": [
        {"id": "watch-1", "kind": "watch", "name": "Часы"},
        {"id": "phone-1", "kind": "phone", "name": "Телефон"},
    ],
}


@pytest.fixture
async def session(
    test_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with test_sessionmaker() as session:
        yield session


def utc(hour: int, minute: int, day: int = 1) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=UTC)


def steps(device: str, start: str, end: str, count: int) -> dict:
    return {"type": "steps", "device": device, "start": start, "end": end, "count": count}


def sleep(device: str, start: str, end: str) -> dict:
    return {"type": "sleep", "device": device, "start": start, "end": end}


def hr(device: str, ts: str, bpm: int) -> dict:
    return {"type": "hr", "device": device, "ts": ts, "bpm": bpm}


async def device_id(session: AsyncSession, user_id: uuid.UUID, external_id: str) -> uuid.UUID:
    [(found,)] = await rows(
        session,
        "SELECT id FROM devices WHERE user_id = :u AND external_id = :e",
        u=user_id,
        e=external_id,
    )
    return found


@pytest.mark.parametrize("batch_size", [1, BATCH_SIZE])
async def test_adjacent_unaligned_intervals_minute_0801_equals_60(
    session: AsyncSession, batch_size: int
) -> None:
    # The example of SPEC F4.3; with batch_size=1 the second interval comes in its own batch and
    # minute 08:01 must still add up both contributions.
    user_id = await make_user(session)
    data = ndjson(
        META,
        steps("watch-1", "2026-10-01T08:00:30+03:00", "2026-10-01T08:01:30+03:00", 60),
        steps("watch-1", "2026-10-01T08:01:30+03:00", "2026-10-01T08:02:30+03:00", 60),
    )

    await upload(session, user_id, data, batch_size=batch_size)

    assert await steps_minute_rows(session, user_id) == {
        ("watch-1", utc(5, 0)): pytest.approx(30),
        ("watch-1", utc(5, 1)): pytest.approx(60),
        ("watch-1", utc(5, 2)): pytest.approx(30),
    }


# Non-overlapping intervals of one device: (gap after the previous end, length, count) in seconds.
INTERVALS = st.lists(
    st.tuples(st.integers(0, 600), st.integers(1, 3 * 3600), st.integers(0, 20_000)),
    min_size=1,
    max_size=40,
)


@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(spec=INTERVALS, first_second=st.integers(0, 59), batch_size=st.integers(1, 50))
async def test_sum_steps_minute_equals_sum_raw(
    session: AsyncSession,
    spec: list[tuple[int, int, int]],
    first_second: int,
    batch_size: int,
) -> None:
    # Every example has a user of its own inside the test transaction.
    user_id = await make_user(session, email=f"{uuid.uuid4().hex}@example.com")
    records = []
    end = datetime(2026, 10, 1, 8, 0, first_second, tzinfo=UTC)
    for gap, length, count in spec:
        start = end + timedelta(seconds=gap)
        end = start + timedelta(seconds=length)
        records.append(steps("watch-1", start.isoformat(), end.isoformat(), count))

    _, counts = await upload(session, user_id, ndjson(META, *records), batch_size=batch_size)

    assert counts.new == len(records)
    values = (await steps_minute_rows(session, user_id)).values()
    assert all(value >= 0 for value in values)
    total = sum(count for _, _, count in spec)
    assert sum(values) == pytest.approx(total, rel=1e-6, abs=1e-6)


async def test_sleep_minute_marked_if_covered_30s_or_more(session: AsyncSession) -> None:
    user_id = await make_user(session)
    data = ndjson(
        META,
        # 23:00 is covered for 30 s (marked), 23:01 fully, 23:02 for 10 s (not marked).
        sleep("watch-1", "2026-10-01T23:00:30Z", "2026-10-01T23:02:10Z"),
        # Overlapping intervals count once: 25 s together, though 20 + 15 = 35.
        sleep("watch-1", "2026-10-01T23:10:00Z", "2026-10-01T23:10:20Z"),
        sleep("watch-1", "2026-10-01T23:10:10Z", "2026-10-01T23:10:25Z"),
        # Disjoint pieces of one minute add up: 20 + 15 = 35 s.
        sleep("watch-1", "2026-10-01T23:20:00Z", "2026-10-01T23:20:20Z"),
        sleep("watch-1", "2026-10-01T23:20:40Z", "2026-10-01T23:20:55Z"),
        # The threshold: 29 s is not enough, exactly 30 s is.
        sleep("watch-1", "2026-10-01T23:30:00Z", "2026-10-01T23:30:29Z"),
        sleep("watch-1", "2026-10-01T23:31:00Z", "2026-10-01T23:31:30Z"),
        # Another device has minutes of its own.
        sleep("phone-1", "2026-10-01T23:00:00Z", "2026-10-01T23:01:00Z"),
    )

    await upload(session, user_id, data)

    assert await sleep_minute_rows(session, user_id) == {
        ("watch-1", utc(23, 0)),
        ("watch-1", utc(23, 1)),
        ("watch-1", utc(23, 20)),
        ("watch-1", utc(23, 31)),
        ("phone-1", utc(23, 0)),
    }


async def test_coverage_from_steps_sleep_and_hr(session: AsyncSession) -> None:
    user_id = await make_user(session)
    data = ndjson(
        META,
        # A step interval with 0 steps still covers 10:00 and 10:01; its end 10:02:00 is excluded.
        steps("watch-1", "2026-10-01T10:00:30Z", "2026-10-01T10:02:00Z", 0),
        # Any overlap with a minute counts, even the 5 s of 11:01 (not a sleep minute).
        sleep("watch-1", "2026-10-01T11:00:50Z", "2026-10-01T11:01:05Z"),
        # Pulse points cover their minute; two points of one minute make one row.
        hr("watch-1", "2026-10-01T12:00:05Z", 70),
        hr("watch-1", "2026-10-01T12:00:59Z", 72),
        hr("phone-1", "2026-10-01T13:05:00Z", 80),
    )

    await upload(session, user_id, data)

    assert await coverage_minute_rows(session, user_id) == {
        ("watch-1", utc(10, 0)),
        ("watch-1", utc(10, 1)),
        ("watch-1", utc(11, 0)),
        ("watch-1", utc(11, 1)),
        ("watch-1", utc(12, 0)),
        ("phone-1", utc(13, 5)),
    }
    # 10 s of 11:00 and 5 s of 11:01: covered, but not sleep minutes.
    assert await sleep_minute_rows(session, user_id) == set()


async def test_recompute_idempotent(session: AsyncSession) -> None:
    user_id = await make_user(session)
    data = ndjson(
        META,
        steps("watch-1", "2026-10-01T08:00:30Z", "2026-10-01T08:03:10Z", 160),
        steps("watch-1", "2026-10-01T08:03:10Z", "2026-10-01T08:05:00Z", 50),
        steps("phone-1", "2026-10-01T08:00:00Z", "2026-10-01T08:10:00Z", 600),
        sleep("watch-1", "2026-10-01T01:00:20Z", "2026-10-01T02:30:40Z"),
        hr("watch-1", "2026-10-01T09:00:05Z", 70),
    )
    await upload(session, user_id, data)
    before = await derived_hashes(session, user_id)
    assert all(count > 0 for count, _ in before.values())
    watch = await device_id(session, user_id, "watch-1")
    phone = await device_id(session, user_id, "phone-1")

    # The whole day of both devices, twice: nothing changes.
    for _ in range(2):
        dirty = minutes.DirtyMinutes()
        dirty.add(watch, utc(0, 0), utc(0, 0, day=2))
        dirty.add(phone, utc(0, 0), utc(0, 0, day=2))
        await minutes.recompute(session, dirty)
        assert await derived_hashes(session, user_id) == before

    # Only the dirty range is rewritten: a spoiled minute outside it stays spoiled ...
    spoil = text("UPDATE steps_minute SET steps = 999 WHERE device_id = :d AND minute_utc = :m")
    await session.execute(spoil, {"d": watch, "m": utc(8, 4)})
    dirty = minutes.DirtyMinutes()
    dirty.add(watch, utc(8, 0), utc(8, 2))
    await minutes.recompute(session, dirty)
    assert (await steps_minute_rows(session, user_id))[("watch-1", utc(8, 4))] == 999
    # ... until a recompute covers it.
    dirty = minutes.DirtyMinutes()
    dirty.add_point(watch, utc(8, 4) + timedelta(seconds=30))
    await minutes.recompute(session, dirty)
    assert await derived_hashes(session, user_id) == before
