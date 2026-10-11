"""Devices API (SPEC F2, §6.3; plan step 6.1): GET /api/devices and PATCH /api/devices/{id}.

Devices are created by the ingest (tested in test_classify.py), so these tests write the rows
directly: the devices and the coverage minutes that give "последние данные". Users register
through the API, the rows go through the same rolled-back connection.
"""

import uuid
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import CoverageMinute, Device
from tests.integration.client import api_client

PASSWORD = "correct horse battery"
CREATED_AT = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
Sessionmaker = async_sessionmaker[AsyncSession]

pytestmark = pytest.mark.xfail(strict=True, reason="step 6.1: not implemented")


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


async def add_device(
    sessionmaker: Sessionmaker,
    user_id: uuid.UUID,
    external_id: str,
    kind: str,
    name: str,
    *,
    created_at: datetime = CREATED_AT,
    covered: Sequence[datetime] = (),
) -> uuid.UUID:
    """A device of the user and its coverage minutes."""
    device = Device(
        user_id=user_id, external_id=external_id, kind=kind, name=name, created_at=created_at
    )
    async with sessionmaker() as session:
        session.add(device)
        await session.flush()
        session.add_all(CoverageMinute(device_id=device.id, minute_utc=m) for m in covered)
        await session.commit()
        return device.id


async def device_name(sessionmaker: Sessionmaker, device_id: uuid.UUID) -> str:
    async with sessionmaker() as session:
        found = await session.execute(select(Device.name).where(Device.id == device_id))
        return found.scalar_one()


def ok(response: httpx.Response, code: int = 200) -> Any:
    assert response.status_code == code, response.text
    return response.json()


async def test_list_and_rename(migrated_database_url: str, test_sessionmaker: Sessionmaker) -> None:
    async with user_client(migrated_database_url, test_sessionmaker, "dev@example.com") as (
        client,
        user_id,
    ):
        assert ok(await client.get("/api/devices")) == []

        last = datetime(2026, 10, 7, 21, 59, tzinfo=UTC)
        watch = await add_device(
            test_sessionmaker, user_id, "watch-1", "watch", "Часы",
            covered=[last - timedelta(minutes=5), last],
        )  # fmt: skip
        phone = await add_device(
            test_sessionmaker, user_id, "phone-1", "phone", "Телефон",
            created_at=CREATED_AT + timedelta(minutes=1),
        )  # fmt: skip

        # In the order of registration; "последние данные" — the last covered minute, or null.
        devices = ok(await client.get("/api/devices"))
        assert devices == [
            {
                "id": str(watch),
                "external_id": "watch-1",
                "kind": "watch",
                "name": "Часы",
                "created_at": "2026-10-01T00:00:00Z",
                "last_data_at": "2026-10-07T21:59:00Z",
            },
            {
                "id": str(phone),
                "external_id": "phone-1",
                "kind": "phone",
                "name": "Телефон",
                "created_at": "2026-10-01T00:01:00Z",
                "last_data_at": None,
            },
        ]

        # Rename: the name is trimmed; kind and external id stay.
        renamed = ok(await client.patch(f"/api/devices/{watch}", json={"name": "  Мои часы "}))
        assert renamed == {**devices[0], "name": "Мои часы"}
        assert await device_name(test_sessionmaker, watch) == "Мои часы"
        assert ok(await client.get("/api/devices"))[0]["name"] == "Мои часы"

        # A blank or too long name → 422, nothing changes.
        for name in ["", "   ", "x" * 101]:
            response = await client.patch(f"/api/devices/{watch}", json={"name": name})
            assert response.status_code == 422, name
        assert await device_name(test_sessionmaker, watch) == "Мои часы"

        # Without the CSRF header → 403 (ADR-026).
        response = await client.patch(
            f"/api/devices/{phone}", json={"name": "X"}, headers={"X-Requested-With": ""}
        )
        assert response.status_code == 403
        assert await device_name(test_sessionmaker, phone) == "Телефон"


async def test_rename_other_user_device_404(
    migrated_database_url: str, test_sessionmaker: Sessionmaker
) -> None:
    async with (
        user_client(migrated_database_url, test_sessionmaker, "alice@example.com") as (a, alice),
        user_client(migrated_database_url, test_sessionmaker, "bob@example.com") as (b, bob),
    ):
        alice_watch = await add_device(test_sessionmaker, alice, "watch-1", "watch", "Часы")
        bob_watch = await add_device(test_sessionmaker, bob, "watch-1", "watch", "Часы Боба")

        # Bob sees only his device and cannot rename Alice's: 404, as for a missing one.
        assert [d["id"] for d in ok(await b.get("/api/devices"))] == [str(bob_watch)]
        response = await b.patch(f"/api/devices/{alice_watch}", json={"name": "Чужие"})
        assert response.status_code == 404
        assert await device_name(test_sessionmaker, alice_watch) == "Часы"
        response = await b.patch(f"/api/devices/{uuid.uuid4()}", json={"name": "Нет такого"})
        assert response.status_code == 404

        assert [d["name"] for d in ok(await a.get("/api/devices"))] == ["Часы"]

    # Without a session: 401.
    async with api_client(migrated_database_url, sessionmaker=test_sessionmaker) as anonymous:
        assert (await anonymous.get("/api/devices")).status_code == 401
        response = await anonymous.patch(f"/api/devices/{alice_watch}", json={"name": "X"})
        assert response.status_code == 401
