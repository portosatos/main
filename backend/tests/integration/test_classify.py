"""Classification of incoming records: new / duplicate / conflict / invalid (SPEC F4.1, F4.2)."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.integration.ingest import (
    NOW,
    device_rows,
    hr_rows,
    make_user,
    ndjson,
    rows,
    sleep_rows,
    steps_rows,
    upload,
)

META = {
    "type": "meta",
    "schema": "ht.v1",
    "generator": "test",
    "devices": [
        {"id": "watch-1", "kind": "watch", "name": "Часы"},
        {"id": "phone-1", "kind": "phone", "name": "Телефон"},
    ],
}


def steps(start: str, end: str, count: int, device: str = "watch-1") -> dict:
    return {
        "type": "steps",
        "device": device,
        "start": f"2026-10-01T{start}+03:00",
        "end": f"2026-10-01T{end}+03:00",
        "count": count,
    }


def sleep(start: str, end: str, device: str = "watch-1") -> dict:
    return {
        "type": "sleep",
        "device": device,
        "start": f"2026-10-01T{start}+03:00",
        "end": f"2026-10-01T{end}+03:00",
    }


def hr(ts: str, bpm: int, device: str = "watch-1") -> dict:
    return {"type": "hr", "device": device, "ts": f"2026-10-01T{ts}+03:00", "bpm": bpm}


def utc(hour: int, minute: int, second: int = 0) -> datetime:
    """A moment of 2026-10-01 in UTC (the test data is +03:00)."""
    return datetime(2026, 10, 1, hour, minute, second, tzinfo=UTC)


def eve(hour: int, minute: int) -> datetime:
    """A moment of 2026-09-30 in UTC: 00:00-02:59 +03:00 of 2026-10-01 falls there."""
    return datetime(2026, 9, 30, hour, minute, tzinfo=UTC)


@pytest.fixture
async def session(
    test_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with test_sessionmaker() as session:
        yield session


@pytest.fixture
async def user_id(session: AsyncSession):
    return await make_user(session)


async def test_new_records_inserted(session: AsyncSession, user_id) -> None:
    data = ndjson(
        META,
        steps("08:00:30", "08:01:30", 112),
        sleep("00:10", "07:12"),
        hr("08:00:05", 96),
        steps("08:00", "08:05", 530, device="phone-1"),
    )
    job_id, counts = await upload(session, user_id, data)

    assert (counts.new, counts.duplicate, counts.conflict, counts.invalid) == (4, 0, 0, 0)
    assert counts.total == 4
    assert counts.errors == []
    assert await steps_rows(session, user_id) == [
        ("phone-1", utc(5, 0), utc(5, 5), 530),
        ("watch-1", utc(5, 0, 30), utc(5, 1, 30), 112),
    ]
    assert await sleep_rows(session, user_id) == [("watch-1", eve(21, 10), utc(4, 12))]
    assert await hr_rows(session, user_id) == [("watch-1", utc(5, 0, 5), 96)]
    # Every raw record knows where it came from (SPEC F4.1).
    for table in ("steps_raw", "sleep_raw", "hr_point"):
        origin = await rows(session, f"SELECT DISTINCT ingest_job_id, ingested_at FROM {table}")
        assert origin == [(job_id, NOW)], table


async def test_same_key_same_value_duplicate(session: AsyncSession, user_id) -> None:
    data = ndjson(META, steps("08:00", "08:01", 50), sleep("01:00", "06:00"), hr("08:00:05", 96))
    await upload(session, user_id, data)
    before = (
        await steps_rows(session, user_id),
        await sleep_rows(session, user_id),
        await hr_rows(session, user_id),
    )

    _, again = await upload(session, user_id, data)
    # The same moments written with another offset are the same keys.
    _, in_utc = await upload(
        session,
        user_id,
        ndjson(
            {
                **steps("08:00", "08:01", 50),
                "start": "2026-10-01T05:00:00Z",
                "end": "2026-10-01T05:01:00Z",
            },
            {**hr("08:00:05", 96), "ts": "2026-10-01T05:00:05Z"},
        ),
    )

    assert (again.new, again.duplicate, again.conflict, again.invalid) == (0, 3, 0, 0)
    assert again.errors == []
    assert (in_utc.new, in_utc.duplicate) == (0, 2)
    after = (
        await steps_rows(session, user_id),
        await sleep_rows(session, user_id),
        await hr_rows(session, user_id),
    )
    assert after == before


async def test_same_key_different_count_conflict_first_kept(session: AsyncSession, user_id) -> None:
    await upload(session, user_id, ndjson(META, steps("08:00", "08:01", 50)))

    _, counts = await upload(session, user_id, ndjson(META, steps("08:00", "08:01", 70)))

    assert (counts.new, counts.duplicate, counts.conflict) == (0, 0, 1)
    [error] = counts.errors
    assert (error.line, error.kind) == (2, "conflict")
    assert error.reason
    assert await steps_rows(session, user_id) == [("watch-1", utc(5, 0), utc(5, 1), 50)]


async def test_overlapping_steps_different_bounds_conflict(session: AsyncSession, user_id) -> None:
    await upload(session, user_id, ndjson(META, steps("08:00", "08:05", 500)))

    _, counts = await upload(
        session,
        user_id,
        ndjson(
            steps("08:03", "08:08", 400),  # overlaps the stored interval
            steps("07:59", "08:00:01", 5),  # one second of overlap is an overlap
            steps("08:01", "08:02", 100),  # inside the stored interval
            steps("08:03", "08:08", 400, device="phone-1"),  # another device: no conflict
        ),
    )
    assert (counts.new, counts.conflict) == (1, 3)
    assert sorted(e.line for e in counts.errors) == [1, 2, 3]
    assert {e.kind for e in counts.errors} == {"conflict"}

    # Overlaps inside one file: the first line wins; overlapping only a rejected line is fine.
    _, chain = await upload(
        session,
        user_id,
        ndjson(
            steps("10:00", "10:02", 20),  # line 1: new
            steps("10:01", "10:03", 20),  # line 2: overlaps line 1 -> conflict
            steps("10:02", "10:04", 20),  # line 3: overlaps only line 2 -> new
        ),
    )
    assert (chain.new, chain.conflict) == (2, 1)
    assert [e.line for e in chain.errors] == [2]
    stored = await steps_rows(session, user_id)
    assert ("watch-1", utc(7, 0), utc(7, 2), 20) in stored
    assert ("watch-1", utc(7, 2), utc(7, 4), 20) in stored
    assert ("watch-1", utc(7, 1), utc(7, 3), 20) not in stored


async def test_adjacent_steps_intervals_both_new(session: AsyncSession, user_id) -> None:
    # SPEC F4.3: unaligned neighbours [08:00:30, 08:01:30) and [08:01:30, 08:02:30) do not overlap.
    _, counts = await upload(
        session,
        user_id,
        ndjson(META, steps("08:00:30", "08:01:30", 60), steps("08:01:30", "08:02:30", 60)),
    )
    # A neighbour from a later upload is new too.
    _, later = await upload(session, user_id, ndjson(steps("08:02:30", "08:03:00", 30)))

    assert (counts.new, counts.conflict) == (2, 0)
    assert (later.new, later.conflict) == (1, 0)
    assert [r[1:] for r in await steps_rows(session, user_id)] == [
        (utc(5, 0, 30), utc(5, 1, 30), 60),
        (utc(5, 1, 30), utc(5, 2, 30), 60),
        (utc(5, 2, 30), utc(5, 3), 30),
    ]


async def test_overlapping_sleep_allowed(session: AsyncSession, user_id) -> None:
    await upload(session, user_id, ndjson(META, sleep("00:00", "06:00")))

    _, counts = await upload(
        session,
        user_id,
        ndjson(sleep("05:00", "07:00"), sleep("01:00", "02:00"), sleep("00:00", "06:00")),
    )

    assert (counts.new, counts.duplicate, counts.conflict) == (2, 1, 0)
    assert await sleep_rows(session, user_id) == [
        ("watch-1", eve(21, 0), utc(3, 0)),
        ("watch-1", eve(22, 0), eve(23, 0)),
        ("watch-1", utc(2, 0), utc(4, 0)),
    ]


async def test_hr_same_ts_different_bpm_conflict(session: AsyncSession, user_id) -> None:
    await upload(session, user_id, ndjson(META, hr("08:00:05", 96)))

    _, counts = await upload(session, user_id, ndjson(hr("08:00:05", 120), hr("08:00:10", 97)))

    assert (counts.new, counts.duplicate, counts.conflict) == (1, 0, 1)
    [error] = counts.errors
    assert (error.line, error.kind) == (1, "conflict")
    assert await hr_rows(session, user_id) == [
        ("watch-1", utc(5, 0, 5), 96),
        ("watch-1", utc(5, 0, 10), 97),
    ]


@pytest.mark.parametrize("batch_size", [5000, 1])
async def test_in_batch_duplicates_collapsed(
    session: AsyncSession, user_id, batch_size: int
) -> None:
    # batch_size=1 puts every line into its own batch: the result must not depend on batching.
    data = ndjson(
        META,
        steps("08:00", "08:01", 50),  # line 2: new
        steps("08:00", "08:01", 50),  # line 3: duplicate of line 2
        steps("08:00", "08:01", 60),  # line 4: same key, other count -> conflict, line 2 kept
        sleep("01:00", "06:00"),  # line 5: new
        sleep("01:00", "06:00"),  # line 6: duplicate
        hr("08:00:05", 96),  # line 7: new
        hr("08:00:05", 96),  # line 8: duplicate
        hr("08:00:05", 99),  # line 9: conflict
    )

    _, counts = await upload(session, user_id, data, batch_size=batch_size)

    assert (counts.new, counts.duplicate, counts.conflict, counts.invalid) == (3, 3, 2, 0)
    assert sorted((e.line, e.kind) for e in counts.errors) == [(4, "conflict"), (9, "conflict")]
    assert await steps_rows(session, user_id) == [("watch-1", utc(5, 0), utc(5, 1), 50)]
    assert len(await sleep_rows(session, user_id)) == 1
    assert await hr_rows(session, user_id) == [("watch-1", utc(5, 0, 5), 96)]


async def test_device_autocreated_from_meta(session: AsyncSession, user_id) -> None:
    _, counts = await upload(session, user_id, ndjson(META, steps("08:00", "08:01", 5)))
    _, again = await upload(session, user_id, ndjson(META, hr("08:00:05", 90, device="watch-1")))

    # Devices of the meta line are created even before their first record (phone-1 has none).
    assert await device_rows(session, user_id) == [
        ("phone-1", "phone", "Телефон"),
        ("watch-1", "watch", "Часы"),
    ]
    assert counts.warnings == []
    assert again.warnings == []
    created = await rows(
        session, "SELECT DISTINCT created_at FROM devices WHERE user_id = :u", u=user_id
    )
    assert created == [(NOW,)]


async def test_unknown_device_created_as_phone_with_warning(session: AsyncSession, user_id) -> None:
    _, counts = await upload(
        session,
        user_id,
        ndjson(steps("08:00", "08:01", 5, device="band-9"), hr("08:00:05", 90, device="band-9")),
    )
    _, again = await upload(session, user_id, ndjson(steps("09:00", "09:01", 5, device="band-9")))

    assert counts.new == 2
    assert await device_rows(session, user_id) == [("band-9", "phone", "band-9")]
    [warning] = counts.warnings
    assert "band-9" in warning
    # The device exists now: no new warning on the next upload.
    assert again.warnings == []


async def test_invalid_lines_counted_with_line_numbers(session: AsyncSession, user_id) -> None:
    """Beyond the plan: invalid lines reach the report with their numbers, valid ones are stored."""
    data = ndjson(META, steps("08:00", "08:01", 5)) + b"{oops\n" + ndjson(hr("08:00:05", 400))

    _, counts = await upload(session, user_id, data)

    assert (counts.new, counts.invalid) == (1, 2)
    assert sorted((e.line, e.kind) for e in counts.errors) == [(3, "invalid"), (4, "invalid")]


async def test_devices_and_records_are_per_user(session: AsyncSession, user_id) -> None:
    """Beyond the plan: the same external id of another user is another device, no duplicates."""
    other = await make_user(session, "other@example.com")
    data = ndjson(META, steps("08:00", "08:01", 5))
    await upload(session, user_id, data)

    _, counts = await upload(session, other, data)

    assert (counts.new, counts.duplicate) == (1, 0)
    assert await device_rows(session, other) == [
        ("phone-1", "phone", "Телефон"),
        ("watch-1", "watch", "Часы"),
    ]
    assert len(await steps_rows(session, user_id)) == 1
    assert len(await steps_rows(session, other)) == 1
