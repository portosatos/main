"""Recommendations API (SPEC F9, F12, §6.3; plan step 8.3): the active ones and the history with
filters, and the feedback on any of them.

Like test_rules_api.py these commit for real; the recommendations are written straight into the
table, so each test controls their statuses and times.
"""

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from tests.integration.test_goals import api_user, listen, of_type
from tests.integration.test_ingest_jobs import wipe

pytestmark = pytest.mark.xfail(strict=True, reason="step 8.3: not implemented")

T = datetime(2026, 10, 10, 6, 0, tzinfo=UTC)


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


async def add_recommendation(
    engine: AsyncEngine,
    user_id: uuid.UUID,
    code: str,
    status: str,
    opened_at: datetime,
    *,
    resolved_at: datetime | None = None,
    context: dict | None = None,
) -> str:
    reason = {"open": None, "resolved": "auto", "closed_rule_disabled": "rule_disabled"}[status]
    async with engine.begin() as conn:
        rec_id = await conn.scalar(
            text(
                "INSERT INTO recommendations (id, user_id, rule_code, status, opened_at,"
                " anchor_date, context, resolved_at, resolve_reason)"
                " VALUES (:id, :u, :code, :status, :opened, :anchor, CAST(:context AS jsonb),"
                " :resolved, :reason) RETURNING id"
            ),
            {
                "id": uuid.uuid4(),
                "u": user_id,
                "code": code,
                "status": status,
                "opened": opened_at,
                "anchor": opened_at.date(),
                "context": json.dumps(context or {}),
                "resolved": resolved_at,
                "reason": reason,
            },
        )
    return str(rec_id)


async def listed(client: httpx.AsyncClient, query: str = "") -> list[dict]:
    response = await client.get(f"/api/recommendations{query}")
    assert response.status_code == 200, response.text
    return response.json()


