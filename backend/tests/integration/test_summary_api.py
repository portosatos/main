"""Summary API (SPEC F7, §6.3; plan step 4.4): GET /api/summary/day|week|range.

daily_summaries is derived (services/summaries.py, tested in test_summaries.py), so these tests
write its rows directly and check what the API makes of them: no_data for dates without a row,
the difference with the previous period and the week's bases. Users register through the API,
the rows go through the same rolled-back connection.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import DailySummary
from tests.integration.client import api_client

PASSWORD = "correct horse battery"
COMPUTED_AT = datetime(2026, 10, 11, 0, 0, tzinfo=UTC)
METRICS = ["steps", "active_minutes", "sleep_minutes", "resting_hr", "peak_hr"]
Sessionmaker = async_sessionmaker[AsyncSession]

# ISO week 2026-W41 is Mon 2026-10-05 .. Sun 2026-10-11.
W41 = [date(2026, 10, 5) + timedelta(days=i) for i in range(7)]
MON, TUE, WED, THU, FRI, SAT, SUN = W41


@asynccontextmanager
async def user_client(
    database_url: str, sessionmaker: Sessionmaker, email: str
) -> AsyncIterator[tuple[httpx.AsyncClient, uuid.UUID]]:
    """A client logged in as a newly registered user, and the user's id."""
    async with api_client(database_url, sessionmaker=sessionmaker) as client:
        body = {"email": email, "password": PASSWORD, "timezone": "Europe/Moscow"}
        registered = await client.post("/api/auth/register", json=body)
        assert registered.status_code == 201, registered.text
        yield client, uuid.UUID(registered.json()["id"])


@pytest.fixture
async def client_and_user(
    migrated_database_url: str, test_sessionmaker: Sessionmaker
) -> AsyncIterator[tuple[httpx.AsyncClient, uuid.UUID]]:
    async with user_client(migrated_database_url, test_sessionmaker, "summary@example.com") as cu:
        yield cu


def day_row(
    user_id: uuid.UUID,
    day: date,
    *,
    status: str = "complete",
    wear_minutes: int | None = None,
    steps: int | None = None,
    active_minutes: int | None = None,
    sleep_minutes: int | None = None,
    night_valid: bool = False,
    resting_hr: float | None = None,
    peak_hr: float | None = None,
) -> DailySummary:
    if wear_minutes is None:
        wear_minutes = 1440 if status == "complete" else 300
    sleep_end = None
    sleep_start = None
    if sleep_minutes is not None:
        sleep_end = datetime(day.year, day.month, day.day, 4, 0, tzinfo=UTC)
        sleep_start = sleep_end - timedelta(minutes=sleep_minutes)
    return DailySummary(
        user_id=user_id,
        local_date=day,
        status=status,
        wear_minutes=wear_minutes,
        steps=steps,
        active_minutes=active_minutes,
        sleep_minutes=sleep_minutes,
        sleep_start=sleep_start,
        sleep_end=sleep_end,
        night_valid=night_valid,
        resting_hr=resting_hr,
        peak_hr=peak_hr,
        computed_at=COMPUTED_AT,
    )


async def store(sessionmaker: Sessionmaker, *summaries: DailySummary) -> None:
    async with sessionmaker() as session:
        session.add_all(summaries)
        await session.commit()


async def get_ok(client: httpx.AsyncClient, url: str) -> Any:
    response = await client.get(url)
    assert response.status_code == 200, response.text
    return response.json()


def assert_no_data(day: dict[str, Any], on: date) -> None:
    """A date without data: status no_data, null instead of zero (SPEC F6)."""
    assert day["date"] == on.isoformat()
    assert day["status"] == "no_data"
    assert day["wear_minutes"] == 0
    assert day["night_valid"] is False
    for key in [*METRICS, "sleep_start", "sleep_end"]:
        assert day[key] is None, key


def base(value: float | None, days: int) -> dict[str, Any]:
    return {"value": value, "days": days, "of": 7}


def w41_rows(user_id: uuid.UUID) -> list[DailySummary]:
    """W41 with every kind of day:
    Mon complete, valid night; Tue partial, but the night is recorded whole (valid);
    Wed complete, invalid night; Thu no data; Fri complete, valid night;
    Sat partial, invalid night, no pulse; Sun no data."""
    return [
        day_row(user_id, MON, steps=10000, active_minutes=60, sleep_minutes=420,
                night_valid=True, resting_hr=58.0, peak_hr=150.0),
        day_row(user_id, TUE, status="partial", steps=1500, active_minutes=5,
                sleep_minutes=480, night_valid=True, resting_hr=None, peak_hr=120.0),
        day_row(user_id, WED, steps=8000, active_minutes=40, sleep_minutes=200,
                night_valid=False, resting_hr=60.0, peak_hr=165.0),
        day_row(user_id, FRI, steps=9000, active_minutes=50, sleep_minutes=450,
                night_valid=True, resting_hr=61.0, peak_hr=140.0),
        day_row(user_id, SAT, status="partial", steps=300, active_minutes=0,
                sleep_minutes=100, night_valid=False),
    ]  # fmt: skip


