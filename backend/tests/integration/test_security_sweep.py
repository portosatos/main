"""A sweep over every route of the API (SPEC §9 #20; ADR-017; plan step 11.1).

The routes are taken from the OpenAPI schema of the app, so a route added later is checked too
or fails the sweep until it is classified here:
- a route with an id in the path answers 404 for another user's resource and changes nothing;
- every mutating request without the CSRF header gets 403 and changes nothing;
- the dev routes are 404 when APP_ENV=prod.

These commit for real, like test_ingest_jobs.py. Users get `@jobs.example.com` addresses and are
deleted by the `clean` fixture.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import AppEnv, Settings
from app.db import create_sessionmaker
from app.main import create_app
from app.models import Device
from tests.integration.client import CSRF_HEADERS
from tests.integration.test_ingest_jobs import PASSWORD, days_file, upload, wipe
from tests.integration.test_recommendations_api import add_recommendation

T = datetime(2026, 10, 10, 6, 0, tzinfo=UTC)
MUTATING = frozenset({"post", "put", "patch", "delete"})

# Routes with an id of a user's own resource in the path: (method, path) → the request body.
OWNED: dict[tuple[str, str], dict[str, Any] | None] = {
    ("get", "/api/ingest/jobs/{job_id}"): None,
    ("patch", "/api/devices/{device_id}"): {"name": "Чужое имя"},
    ("put", "/api/recommendations/{rec_id}/feedback"): {"value": "useful"},
    ("delete", "/api/recommendations/{rec_id}/feedback"): None,
}
# Routes with an id of a shared catalog entry: another user's call changes only their own state.
SHARED = {("patch", "/api/rules/{code}")}


@pytest.fixture
async def clean(db_engine: AsyncEngine) -> AsyncIterator[None]:
    await wipe(db_engine)
    yield
    await wipe(db_engine)


def make_settings(database_url: str, tmp_path: Path, app_env: AppEnv) -> Settings:
    return Settings(
        _env_file=None,
        database_url=database_url,
        app_env=app_env,
        ingest_dir=tmp_path / "ingest",
    )


@asynccontextmanager
async def two_clients(settings: Settings) -> AsyncIterator[tuple[httpx.AsyncClient, Any]]:
    """A fresh app and a client with the CSRF header; the app is yielded for more clients."""
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", headers=CSRF_HEADERS
        ) as client:
            yield client, app


async def register(client: httpx.AsyncClient, name: str) -> uuid.UUID:
    body = {
        "email": f"{name}-{uuid.uuid4().hex[:8]}@jobs.example.com",
        "password": PASSWORD,
        "timezone": "Europe/Moscow",
    }
    registered = await client.post("/api/auth/register", json=body)
    assert registered.status_code == 201, registered.text
    return uuid.UUID(registered.json()["id"])


def operations(app: Any) -> set[tuple[str, str]]:
    """(method, path) of every operation in the app's OpenAPI schema."""
    return {(method, path) for path, ops in app.openapi()["paths"].items() for method in ops}


async def call(
    client: httpx.AsyncClient, method: str, path: str, body: dict[str, Any] | None = None
) -> httpx.Response:
    return await client.request(method.upper(), path, json=body)