async def test_filters_by_status_and_rule(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with api_user(settings, "recs-filter") as (client, _clock, user_id):
        r1_old = await add_recommendation(
            db_engine,
            user_id,
            "R1",
            "resolved",
            T - timedelta(days=5),
            resolved_at=T - timedelta(days=3),
        )
        r2_off = await add_recommendation(
            db_engine,
            user_id,
            "R2",
            "closed_rule_disabled",
            T - timedelta(days=4),
            resolved_at=T - timedelta(days=2),
        )
        r1_open = await add_recommendation(
            db_engine,
            user_id,
            "R1",
            "open",
            T - timedelta(days=1),
            context={"short_hours": 6},
        )
        r3_open = await add_recommendation(db_engine, user_id, "R3", "open", T)

        # Everything, newest first.
        everything = await listed(client)
        assert [r["id"] for r in everything] == [r3_open, r1_open, r2_off, r1_old]
        assert everything[1] == {
            "id": r1_open,
            "rule_code": "R1",
            "title": "Недосып",
            "status": "open",
            "opened_at": "2026-10-09T06:00:00Z",
            "anchor_date": "2026-10-09",
            "context": {"short_hours": 6},
            "resolved_at": None,
            "resolve_reason": None,
            "feedback": None,
            "feedback_at": None,
        }

        # The tabs: active, and the history (both closing statuses).
        assert [r["id"] for r in await listed(client, "?status=open")] == [r3_open, r1_open]
        history = await listed(client, "?status=resolved&status=closed_rule_disabled")
        assert [(r["id"], r["status"]) for r in history] == [
            (r2_off, "closed_rule_disabled"),
            (r1_old, "resolved"),
        ]
        assert history[1]["resolved_at"] == "2026-10-07T06:00:00Z"
        assert history[1]["resolve_reason"] == "auto"

        # By rule, and both filters at once.
        assert [r["id"] for r in await listed(client, "?rule=R1")] == [r1_open, r1_old]
        assert [r["id"] for r in await listed(client, "?rule=R1&status=resolved")] == [r1_old]
        assert await listed(client, "?rule=R6") == []

        assert (await client.get("/api/recommendations?status=closed")).status_code == 422
        assert (await client.get("/api/recommendations?rule=R9")).status_code == 422


async def test_feedback_set_change_clear_with_timestamp(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with api_user(settings, "recs-feedback") as (client, clock, user_id):
        # Feedback goes on closed recommendations too.
        rec_id = await add_recommendation(
            db_engine, user_id, "R2", "resolved", T - timedelta(days=2), resolved_at=T
        )
        url = f"/api/recommendations/{rec_id}/feedback"

        clock.at = T + timedelta(hours=1)
        useful = await client.put(url, json={"value": "useful"})
        assert useful.status_code == 200, useful.text
        assert (useful.json()["feedback"], useful.json()["feedback_at"]) == (
            "useful",
            "2026-10-10T07:00:00Z",
        )
        assert useful.json()["status"] == "resolved"

        # The same value again keeps the time it was given.
        clock.at = T + timedelta(hours=2)
        same = await client.put(url, json={"value": "useful"})
        assert same.status_code == 200, same.text
        assert same.json()["feedback_at"] == "2026-10-10T07:00:00Z"

        changed = await client.put(url, json={"value": "not_useful"})
        assert changed.status_code == 200, changed.text
        assert (changed.json()["feedback"], changed.json()["feedback_at"]) == (
            "not_useful",
            "2026-10-10T08:00:00Z",
        )
        [item] = await listed(client)
        assert (item["feedback"], item["feedback_at"]) == ("not_useful", "2026-10-10T08:00:00Z")

        clock.at = T + timedelta(hours=3)
        cleared = await client.delete(url)
        assert cleared.status_code == 200, cleared.text
        assert (cleared.json()["feedback"], cleared.json()["feedback_at"]) == (None, None)
        # Clearing a cleared one is fine.
        assert (await client.delete(url)).status_code == 200

        assert (await client.put(url, json={"value": "great"})).status_code == 422
        assert (await client.put(url, json={})).status_code == 422


async def test_feedback_emits_event(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with api_user(settings, "recs-feedback-event") as (client, clock, user_id):
        rec_id = await add_recommendation(db_engine, user_id, "R1", "open", T)
        url = f"/api/recommendations/{rec_id}/feedback"
        clock.at = T + timedelta(minutes=30)
        async with listen(settings.database_url, user_id) as events:
            assert (await client.put(url, json={"value": "useful"})).status_code == 200
            assert of_type(
                await events.until("recommendation.feedback"), "recommendation.feedback"
            ) == [{"id": rec_id, "feedback": "useful"}]

            # Nothing changed: no event.
            assert (await client.put(url, json={"value": "useful"})).status_code == 200
            assert await events.quiet() == []

            assert (await client.delete(url)).status_code == 200
            assert of_type(
                await events.until("recommendation.feedback"), "recommendation.feedback"
            ) == [{"id": rec_id, "feedback": None}]


async def test_other_user_recommendation_404(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with (
        api_user(settings, "recs-alice") as (alice, _clock, alice_id),
        api_user(settings, "recs-bob") as (bob, _bob_clock, _bob_id),
    ):
        rec_id = await add_recommendation(db_engine, alice_id, "R1", "open", T)
        url = f"/api/recommendations/{rec_id}/feedback"

        # Bob sees none of Alice's and cannot rate or clear hers.
        assert await listed(bob) == []
        assert (await bob.put(url, json={"value": "not_useful"})).status_code == 404
        assert (await bob.delete(url)).status_code == 404
        missing = f"/api/recommendations/{uuid.uuid4()}/feedback"
        assert (await alice.put(missing, json={"value": "useful"})).status_code == 404

        [item] = await listed(alice)
        assert (item["id"], item["feedback"]) == (rec_id, None)

        # Bob turning R1 off leaves Alice's open recommendation alone.
        assert (await bob.patch("/api/rules/R1", json={"enabled": False})).status_code == 200
        [item] = await listed(alice)
        assert item["status"] == "open"
        alice_rules = (await alice.get("/api/rules")).json()
        assert all(r["enabled"] for r in alice_rules)
