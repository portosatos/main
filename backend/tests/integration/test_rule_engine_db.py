"""Rules and recommendations in the database (SPEC F9, §7.1): the seeded rules, the partial
unique index, services/rules/engine.py::evaluate_user.

Rolled-back transactions like the other ingest tests; the tables are reached with plain SQL so
the tests do not depend on the ORM models of the step.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import date, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import DailySummary
from app.services.rules.catalog import CATALOG
from app.services.rules.engine import evaluate_user
from tests.integration.ingest import NOW, make_user

NOT_IMPLEMENTED = "step 8.1: not implemented"
TODAY = NOW.date()  # the user lives in UTC


@pytest.fixture
async def session(
    test_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with test_sessionmaker() as s:
        yield s


async def add_recommendation(
    session: AsyncSession, user_id: uuid.UUID, code: str, status: str = "open"
) -> None:
    await session.execute(
        text(
            "INSERT INTO recommendations (id, user_id, rule_code, status, opened_at, anchor_date,"
            " context) VALUES (:id, :user_id, :code, :status, :now, :day, '{}'::jsonb)"
        ),
        {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "code": code,
            "status": status,
            "now": NOW,
            "day": TODAY,
        },
    )


async def recommendations(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    result = await session.execute(
        text(
            "SELECT rule_code, status, anchor_date, context, opened_at, resolved_at,"
            " resolve_reason FROM recommendations WHERE user_id = :user_id ORDER BY opened_at"
        ),
        {"user_id": user_id},
    )
    return [dict(row._mapping) for row in result]


def night(day: date, hours: float, *, valid: bool = True) -> DailySummary:
    return DailySummary(
        local_date=day,
        status="complete",
        wear_minutes=1200,
        steps=9000,
        active_minutes=60,
        sleep_minutes=round(hours * 60),
        night_valid=valid,
        computed_at=NOW,
    )


async def add_days(session: AsyncSession, user_id: uuid.UUID, *days: DailySummary) -> None:
    for d in days:
        d.user_id = user_id
        session.add(d)
    await session.flush()


@pytest.mark.xfail(strict=True, reason=NOT_IMPLEMENTED)
async def test_rules_seeded_r1_to_r6_with_params_from_code(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT code, title, description, params, sort_order FROM rules ORDER BY sort_order")
    )
    rows = [tuple(row) for row in result]

    assert rows == [(r.code, r.title, r.description, r.params, r.sort_order) for r in CATALOG]
    assert [r[0] for r in rows] == ["R1", "R2", "R3", "R4", "R5", "R6"]


@pytest.mark.xfail(strict=True, reason=NOT_IMPLEMENTED)
async def test_partial_unique_index_prevents_two_open(session: AsyncSession) -> None:
    user_id = await make_user(session)
    other_id = await make_user(session, email="other@example.com")
    await add_recommendation(session, user_id, "R1")

    with pytest.raises(IntegrityError, match="uq_recommendations_open"):
        async with session.begin_nested():
            await add_recommendation(session, user_id, "R1")

    # Closed ones are history: any number of them next to the open one.
    await add_recommendation(session, user_id, "R1", "resolved")
    await add_recommendation(session, user_id, "R1", "closed_rule_disabled")
    # Another rule and another user are free.
    await add_recommendation(session, user_id, "R2")
    await add_recommendation(session, other_id, "R1")
    statuses = [(r["rule_code"], r["status"]) for r in await recommendations(session, user_id)]
    assert sorted(statuses) == [
        ("R1", "closed_rule_disabled"),
        ("R1", "open"),
        ("R1", "resolved"),
        ("R2", "open"),
    ]


@pytest.mark.xfail(strict=True, reason=NOT_IMPLEMENTED)
async def test_evaluate_user_opens_once_and_resolves(session: AsyncSession) -> None:
    user_id = await make_user(session)
    other_id = await make_user(session, email="other@example.com")
    short = [night(TODAY - timedelta(days=i), 5) for i in (2, 1, 0)]
    await add_days(session, user_id, *short)

    actions = await evaluate_user(session, user_id, NOW)
    again = await evaluate_user(session, user_id, NOW + timedelta(hours=1))

    assert [(a.code, a.kind) for a in actions] == [("R1", "open")]
    assert again == []
    [opened] = await recommendations(session, user_id)
    assert opened["rule_code"] == "R1"
    assert opened["status"] == "open"
    assert opened["anchor_date"] == TODAY
    assert opened["opened_at"] == NOW
    assert [n["sleep_minutes"] for n in opened["context"]["nights"]] == [300, 300, 300]
    # The other user has no data: nothing for them.
    assert await evaluate_user(session, other_id, NOW) == []
    assert await recommendations(session, other_id) == []

    # The next night is long: resolved automatically, the snapshot stays.
    later = NOW + timedelta(days=1)
    await add_days(session, user_id, night(TODAY + timedelta(days=1), 7.5))
    actions = await evaluate_user(session, user_id, later)

    assert [(a.code, a.kind) for a in actions] == [("R1", "resolve")]
    [resolved] = await recommendations(session, user_id)
    assert resolved["status"] == "resolved"
    assert resolved["resolve_reason"] == "auto"
    assert resolved["resolved_at"] == later
    assert resolved["context"] == opened["context"]


@pytest.mark.xfail(strict=True, reason=NOT_IMPLEMENTED)
async def test_evaluate_user_skips_rule_disabled_by_user(session: AsyncSession) -> None:
    user_id = await make_user(session)
    await add_days(session, user_id, *[night(TODAY - timedelta(days=i), 5) for i in (2, 1, 0)])
    await session.execute(
        text(
            "INSERT INTO user_rules (user_id, rule_code, enabled, changed_at)"
            " VALUES (:user_id, 'R1', false, :now)"
        ),
        {"user_id": user_id, "now": NOW},
    )

    assert await evaluate_user(session, user_id, NOW) == []
    assert await recommendations(session, user_id) == []
    # Enabled explicitly: evaluated as by default.
    await session.execute(
        text("UPDATE user_rules SET enabled = true WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    assert [a.code for a in await evaluate_user(session, user_id, NOW)] == ["R1"]
