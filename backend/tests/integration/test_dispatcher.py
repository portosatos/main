"""The digest dispatcher (SPEC F10; plan step 9.2): the worker's tick plans the digest of the
pending outbox entries and sends one letter with every recommendation still open when it is due.

These commit for real, like test_rule_triggers.py: the worker uses its own sessions. Users get
`@jobs.example.com` addresses and are deleted by the `clean` fixture. Letters go to a fake
mailer; test_mailpit.py sends a real one.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, date, datetime, time, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.db import create_sessionmaker
from app.models import Recommendation
from app.services.notify import outbox
from app.services.notify.mailer import SmtpMailer
from app.services.rules.catalog import TITLES
from tests.integration.ingest import make_user, ndjson
from tests.integration.test_goals import api_user, listen, of_type
from tests.integration.test_ingest_jobs import (
    META,
    MovableClock,
    day_records,
    make_worker,
    wait_until,
    wipe,
)

T = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
APP_URL = "http://localhost:5173"


class BrokenMailer:
    """An SMTP server that refuses every letter."""

    def __init__(self) -> None:
        self.attempts = 0

    async def send(self, message: EmailMessage) -> None:
        self.attempts += 1
        raise ConnectionRefusedError("smtp is down")


class FakeMailer:
    """Keeps the letters instead of sending them."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


@pytest.fixture
async def clean(db_engine: AsyncEngine) -> AsyncIterator[None]:
    await wipe(db_engine)
    yield
    await wipe(db_engine)


@pytest.fixture
def settings(migrated_database_url: str, tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=migrated_database_url,
        app_env="test",
        ingest_dir=tmp_path / "ingest",
    )


async def committed_user(engine: AsyncEngine, name: str) -> tuple[uuid.UUID, str]:
    """A committed user in UTC whose digest address is the login; (id, address)."""
    email = f"{name}-{uuid.uuid4().hex[:8]}@jobs.example.com"
    async with create_sessionmaker(engine)() as session:
        user_id = await make_user(session, email=email)
        await session.commit()
    return user_id, email


async def open_rec(engine: AsyncEngine, user_id: uuid.UUID, code: str, at: datetime) -> uuid.UUID:
    """An open recommendation of `code` and its outbox entry, as the engine opens it at `at`."""
    rec_id = uuid.uuid4()
    async with create_sessionmaker(engine)() as session:
        session.add(
            Recommendation(
                id=rec_id,
                user_id=user_id,
                rule_code=code,
                status="open",
                opened_at=at,
                anchor_date=at.date(),
                context={},
            )
        )
        await session.flush()
        await outbox.enqueue(session, user_id, rec_id, at)
        await session.commit()
    return rec_id


async def resolve(engine: AsyncEngine, rec_id: uuid.UUID, at: datetime) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE recommendations SET status = 'resolved', resolved_at = :at,"
                " resolve_reason = 'auto' WHERE id = :id"
            ),
            {"id": rec_id, "at": at},
        )