@pytest.mark.xfail(strict=True, reason="step 4.4: not implemented")
async def test_day_summary_with_delta_vs_previous_day(
    client_and_user: tuple[httpx.AsyncClient, uuid.UUID], test_sessionmaker: Sessionmaker
) -> None:
    client, user_id = client_and_user
    await store(
        test_sessionmaker,
        day_row(user_id, TUE, steps=8000, active_minutes=40, sleep_minutes=420,
                night_valid=True, resting_hr=58.0, peak_hr=150.0),
        day_row(user_id, WED, steps=10000, active_minutes=50, sleep_minutes=390,
                night_valid=True, resting_hr=60.0, peak_hr=140.0),
    )  # fmt: skip

    body = await get_ok(client, "/api/summary/day?date=2026-10-07")

    day, previous = body["day"], body["previous"]
    assert day["date"] == "2026-10-07"
    assert (day["status"], day["wear_minutes"], day["steps"]) == ("complete", 1440, 10000)
    assert (day["sleep_minutes"], day["night_valid"], day["resting_hr"]) == (390, True, 60.0)
    assert day["sleep_end"] is not None
    assert previous["date"] == "2026-10-06"
    assert previous["steps"] == 8000
    # Absolute and per cent of the previous day, rounded to 0.1.
    assert body["delta"] == {
        "steps": {"abs": 2000, "pct": 25.0},
        "active_minutes": {"abs": 10, "pct": 25.0},
        "sleep_minutes": {"abs": -30, "pct": -7.1},
        "resting_hr": {"abs": 2.0, "pct": 3.4},
        "peak_hr": {"abs": -10.0, "pct": -6.7},
    }


@pytest.mark.xfail(strict=True, reason="step 4.4: not implemented")
async def test_day_delta_null_when_previous_no_data(
    client_and_user: tuple[httpx.AsyncClient, uuid.UUID], test_sessionmaker: Sessionmaker
) -> None:
    client, user_id = client_and_user
    await store(
        test_sessionmaker,
        day_row(user_id, WED, steps=10000, active_minutes=50, sleep_minutes=390,
                night_valid=True, resting_hr=60.0, peak_hr=140.0),
        # Fri has steps but no resting pulse and zero active minutes; Sat has all of them.
        day_row(user_id, FRI, status="partial", steps=4000, active_minutes=0, peak_hr=130.0),
        day_row(user_id, SAT, steps=6000, active_minutes=30, resting_hr=59.0, peak_hr=150.0),
    )  # fmt: skip
    nothing = dict.fromkeys(METRICS)

    # The previous day has no data: nothing to compare with.
    body = await get_ok(client, "/api/summary/day?date=2026-10-07")
    assert body["day"]["steps"] == 10000
    assert_no_data(body["previous"], TUE)
    assert body["delta"] == nothing

    # The day itself has no data: no_data with nulls, not zeros, and no comparison.
    body = await get_ok(client, "/api/summary/day?date=2026-10-08")
    assert_no_data(body["day"], THU)
    assert body["previous"]["steps"] == 10000
    assert body["delta"] == nothing

    # Per metric: a null on either side gives null; a previous 0 gives no per cent.
    body = await get_ok(client, "/api/summary/day?date=2026-10-10")
    assert body["delta"] == {
        "steps": {"abs": 2000, "pct": 50.0},
        "active_minutes": {"abs": 30, "pct": None},
        "sleep_minutes": None,
        "resting_hr": None,
        "peak_hr": {"abs": 20.0, "pct": 15.4},
    }


@pytest.mark.xfail(strict=True, reason="step 4.4: not implemented")
async def test_week_sleep_avg_over_valid_nights_including_partial_days(
    client_and_user: tuple[httpx.AsyncClient, uuid.UUID], test_sessionmaker: Sessionmaker
) -> None:
    client, user_id = client_and_user
    await store(test_sessionmaker, *w41_rows(user_id))

    body = await get_ok(client, "/api/summary/week?week=2026-W41")

    # Valid nights: Mon 420, Tue 480 (a partial day), Fri 450. Wed 200 and Sat 100 are invalid.
    assert body["metrics"]["sleep_minutes"] == base(450.0, 3)


