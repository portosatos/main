import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clock import Clock
from app.seed import seed_demo_user
from tests.integration.client import CSRF_HEADERS, api_client

pytestmark = pytest.mark.xfail(strict=True, reason="step 1.2: not implemented")

PASSWORD = "correct horse battery"
SESSION_TTL = timedelta(days=14)
Sessionmaker = async_sessionmaker[AsyncSession]


async def register(
    client: httpx.AsyncClient,
    email: str = "user@example.com",
    password: str = PASSWORD,
    timezone: str = "Europe/Moscow",
    **kwargs: Any,
) -> httpx.Response:
    body = {"email": email, "password": password, "timezone": timezone}
    return await client.post("/api/auth/register", json=body, **kwargs)


async def login(
    client: httpx.AsyncClient, email: str = "user@example.com", password: str = PASSWORD
) -> httpx.Response:
    return await client.post("/api/auth/login", json={"email": email, "password": password})


def session_cookie(response: httpx.Response) -> dict[str, str]:
    """The ht_session Set-Cookie header: {"value": ..., "<attribute in lower case>": ...}."""
    headers = response.headers.get_list("set-cookie")
    for header in headers:
        name_value, *attributes = (part.strip() for part in header.split(";"))
        name, _, value = name_value.partition("=")
        if name == "ht_session":
            cookie = {"value": value}
            for attribute in attributes:
                key, _, attr_value = attribute.partition("=")
                cookie[key.lower()] = attr_value
            return cookie
    raise AssertionError(f"no ht_session cookie in Set-Cookie: {headers}")


async def scalar(sessionmaker: Sessionmaker, sql: str, **params: Any) -> Any:
    async with sessionmaker() as session:
        return await session.scalar(text(sql), params)


async def count_users(sessionmaker: Sessionmaker) -> int:
    return await scalar(sessionmaker, "SELECT count(*) FROM users")


async def test_register_sets_httponly_samesite_lax_cookie(
    migrated_database_url: str, test_sessionmaker: Sessionmaker
) -> None:
    async with api_client(migrated_database_url, sessionmaker=test_sessionmaker) as client:
        registered = await register(client)
        me = await client.get("/api/auth/me")

    assert registered.status_code == 201, registered.text
    assert registered.json()["email"] == "user@example.com"
    # SPEC F1: the address for emails defaults to the login.
    assert registered.json()["notify_email"] == "user@example.com"

    cookie = session_cookie(registered)
    assert "httponly" in cookie
    assert cookie.get("samesite", "").lower() == "lax"
    assert cookie.get("path") == "/"
    assert cookie.get("max-age") == str(int(SESSION_TTL.total_seconds()))
    assert "secure" not in cookie, "Secure only in prod: the dev stack is plain http"

    # Only a hash of the random token is stored on the server.
    token = cookie["value"]
    assert len(token) >= 32
    stored = await scalar(test_sessionmaker, "SELECT id FROM sessions")
    assert stored == hashlib.sha256(token.encode()).hexdigest()

    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"


async def test_register_duplicate_email_409(
    migrated_database_url: str, test_sessionmaker: Sessionmaker
) -> None:
    async with api_client(migrated_database_url, sessionmaker=test_sessionmaker) as client:
        first = await register(client, email="twin@example.com")
        same = await register(client, email="twin@example.com")
        other_case = await register(client, email="Twin@Example.COM")

    assert first.status_code == 201
    assert same.status_code == 409
    assert other_case.status_code == 409, "emails are case-insensitive (citext)"
    assert await count_users(test_sessionmaker) == 1


@pytest.mark.parametrize("timezone", ["Mars/Olympus", "", "../../etc/passwd", "UTC+3"])
async def test_register_invalid_timezone_422(
    migrated_database_url: str, test_sessionmaker: Sessionmaker, timezone: str
) -> None:
    async with api_client(migrated_database_url, sessionmaker=test_sessionmaker) as client:
        response = await register(client, timezone=timezone)

    assert response.status_code == 422
    assert await count_users(test_sessionmaker) == 0


