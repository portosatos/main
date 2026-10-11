"""A real digest in Mailpit (SPEC F10, §5; plan step 9.2): the worker sends it over SMTP and the
letter is found through the Mailpit API (`/api/v1/search`, `/api/v1/message/{id}`).

Needs a running Mailpit: scripts/test.ps1 / scripts/test.sh start it with Postgres, CI has it as
a service. MAILPIT_URL and MAILPIT_SMTP_HOST / MAILPIT_SMTP_PORT override the compose defaults.
Only this module: scripts/test.sh -m mailpit
"""

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.services.notify.mailer import SmtpMailer
from app.services.rules.catalog import TITLES
from tests.integration.test_dispatcher import T, committed_user, open_rec
from tests.integration.test_ingest_jobs import MovableClock, make_worker, wipe

pytestmark = pytest.mark.mailpit

MAILPIT_URL = os.environ.get("MAILPIT_URL", "http://localhost:8025")
SMTP_HOST = os.environ.get("MAILPIT_SMTP_HOST", "localhost")
SMTP_PORT = int(os.environ.get("MAILPIT_SMTP_PORT", "1025"))
WAIT_S = 10.0


@pytest.fixture
async def mailpit() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=MAILPIT_URL, timeout=5) as client:
        try:
            (await client.get("/api/v1/info")).raise_for_status()
        except httpx.HTTPError as exc:
            pytest.fail(
                f"Mailpit is unreachable at {MAILPIT_URL} ({exc!r}). "
                "Start it: docker compose up -d --wait mailpit",
                pytrace=False,
            )
        yield client


@pytest.fixture
async def clean(db_engine: AsyncEngine) -> AsyncIterator[None]:
    await wipe(db_engine)
    yield
    await wipe(db_engine)


async def letters_to(mailpit: httpx.AsyncClient, address: str) -> list[dict[str, Any]]:
    response = await mailpit.get("/api/v1/search", params={"query": f'to:"{address}"'})
    response.raise_for_status()
    return response.json()["messages"]


@pytest.mark.xfail(strict=True, reason="step 9.2: not implemented")
async def test_digest_arrives_in_mailpit_with_subject(
    clean: None, db_engine: AsyncEngine, mailpit: httpx.AsyncClient
) -> None:
    user_id, email = await committed_user(db_engine, "mailpit")
    await open_rec(db_engine, user_id, "R1", T)
    await open_rec(db_engine, user_id, "R2", T + timedelta(minutes=5))
    worker = make_worker(
        db_engine, MovableClock(T + timedelta(minutes=20)), mailer=SmtpMailer(SMTP_HOST, SMTP_PORT)
    )

    await worker.digest_tick()

    found: list[dict[str, Any]] = []
    async with asyncio.timeout(WAIT_S):
        while not found:
            found = await letters_to(mailpit, email)
            if not found:
                await asyncio.sleep(0.2)
    [summary] = found
    assert summary["Subject"] == "Трекер здоровья: 2 новые рекомендации"
    response = await mailpit.get(f"/api/v1/message/{summary['ID']}")
    response.raise_for_status()
    letter = response.json()
    assert [to["Address"] for to in letter["To"]] == [email]
    for code in ("R1", "R2"):
        assert TITLES[code] in letter["Text"]
        assert TITLES[code] in letter["HTML"]
    assert "/recommendations" in letter["HTML"]
