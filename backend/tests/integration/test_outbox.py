"""The e-mail outbox (SPEC F9, F10, §7.1; plan step 9.2): an opened recommendation and its
outbox entry are written in one transaction — when it is rolled back, neither is left.

A rolled-back transaction like test_rule_engine_db.py; the tables are read with plain SQL.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.rules.engine import evaluate_user
from tests.integration.ingest import NOW, make_user
from tests.integration.test_rule_engine_db import TODAY, add_days, night


@pytest.fixture
async def session(
    test_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with test_sessionmaker() as s:
        yield s


async def outbox(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    result = await session.execute(
        text(
            "SELECT recommendation_id, status, digest_id, created_at FROM email_outbox"
            " WHERE user_id = :user_id ORDER BY created_at"
        ),
        {"user_id": user_id},
    )
    return [dict(row._mapping) for row in result]


async def open_ids(session: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    result = await session.scalars(
        text("SELECT id FROM recommendations WHERE user_id = :user_id AND status = 'open'"),
        {"user_id": user_id},
    )
    return list(result)


async def test_outbox_row_in_same_transaction_as_open(session: AsyncSession) -> None:
    user_id = await make_user(session)
    await add_days(session, user_id, *[night(TODAY - timedelta(days=i), 5) for i in (2, 1, 0)])

    opening = await session.begin_nested()
    actions = await evaluate_user(session, user_id, NOW)
    assert [(a.code, a.kind) for a in actions] == [("R1", "open")]
    [rec_id] = await open_ids(session, user_id)
    assert await outbox(session, user_id) == [
        {"recommendation_id": rec_id, "status": "pending", "digest_id": None, "created_at": NOW}
    ]
    # The same rule fires again an hour later: still one recommendation, one entry.
    assert await evaluate_user(session, user_id, NOW + timedelta(hours=1)) == []
    assert len(await outbox(session, user_id)) == 1

    await opening.rollback()
    assert await open_ids(session, user_id) == []
    assert await outbox(session, user_id) == []