@pytest.mark.parametrize(
    ("email", "password"),
    [("user@example.com", "1234567"), ("not-an-email", PASSWORD), ("", PASSWORD)],
)
async def test_register_rejects_bad_email_or_short_password_422(
    migrated_database_url: str, test_sessionmaker: Sessionmaker, email: str, password: str
) -> None:
    async with api_client(migrated_database_url, sessionmaker=test_sessionmaker) as client:
        response = await register(client, email=email, password=password)

    assert response.status_code == 422
    assert await count_users(test_sessionmaker) == 0


async def test_register_creates_initial_timezone_record(
    migrated_database_url: str, test_sessionmaker: Sessionmaker
) -> None:
    shift = timedelta(days=30)
    async with api_client(migrated_database_url, sessionmaker=test_sessionmaker) as client:
        moved = await client.post(
            "/api/dev/clock", json={"offset_seconds": int(shift.total_seconds())}
        )
        registered = await register(client, timezone="Asia/Almaty")
    assert moved.status_code == 200
    assert registered.status_code == 201

    async with test_sessionmaker() as session:
        rows = (
            await session.execute(
                text("SELECT tz, valid_from FROM user_timezones WHERE user_id = :id"),
                {"id": registered.json()["id"]},
            )
        ).all()

    assert len(rows) == 1
    tz, valid_from = rows[0]
    assert tz == "Asia/Almaty"
    # valid_from is the moment of registration by Clock (dev offset included).
    assert abs(valid_from - (datetime.now(UTC) + shift)) < timedelta(minutes=1)


async def test_login_wrong_password_401(
    migrated_database_url: str, test_sessionmaker: Sessionmaker
) -> None:
    async with api_client(migrated_database_url, sessionmaker=test_sessionmaker) as client:
        await register(client)
        client.cookies.clear()
        wrong_password = await login(client, password=PASSWORD + "!")
        unknown_email = await login(client, email="nobody@example.com")
        me_after_failures = await client.get("/api/auth/me")
        correct = await login(client, email="USER@example.com")
        me = await client.get("/api/auth/me")

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    # The same answer, so login does not reveal which emails are registered.
    assert wrong_password.json() == unknown_email.json()
    assert "set-cookie" not in wrong_password.headers
    assert me_after_failures.status_code == 401

    assert correct.status_code == 200
    assert "httponly" in session_cookie(correct)
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"


async def test_me_without_cookie_401(
    migrated_database_url: str, test_sessionmaker: Sessionmaker
) -> None:
    async with api_client(migrated_database_url, sessionmaker=test_sessionmaker) as client:
        no_cookie = await client.get("/api/auth/me")
        unknown_token = await client.get(
            "/api/auth/me", headers={"Cookie": "ht_session=not-a-real-token"}
        )

    assert no_cookie.status_code == 401
    assert unknown_token.status_code == 401


async def test_mutating_request_without_csrf_header_403(
    migrated_database_url: str, test_sessionmaker: Sessionmaker
) -> None:
    async with api_client(
        migrated_database_url, sessionmaker=test_sessionmaker, csrf=False
    ) as client:
        rejected = {
            "register": await register(client),
            "login": await login(client),
            "logout": await client.post("/api/auth/logout"),
            "dev clock": await client.post("/api/dev/clock", json={"offset_seconds": 60}),
            "wrong header value": await register(
                client, headers={"X-Requested-With": "XMLHttpRequest"}
            ),
            "patch, any path": await client.patch("/api/anything", json={}),
            "delete, any path": await client.delete("/api/anything"),
        }
        dev_clock = await client.get("/api/dev/clock")
        me = await client.get("/api/auth/me")
        # Control: the same request with the header gets through.
        with_header = await register(client, headers=CSRF_HEADERS)

    for name, response in rejected.items():
        assert response.status_code == 403, f"{name}: {response.status_code}"
    assert dev_clock.json()["offset_seconds"] == 0, "the rejected POST must not change anything"
    assert me.status_code == 401, "reads need no CSRF header"
    assert with_header.status_code == 201
    assert await count_users(test_sessionmaker) == 1


