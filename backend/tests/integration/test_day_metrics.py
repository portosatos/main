"""Metrics of a local day from the merged minutes (SPEC F6, F7): services/metrics.py.

The user lives in Europe/Moscow (+03:00); data go through the parser and the classifier, which
fill the minute tables, then the day is computed for a local date.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import UserTimezone
from app.services.metrics import DayMetrics, day_metrics
from tests.integration.ingest import NOW, make_user, ndjson, steps_minute_rows, upload

pytestmark = pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="step 4.2: not implemented"
)

MSK = timezone(timedelta(hours=3))
DAY = date(2026, 10, 5)
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


async def make_msk_user(session: AsyncSession) -> uuid.UUID:
    """A user registered at NOW in Europe/Moscow: the first zone also covers the earlier data."""
    user_id = await make_user(session)
    session.add(UserTimezone(user_id=user_id, tz="Europe/Moscow", valid_from=NOW, created_at=NOW))
    await session.flush()
    return user_id


def at(hour: int, minute: int = 0, second: int = 0, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=MSK)


def steps(device: str, start: datetime, end: datetime, count: int) -> dict:
    return {
        "type": "steps",
        "device": device,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "count": count,
    }


def per_minute(device: str, start: datetime, counts: list[int]) -> list[dict]:
    """One-minute step intervals from `start` on, one per count."""
    minute = timedelta(minutes=1)
    return [
        steps(device, start + i * minute, start + (i + 1) * minute, c) for i, c in enumerate(counts)
    ]


def hr(device: str, ts: datetime, bpm: int) -> dict:
    return {"type": "hr", "device": device, "ts": ts.isoformat(), "bpm": bpm}


async def load(session: AsyncSession, user_id: uuid.UUID, *records: dict) -> None:
    await upload(session, user_id, ndjson(META, *records))


async def test_phone_only_walk_plus_both_walk_day_equals_5000(session: AsyncSession) -> None:
    # SPEC §8 stage 4, §9 #4: walk 1 only on the phone (the watch is off), 3000; walk 2 on both,
    # watch 2000 and phone 1900. The day is 5000: more than either device alone (2000 and 4900).
    user_id = await make_msk_user(session)
    await load(
        session,
        user_id,
        *per_minute("phone-1", at(8), [100] * 30),
        *per_minute("watch-1", at(18), [100] * 20),
        *per_minute("phone-1", at(18), [95] * 20),
        # 02:00 MSK on Oct 6 is still Oct 5 in UTC, but belongs to the next local day
        steps("phone-1", at(2, day=date(2026, 10, 6)), at(2, 10, day=date(2026, 10, 6)), 500),
    )

    by_device: dict[str, float] = {}
    for (external_id, minute), value in (await steps_minute_rows(session, user_id)).items():
        if minute.astimezone(MSK).date() == DAY:
            by_device[external_id] = by_device.get(external_id, 0.0) + value
    assert by_device == {"watch-1": 2000, "phone-1": 4900}

    metrics = await day_metrics(session, user_id, DAY)

    assert metrics.steps == 5000
    assert metrics.wear_minutes == 50
    assert metrics.status == "partial"


@pytest.mark.parametrize(
    ("covered", "status"), [(0, "no_data"), (1, "partial"), (719, "partial"), (720, "complete")]
)
async def test_status_boundaries_0_719_720_minutes(
    session: AsyncSession, covered: int, status: str
) -> None:
    # SPEC F6: wear time = minutes covered by any device; complete from 12 h. One zero-step
    # interval from local midnight covers exactly `covered` minutes; the day before has data too.
    user_id = await make_msk_user(session)
    records = [steps("watch-1", at(12, day=date(2026, 10, 4)), at(13, day=date(2026, 10, 4)), 0)]
    if covered:
        records.append(steps("watch-1", at(0), at(0) + timedelta(minutes=covered), 0))
    await load(session, user_id, *records)

    metrics = await day_metrics(session, user_id, DAY)

    assert (metrics.wear_minutes, metrics.status) == (covered, status)


async def test_no_data_day_steps_null_not_zero(session: AsyncSession) -> None:
    # SPEC F6, §9 #9: a day without data is "no data", not 0 steps. Data exist on Oct 4 and on
    # Oct 6; Oct 6 has pulse only, so its steps are a real 0.
    user_id = await make_msk_user(session)
    oct4, oct6 = date(2026, 10, 4), date(2026, 10, 6)
    await load(
        session,
        user_id,
        *per_minute("watch-1", at(9, day=oct4), [120] * 10),
        *(hr("watch-1", at(10, i, day=oct6), 70) for i in range(5)),
    )

    assert await day_metrics(session, user_id, DAY) == DayMetrics(
        local_date=DAY,
        status="no_data",
        wear_minutes=0,
        steps=None,
        active_minutes=None,
        resting_hr=None,
        peak_hr=None,
    )
    pulse_only = await day_metrics(session, user_id, oct6)
    assert (pulse_only.status, pulse_only.steps, pulse_only.active_minutes) == ("partial", 0, 0)


@pytest.mark.parametrize(("rest_minutes", "expected"), [(60, 55.9), (59, None)])
async def test_resting_hr_p10_requires_60_rest_minutes(
    session: AsyncSession, rest_minutes: int, expected: float | None
) -> None:
    # SPEC F7: the 10th percentile of the pulse in minutes without steps, at least 60 of them.
    # Rest minutes have one watch point each, 50, 51, ...; the phone's 40s in the same minutes
    # lose the merge. A 10-minute walk with pulse 150 has steps and stays out.
    # 60 minutes 50..109: p10 = 50 + 0.1 * 59 = 55.9 (linear interpolation).
    user_id = await make_msk_user(session)
    await load(
        session,
        user_id,
        *(hr("watch-1", at(3, i, 10), 50 + i) for i in range(rest_minutes)),
        *(hr("phone-1", at(3, i, 20), 40) for i in range(rest_minutes)),
        *per_minute("watch-1", at(8), [120] * 10),
        *(hr("watch-1", at(8, i, 30), 150) for i in range(10)),
    )

    metrics = await day_metrics(session, user_id, DAY)

    assert metrics.resting_hr == (pytest.approx(expected) if expected is not None else None)


async def test_peak_hr_ignores_single_spike(session: AsyncSession) -> None:
    # SPEC F7: the peak is the maximum of minute medians. 10:00 has eleven points of 80 and one
    # spike of 200 (median 80); 10:01 has 118, 120, 122 (median 120) -> the peak is 120, not 200.
    user_id = await make_msk_user(session)
    await load(
        session,
        user_id,
        *(hr("watch-1", at(10, 0, 5 * i), 80) for i in range(11)),
        hr("watch-1", at(10, 0, 55), 200),
        *(hr("watch-1", at(10, 1, 5 * i), bpm) for i, bpm in enumerate([118, 120, 122])),
    )

    metrics = await day_metrics(session, user_id, DAY)

    assert metrics.peak_hr == 120


async def test_active_minutes_threshold_100(session: AsyncSession) -> None:
    # SPEC F7: an active minute has at least 100 merged steps: 99 no, 100 and 101 yes, 0 no.
    user_id = await make_msk_user(session)
    await load(session, user_id, *per_minute("watch-1", at(8), [99, 100, 101, 0]))

    metrics = await day_metrics(session, user_id, DAY)

    assert (metrics.active_minutes, metrics.steps, metrics.wear_minutes) == (2, 300, 4)