async def outbox_rows(engine: AsyncEngine, user_id: uuid.UUID) -> dict[uuid.UUID, dict]:
    """The user's outbox entries by recommendation id."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT recommendation_id, status, digest_id FROM email_outbox WHERE user_id = :u"
            ),
            {"u": user_id},
        )
        return {row.recommendation_id: dict(row._mapping) for row in result}


async def digests(engine: AsyncEngine, user_id: uuid.UUID) -> list[dict]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT id, local_date, to_email, subject, planned_at, plan_reason, sent_at, error"
                " FROM email_digests WHERE user_id = :u ORDER BY planned_at"
            ),
            {"u": user_id},
        )
        return [dict(row._mapping) for row in result]


async def tick(engine: AsyncEngine, at: datetime, mailer: Any) -> None:
    """One digest tick of a worker whose Clock says `at`."""
    await make_worker(engine, MovableClock(at), mailer=mailer).digest_tick()


def bodies(message: EmailMessage) -> tuple[str, str]:
    """The text and the HTML part of a letter."""
    plain = message.get_body(("plain",))
    html = message.get_body(("html",))
    assert plain is not None and html is not None, "the letter needs a text and an HTML part"
    return plain.get_content(), html.get_content()


async def digest_list(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get("/api/digests")
    assert response.status_code == 200, response.text
    return response.json()


async def test_one_email_with_all_pending(clean: None, db_engine: AsyncEngine) -> None:
    user_id, email = await committed_user(db_engine, "digest-all")
    recs = [
        await open_rec(db_engine, user_id, "R1", T),
        await open_rec(db_engine, user_id, "R2", T + timedelta(minutes=5)),
        await open_rec(db_engine, user_id, "R3", T + timedelta(minutes=10)),
    ]
    mailer = FakeMailer()

    # Due 15 minutes after the last one: nothing yet a minute before, but the plan is stored.
    await tick(db_engine, T + timedelta(minutes=24), mailer)
    assert mailer.sent == []
    [planned] = await digests(db_engine, user_id)
    assert planned["planned_at"] == T + timedelta(minutes=25)
    assert planned["plan_reason"] == "window"
    assert planned["sent_at"] is None

    await tick(db_engine, T + timedelta(minutes=25), mailer)
    [letter] = mailer.sent
    assert letter["To"] == email
    assert letter["Subject"] == "Трекер здоровья: 3 новые рекомендации"
    plain, html = bodies(letter)
    for code in ("R1", "R2", "R3"):
        assert TITLES[code] in plain
        assert TITLES[code] in html
    assert f"{APP_URL}/recommendations" in plain
    assert f'href="{APP_URL}/recommendations"' in html

    [sent] = await digests(db_engine, user_id)
    assert sent | {"id": None} == {
        "id": None,
        "local_date": date(2026, 10, 10),
        "to_email": email,
        "subject": "Трекер здоровья: 3 новые рекомендации",
        "planned_at": T + timedelta(minutes=25),
        "plan_reason": "window",
        "sent_at": T + timedelta(minutes=25),
        "error": None,
    }
    rows = await outbox_rows(db_engine, user_id)
    assert {rec: (r["status"], r["digest_id"]) for rec, r in rows.items()} == {
        rec: ("sent", sent["id"]) for rec in recs
    }


async def test_repeated_tick_no_resend(clean: None, db_engine: AsyncEngine) -> None:
    user_id, _email = await committed_user(db_engine, "digest-once")
    await open_rec(db_engine, user_id, "R1", T)
    mailer = FakeMailer()
    due = T + timedelta(minutes=15)

    # Two workers tick at the same moment, then the ticks go on: one letter only.
    await asyncio.gather(tick(db_engine, due, mailer), tick(db_engine, due, mailer))
    for at in (due, due + timedelta(seconds=30), due + timedelta(hours=2)):
        await tick(db_engine, at, mailer)

    assert len(mailer.sent) == 1
    [sent] = await digests(db_engine, user_id)
    assert sent["sent_at"] == due


async def test_resolved_before_send_skipped_and_excluded(
    clean: None, db_engine: AsyncEngine
) -> None:
    user_id, _email = await committed_user(db_engine, "digest-skip")
    r1 = await open_rec(db_engine, user_id, "R1", T)
    r2 = await open_rec(db_engine, user_id, "R2", T + timedelta(minutes=1))
    await resolve(db_engine, r1, T + timedelta(minutes=5))
    mailer = FakeMailer()

    await tick(db_engine, T + timedelta(minutes=16), mailer)

    [letter] = mailer.sent
    assert letter["Subject"] == "Трекер здоровья: 1 новая рекомендация"
    plain, html = bodies(letter)
    assert TITLES["R2"] in plain and TITLES["R2"] in html
    assert TITLES["R1"] not in plain and TITLES["R1"] not in html
    [sent] = await digests(db_engine, user_id)
    rows = await outbox_rows(db_engine, user_id)
    assert rows[r1]["status"] == "skipped"
    assert rows[r1]["digest_id"] is None
    assert (rows[r2]["status"], rows[r2]["digest_id"]) == ("sent", sent["id"])


async def test_no_open_left_no_email_limit_not_consumed(
    clean: None, db_engine: AsyncEngine
) -> None:
    user_id, _email = await committed_user(db_engine, "digest-none")
    r1 = await open_rec(db_engine, user_id, "R1", T)
    await resolve(db_engine, r1, T + timedelta(minutes=5))
    mailer = FakeMailer()

    await tick(db_engine, T + timedelta(minutes=15), mailer)
    assert mailer.sent == []
    assert (await outbox_rows(db_engine, user_id))[r1]["status"] == "skipped"
    assert await digests(db_engine, user_id) == []  # no letter, no plan left

    # The same local day: the limit was not used, the next recommendation goes out today.
    later = T + timedelta(hours=1)
    await open_rec(db_engine, user_id, "R2", later)
    await tick(db_engine, later + timedelta(minutes=15), mailer)
    [letter] = mailer.sent
    assert letter["Subject"] == "Трекер здоровья: 1 новая рекомендация"
    [sent] = await digests(db_engine, user_id)
    assert sent["local_date"] == date(2026, 10, 10)
    assert sent["sent_at"] == later + timedelta(minutes=15)


async def test_no_notify_email_no_send_and_warning_flag(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with api_user(settings, "digest-noemail", at=T) as (client, _clock, user_id):
        before = await digest_list(client)
        assert before["warning"] is None
        assert before["notify_email"] is not None

        async with db_engine.begin() as conn:
            await conn.execute(
                text("UPDATE users SET notify_email = NULL WHERE id = :u"), {"u": user_id}
            )
        rec = await open_rec(db_engine, user_id, "R1", T)
        mailer = FakeMailer()
        await tick(db_engine, T + timedelta(hours=1), mailer)

        assert mailer.sent == []
        assert (await outbox_rows(db_engine, user_id))[rec]["status"] == "pending"
        assert await digests(db_engine, user_id) == []
        assert await digest_list(client) == {
            "notify_email": None,
            "warning": "no_notify_email",
            "pending": 1,
            "items": [],
        }


async def test_digests_api_shows_planned_at_and_reason(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    # Moscow: T is 15:00. Quiet hours 15:00–18:00 take the window's 15:15 to 18:00 (15:00 UTC).
    async with (
        api_user(settings, "digest-api", at=T) as (client, _clock, user_id),
        api_user(settings, "digest-other", at=T) as (other, _other_clock, _other_id),
    ):
        async with db_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE users SET quiet_enabled = true, quiet_start = :start,"
                    " quiet_end = :end WHERE id = :u"
                ),
                {"u": user_id, "start": time(15, 0), "end": time(18, 0)},
            )
        await open_rec(db_engine, user_id, "R1", T)
        mailer = FakeMailer()
        await tick(db_engine, T + timedelta(minutes=15), mailer)
        assert mailer.sent == []

        planned = await digest_list(client)
        assert planned["pending"] == 1
        assert planned["warning"] is None
        [item] = planned["items"]
        assert item | {"id": None} == {
            "id": None,
            "status": "planned",
            "local_date": "2026-10-10",
            "planned_at": "2026-10-10T15:00:00Z",
            "plan_reason": "quiet_hours",
            "sent_at": None,
            "to_email": None,
            "subject": None,
            "recommendations": 1,
            "error": None,
        }

        async with listen(settings.database_url, user_id) as events:
            await tick(db_engine, datetime(2026, 10, 10, 15, 0, tzinfo=UTC), mailer)
            found = await events.until("digest.sent")
        assert len(mailer.sent) == 1

        sent = await digest_list(client)
        assert sent["pending"] == 0
        [item] = sent["items"]
        assert item["status"] == "sent"
        assert item["planned_at"] == "2026-10-10T15:00:00Z"
        assert item["plan_reason"] == "quiet_hours"
        assert item["sent_at"] == "2026-10-10T15:00:00Z"
        assert item["subject"] == "Трекер здоровья: 1 новая рекомендация"
        assert item["to_email"] == planned["notify_email"]
        assert item["recommendations"] == 1
        assert of_type(found, "digest.sent") == [
            {"id": item["id"], "local_date": "2026-10-10", "count": 1}
        ]
        # Another user sees none of it.
        assert (await digest_list(other))["items"] == []


# Beyond the plan's list (the user's conditions on assumption 5, ADR-050): a failed send rolls
# back its transaction, yet the error is kept on the planned digest; a hanging SMTP server is cut
# off by the timeout, so it does not hold the transaction and the lock.


async def test_smtp_failure_rolls_back_send_and_keeps_error(
    clean: None, db_engine: AsyncEngine
) -> None:
    user_id, _email = await committed_user(db_engine, "digest-broken")
    rec = await open_rec(db_engine, user_id, "R1", T)
    broken = BrokenMailer()
    due = T + timedelta(minutes=15)

    await tick(db_engine, due, broken)

    assert broken.attempts == 1
    [planned] = await digests(db_engine, user_id)
    assert planned["sent_at"] is None
    assert "smtp is down" in planned["error"]
    assert (await outbox_rows(db_engine, user_id))[rec] == {
        "recommendation_id": rec,
        "status": "pending",
        "digest_id": None,
    }

    # The next tick tries again; the letter goes out and the error is cleared.
    mailer = FakeMailer()
    await tick(db_engine, due + timedelta(seconds=30), mailer)
    assert len(mailer.sent) == 1
    [sent] = await digests(db_engine, user_id)
    assert sent["id"] == planned["id"]
    assert sent["sent_at"] == due + timedelta(seconds=30)
    assert sent["planned_at"] == due
    assert sent["error"] is None
    assert (await outbox_rows(db_engine, user_id))[rec]["status"] == "sent"


async def test_hanging_smtp_cut_off_by_timeout(clean: None, db_engine: AsyncEngine) -> None:
    # A server that accepts the connection and never says a word.
    connections: list[asyncio.StreamWriter] = []

    async def silent(_reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        connections.append(writer)

    server = await asyncio.start_server(silent, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    user_id, _email = await committed_user(db_engine, "digest-hang")
    await open_rec(db_engine, user_id, "R1", T)
    try:
        loop = asyncio.get_running_loop()
        started = loop.time()
        await tick(
            db_engine, T + timedelta(minutes=15), SmtpMailer("127.0.0.1", port, timeout_s=0.5)
        )
        elapsed = loop.time() - started
    finally:
        for writer in connections:
            writer.close()
        server.close()
        await server.wait_closed()

    assert connections, "the mailer did not connect"
    assert elapsed < 5
    [planned] = await digests(db_engine, user_id)
    assert planned["sent_at"] is None
    assert "Timeout" in planned["error"]


async def test_cleared_address_drops_planned_digest(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    # Added after the code (found on step 10.1, the settings page clears the address): a digest
    # planned while there was an address must not stay "planned" once it is gone — no letter
    # will go. The entries keep waiting and are planned again when an address is set.
    async with api_user(settings, "digest-cleared", at=T) as (client, _clock, user_id):
        await open_rec(db_engine, user_id, "R1", T)
        mailer = FakeMailer()
        await tick(db_engine, T + timedelta(minutes=1), mailer)
        assert [i["status"] for i in (await digest_list(client))["items"]] == ["planned"]

        cleared = await client.patch("/api/settings", json={"notify_email": ""})
        assert cleared.status_code == 200, cleared.text
        await tick(db_engine, T + timedelta(minutes=2), mailer)
        assert await digest_list(client) == {
            "notify_email": None,
            "warning": "no_notify_email",
            "pending": 1,
            "items": [],
        }

        restored = await client.patch("/api/settings", json={"notify_email": "back@example.com"})
        assert restored.status_code == 200, restored.text
        await tick(db_engine, T + timedelta(minutes=3), mailer)
        assert [i["status"] for i in (await digest_list(client))["items"]] == ["planned"]
        assert mailer.sent == []


@pytest.mark.xfail(strict=True, reason="step 11.1: not implemented")
async def test_digest_sent_on_time_while_queue_busy(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    # Plan step 11.1 (ADR-050, "known limitation"): the digest tick must not wait until the
    # worker has emptied the queue — a stream of batches keeps it busy for a long time.
    user_id, _email = await committed_user(db_engine, "digest-busy")
    await open_rec(db_engine, user_id, "R1", T)  # due at T+15 min
    mailer = FakeMailer()
    busy = asyncio.Event()

    async def slow_batch(_number: int) -> None:
        busy.set()
        await asyncio.sleep(0.1)

    async with api_user(settings, "queue-busy", at=T) as (client, clock, other_id):
        for day in (0, 1):  # two jobs of another user, 15 one-record batches each
            data = ndjson(META, *day_records(day)[:15])
            uploaded = await client.post(
                "/api/ingest/files", files={"file": ("busy.ndjson", data, "application/x-ndjson")}
            )
            assert uploaded.status_code == 202, uploaded.text
        worker = make_worker(
            db_engine, clock, mailer=mailer, batch_size=1, on_batch=slow_batch, digest_tick_s=0.2
        )
        stop = asyncio.Event()
        loop_task = asyncio.create_task(worker.run(stop))
        try:

            async def check(condition: Callable[[], bool]) -> bool:
                if loop_task.done():
                    loop_task.result()  # re-raise the loop's error
                return condition()

            assert await wait_until(lambda: check(busy.is_set), timeout_s=5)
            clock.at = T + timedelta(minutes=16)  # the digest is due now
            assert await wait_until(lambda: check(lambda: bool(mailer.sent)), timeout_s=1.5), (
                "the digest waited for the job queue"
            )
            async with db_engine.connect() as conn:
                unfinished = await conn.scalar(
                    text(
                        "SELECT count(*) FROM ingest_jobs WHERE user_id = :u AND status <> 'done'"
                    ),
                    {"u": other_id},
                )
            assert unfinished > 0, "the queue was still busy when the digest went"
        finally:
            stop.set()
            await asyncio.wait_for(loop_task, timeout=10)

    [letter] = mailer.sent
    assert letter["Subject"] == "Трекер здоровья: 1 новая рекомендация"