async def test_all_id_routes_return_404_for_other_users_resources(
    clean: None, migrated_database_url: str, tmp_path: Path, db_engine: AsyncEngine
) -> None:
    settings = make_settings(migrated_database_url, tmp_path, "test")
    async with two_clients(settings) as (owner, app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", headers=CSRF_HEADERS
        ) as stranger:
            owner_id = await register(owner, "sweep-owner")
            await register(stranger, "sweep-stranger")

            # The owner's resources: a device, an upload job, a recommendation.
            async with create_sessionmaker(db_engine)() as session:
                device = Device(
                    user_id=owner_id, external_id="watch-1", kind="watch", name="Часы", created_at=T
                )
                session.add(device)
                await session.commit()
                device_id = device.id
            job_id = await upload(owner, days_file(0))
            rec_id = await add_recommendation(db_engine, owner_id, "R1", "open", T)
            ids = {"job_id": job_id, "device_id": device_id, "rec_id": rec_id, "code": "R1"}

            id_routes = {op for op in operations(app) if "{" in op[1]}
            assert id_routes == set(OWNED) | SHARED, (
                "classify every route with an id in the path in OWNED or SHARED"
            )

            for (method, path), body in OWNED.items():
                response = await call(stranger, method, path.format(**ids), body)
                assert response.status_code == 404, f"{method} {path}: {response.status_code}"

            # Another user's call to a shared route changes only their own state.
            switched = await call(stranger, "patch", "/api/rules/R1", {"enabled": False})
            assert switched.status_code == 200, switched.text

            # The stranger's lists show nothing of the owner.
            for path in ("/api/ingest/jobs", "/api/devices", "/api/recommendations"):
                listed = await stranger.get(path)
                assert listed.status_code == 200, listed.text
                assert listed.json() == [], f"{path} shows another user's data"

            # The owner's resources are untouched.
            owner_devices = (await owner.get("/api/devices")).json()
            assert [d["name"] for d in owner_devices] == ["Часы"]
            [owner_rec] = (await owner.get("/api/recommendations")).json()
            assert owner_rec["feedback"] is None
            owner_rules = {r["code"]: r["enabled"] for r in (await owner.get("/api/rules")).json()}
            assert owner_rules["R1"] is True

            # Control: the same requests of the owner get through, so the 404s above are not typos.
            for (method, path), body in OWNED.items():
                response = await call(owner, method, path.format(**ids), body)
                assert response.is_success, f"{method} {path}: {response.status_code}"


async def test_all_mutating_routes_require_csrf_header(
    clean: None, migrated_database_url: str, tmp_path: Path, db_engine: AsyncEngine
) -> None:
    settings = make_settings(migrated_database_url, tmp_path, "dev")
    async with two_clients(settings) as (client, app):
        user_id = await register(client, "sweep-csrf")
        transport = httpx.ASGITransport(app=app)
        # The same session, without the header: what a cross-site form would send.
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", cookies=client.cookies
        ) as bare:
            mutating = sorted(op for op in operations(app) if op[0] in MUTATING)
            # The stream route of this step is in the sweep.
            assert ("post", "/api/ingest/batch") in mutating
            ids = {
                "job_id": uuid.uuid4(),
                "device_id": uuid.uuid4(),
                "rec_id": uuid.uuid4(),
                "code": "R1",
            }
            for method, path in mutating:
                response = await call(bare, method, path.format(**ids), {})
                assert response.status_code == 403, f"{method} {path}: {response.status_code}"
            batch = await bare.post(
                "/api/ingest/batch", json={"records": days_file(0).decode().splitlines()}
            )
            assert batch.status_code == 403

            # Nothing changed: still logged in, no job, no clock offset, rules on.
            assert (await bare.get("/api/auth/me")).status_code == 200
            assert (await bare.get("/api/ingest/jobs")).json() == []
            assert (await bare.get("/api/dev/clock")).json()["offset_seconds"] == 0
            assert all(r["enabled"] for r in (await bare.get("/api/rules")).json())
    async with db_engine.connect() as conn:
        query = text("SELECT count(*) FROM jobs WHERE user_id = :u")
        jobs = await conn.scalar(query, {"u": user_id})
    assert jobs == 0


async def test_all_dev_routes_404_in_prod(
    clean: None, migrated_database_url: str, tmp_path: Path
) -> None:
    async with two_clients(make_settings(migrated_database_url, tmp_path, "dev")) as (_, dev_app):
        dev_routes = sorted(op for op in operations(dev_app) if op[1].startswith("/api/dev/"))
    assert dev_routes, "the dev app has no dev routes: the sweep would check nothing"

    async with two_clients(make_settings(migrated_database_url, tmp_path, "prod")) as (
        client,
        prod_app,
    ):
        assert not [op for op in operations(prod_app) if op[1].startswith("/api/dev/")]
        for method, path in dev_routes:
            body = {"offset_seconds": 60} if method in MUTATING else None
            response = await call(client, method, path, body)
            assert response.status_code == 404, f"{method} {path}: {response.status_code}"