async def test_logout_invalidates_session(
    migrated_database_url: str, test_sessionmaker: Sessionmaker
) -> None:
    async with api_client(migrated_database_url, sessionmaker=test_sessionmaker) as client:
        registered = await register(client)
        token = session_cookie(registered)["value"]
        logged_out = await client.post("/api/auth/logout")
        client.cookies.clear()
        # The old token, as if someone kept a copy of the cookie.
        reused = await client.get("/api/auth/me", headers={"Cookie": f"ht_session={token}"})
        logout_again = await client.post("/api/auth/logout")

    assert logged_out.status_code == 204
    assert session_cookie(logged_out).get("max-age") == "0", "the browser cookie is cleared"
    assert reused.status_code == 401
    assert await scalar(test_sessionmaker, "SELECT count(*) FROM sessions") == 0
    assert logout_again.status_code == 204, "logout without a session is a no-op"


async def test_session_expires_after_14_days_by_clock(
    migrated_database_url: str, test_sessionmaker: Sessionmaker
) -> None:
    ttl = int(SESSION_TTL.total_seconds())
    async with api_client(migrated_database_url, sessionmaker=test_sessionmaker) as client:
        registered = await register(client)
        await client.post("/api/dev/clock", json={"offset_seconds": ttl - 60})
        almost_expired = await client.get("/api/auth/me")
        await client.post("/api/dev/clock", json={"offset_seconds": ttl + 60})
        expired = await client.get("/api/auth/me")

    assert registered.status_code == 201
    assert almost_expired.status_code == 200
    assert expired.status_code == 401


async def test_cookie_secure_flag_in_prod(
    migrated_database_url: str, test_sessionmaker: Sessionmaker
) -> None:
    async with api_client(migrated_database_url, "prod", test_sessionmaker) as client:
        registered = await register(client)

    assert registered.status_code == 201
    cookie = session_cookie(registered)
    assert "secure" in cookie
    assert "httponly" in cookie
    assert cookie.get("samesite", "").lower() == "lax"


async def demo_login(database_url: str, sessionmaker: Sessionmaker, password: str) -> int:
    async with api_client(database_url, sessionmaker=sessionmaker) as client:
        response = await login(client, email="demo@example.com", password=password)
    return response.status_code


async def test_seed_demo_user_idempotent(
    migrated_database_url: str, test_sessionmaker: Sessionmaker
) -> None:
    clock = Clock(app_env="test")
    for _ in range(2):
        async with test_sessionmaker() as session:
            await seed_demo_user(
                session,
                clock,
                email="demo@example.com",
                password=PASSWORD,
                timezone="Europe/Moscow",
            )

    assert await count_users(test_sessionmaker) == 1
    user_id = await scalar(test_sessionmaker, "SELECT id FROM users")
    timezones = await scalar(
        test_sessionmaker, "SELECT count(*) FROM user_timezones WHERE user_id = :id", id=user_id
    )
    assert timezones == 1
    assert await demo_login(migrated_database_url, test_sessionmaker, PASSWORD) == 200

    # A new password in the environment takes effect on the next start; the user stays the same.
    async with test_sessionmaker() as session:
        await seed_demo_user(
            session, clock, email="demo@example.com", password="new password", timezone="UTC"
        )
    assert await scalar(test_sessionmaker, "SELECT id FROM users") == user_id
    assert await demo_login(migrated_database_url, test_sessionmaker, "new password") == 200
    assert await demo_login(migrated_database_url, test_sessionmaker, PASSWORD) == 401


async def test_swagger_ui_sends_csrf_header(migrated_database_url: str) -> None:
    """/docs must stay usable for manual checks: Swagger adds the header to its requests."""
    async with api_client(migrated_database_url) as client:
        docs = await client.get("/docs")

    assert docs.status_code == 200
    assert "requestInterceptor" in docs.text
    assert "X-Requested-With" in docs.text