@pytest.mark.xfail(strict=True, reason="step 4.4: not implemented")
async def test_week_steps_avg_over_complete_days_only(
    client_and_user: tuple[httpx.AsyncClient, uuid.UUID], test_sessionmaker: Sessionmaker
) -> None:
    client, user_id = client_and_user
    await store(test_sessionmaker, *w41_rows(user_id))

    body = await get_ok(client, "/api/summary/week?week=2026-W41")

    # Complete days: Mon 10000, Wed 8000, Fri 9000. Partial Tue (1500) and Sat (300) stay out.
    assert body["metrics"]["steps"] == base(9000.0, 3)
    assert body["metrics"]["active_minutes"] == base(50.0, 3)
    # The partial days are still in the week's days, with their values.
    by_date = {d["date"]: d for d in body["days"]}
    assert by_date["2026-10-06"]["status"] == "partial"
    assert by_date["2026-10-06"]["steps"] == 1500


@pytest.mark.xfail(strict=True, reason="step 4.4: not implemented")
async def test_week_returns_base_counts(
    client_and_user: tuple[httpx.AsyncClient, uuid.UUID], test_sessionmaker: Sessionmaker
) -> None:
    client, user_id = client_and_user
    previous_mon = MON - timedelta(days=7)
    await store(
        test_sessionmaker,
        *w41_rows(user_id),
        day_row(user_id, previous_mon, steps=6000, active_minutes=40, resting_hr=60.0,
                peak_hr=170.0),
    )  # fmt: skip

    body = await get_ok(client, "/api/summary/week?week=2026-W41")

    assert (body["week"], body["start"], body["end"]) == ("2026-W41", "2026-10-05", "2026-10-11")
    assert body["metrics"] == {
        "steps": base(9000.0, 3),
        "active_minutes": base(50.0, 3),
        "sleep_minutes": base(450.0, 3),
        "resting_hr": base(59.7, 3),  # Mon 58, Wed 60, Fri 61
        "peak_hr": base(165.0, 4),  # the max over Mon, Tue, Wed, Fri
    }
    # All seven days, no_data ones with nulls.
    assert [d["date"] for d in body["days"]] == [d.isoformat() for d in W41]
    assert [d["status"] for d in body["days"]] == [
        "complete", "partial", "complete", "no_data", "complete", "partial", "no_data",
    ]  # fmt: skip
    assert_no_data(body["days"][3], THU)
    assert_no_data(body["days"][6], SUN)

    # The previous week W40 has one complete day and no valid night.
    previous = body["previous"]
    assert (previous["week"], previous["start"], previous["end"]) == (
        "2026-W40", "2026-09-28", "2026-10-04",
    )  # fmt: skip
    assert previous["metrics"]["steps"] == base(6000.0, 1)
    assert previous["metrics"]["sleep_minutes"] == base(None, 0)
    assert body["delta"] == {
        "steps": {"abs": 3000.0, "pct": 50.0},
        "active_minutes": {"abs": 10.0, "pct": 25.0},
        "sleep_minutes": None,
        "resting_hr": {"abs": -0.3, "pct": -0.5},
        "peak_hr": {"abs": -5.0, "pct": -2.9},
    }


@pytest.mark.xfail(strict=True, reason="step 4.4: not implemented")
async def test_week_empty_base_returns_null(
    client_and_user: tuple[httpx.AsyncClient, uuid.UUID], test_sessionmaker: Sessionmaker
) -> None:
    client, user_id = client_and_user
    # W41 has only partial days without valid nights or pulse; W42 has nothing at all.
    await store(
        test_sessionmaker,
        day_row(user_id, MON, status="partial", steps=2000, active_minutes=10,
                sleep_minutes=120, night_valid=False),
        day_row(user_id, TUE, status="partial", steps=500, active_minutes=0),
    )  # fmt: skip
    empty = dict.fromkeys(METRICS, base(None, 0))

    body = await get_ok(client, "/api/summary/week?week=2026-W41")
    assert body["metrics"] == empty
    assert body["delta"] == dict.fromkeys(METRICS)

    body = await get_ok(client, "/api/summary/week?week=2026-W42")
    assert body["metrics"] == empty
    assert len(body["days"]) == 7
    for day, on in zip(body["days"], [d + timedelta(days=7) for d in W41], strict=True):
        assert_no_data(day, on)


@pytest.mark.xfail(strict=True, reason="step 4.4: not implemented")
async def test_range_returns_status_per_day_with_nulls(
    client_and_user: tuple[httpx.AsyncClient, uuid.UUID], test_sessionmaker: Sessionmaker
) -> None:
    client, user_id = client_and_user
    await store(test_sessionmaker, *w41_rows(user_id))

    days = await get_ok(client, "/api/summary/range?from=2026-10-04&to=2026-10-12")

    assert [d["date"] for d in days] == [
        (date(2026, 10, 4) + timedelta(days=i)).isoformat() for i in range(9)
    ]
    assert [d["status"] for d in days] == [
        "no_data", "complete", "partial", "complete", "no_data", "complete", "partial",
        "no_data", "no_data",
    ]  # fmt: skip
    assert [d["steps"] for d in days] == [None, 10000, 1500, 8000, None, 9000, 300, None, None]
    assert [d["sleep_minutes"] for d in days] == [None, 420, 480, 200, None, 450, 100, None, None]
    assert [d["night_valid"] for d in days] == [
        False, True, True, False, False, True, False, False, False,
    ]  # fmt: skip
    assert_no_data(days[4], THU)

    one = await get_ok(client, "/api/summary/range?from=2026-10-05&to=2026-10-05")
    assert [d["steps"] for d in one] == [10000]

    # Reversed and too long ranges are rejected; a year (366 days) is the limit.
    year = await client.get("/api/summary/range?from=2025-10-12&to=2026-10-12")
    assert year.status_code == 200, year.text
    assert len(year.json()) == 366
    for query in ["from=2026-10-12&to=2026-10-04", "from=2025-10-11&to=2026-10-12"]:
        response = await client.get(f"/api/summary/range?{query}")
        assert response.status_code == 422, (query, response.text)


@pytest.mark.xfail(strict=True, reason="step 4.4: not implemented")
async def test_iso_week_param_edges_w01_w53(
    client_and_user: tuple[httpx.AsyncClient, uuid.UUID], test_sessionmaker: Sessionmaker
) -> None:
    client, user_id = client_and_user
    await store(
        test_sessionmaker,
        day_row(user_id, date(2025, 12, 29), steps=1000),
        day_row(user_id, date(2026, 1, 4), steps=3000),
        day_row(user_id, date(2025, 12, 28), steps=5000),
        day_row(user_id, date(2027, 1, 3), steps=7000),
    )

    # W01 of 2026 starts in 2025; the week before it is 2025-W52 (2025 has 52 weeks).
    body = await get_ok(client, "/api/summary/week?week=2026-W01")
    assert (body["start"], body["end"]) == ("2025-12-29", "2026-01-04")
    assert body["metrics"]["steps"] == base(2000.0, 2)
    assert body["previous"]["week"] == "2025-W52"
    assert body["previous"]["metrics"]["steps"] == base(5000.0, 1)

    # 2026 has 53 weeks (it starts on a Thursday); W53 ends in 2027.
    body = await get_ok(client, "/api/summary/week?week=2026-W53")
    assert (body["start"], body["end"]) == ("2026-12-28", "2027-01-03")
    assert body["metrics"]["steps"] == base(7000.0, 1)
    body = await get_ok(client, "/api/summary/week?week=2027-W01")
    assert body["previous"]["week"] == "2026-W53"
    assert body["previous"]["metrics"]["steps"] == base(7000.0, 1)

    for week in ["2025-W53", "2026-W00", "2026-W54", "2026-41", "2026-W5", "2026-w41", ""]:
        response = await client.get("/api/summary/week", params={"week": week})
        assert response.status_code == 422, (week, response.text)


@pytest.mark.xfail(strict=True, reason="step 4.4: not implemented")
async def test_summary_returns_only_own_data(
    migrated_database_url: str, test_sessionmaker: Sessionmaker
) -> None:
    async with (
        user_client(migrated_database_url, test_sessionmaker, "alice@example.com") as (a, alice),
        user_client(migrated_database_url, test_sessionmaker, "bob@example.com") as (b, bob),
    ):
        await store(
            test_sessionmaker,
            day_row(alice, TUE, steps=11111, sleep_minutes=500, night_valid=True),
            day_row(alice, WED, steps=22222, sleep_minutes=510, night_valid=True),
            day_row(bob, WED, steps=3000),
        )

        day = await get_ok(b, "/api/summary/day?date=2026-10-07")
        assert day["day"]["steps"] == 3000
        assert_no_data(day["previous"], TUE)

        week = await get_ok(b, "/api/summary/week?week=2026-W41")
        assert [d["steps"] for d in week["days"]] == [None, None, 3000, None, None, None, None]
        assert week["metrics"]["steps"] == base(3000.0, 1)
        assert week["metrics"]["sleep_minutes"] == base(None, 0)

        days = await get_ok(b, "/api/summary/range?from=2026-10-06&to=2026-10-07")
        assert [d["steps"] for d in days] == [None, 3000]

        # Alice still sees hers.
        day = await get_ok(a, "/api/summary/day?date=2026-10-07")
        assert (day["day"]["steps"], day["previous"]["steps"]) == (22222, 11111)

    # Without a session: 401.
    async with api_client(migrated_database_url, sessionmaker=test_sessionmaker) as anonymous:
        for url in [
            "/api/summary/day?date=2026-10-07",
            "/api/summary/week?week=2026-W41",
            "/api/summary/range?from=2026-10-06&to=2026-10-07",
        ]:
            response = await anonymous.get(url)
            assert response.status_code == 401, (url, response.text)
