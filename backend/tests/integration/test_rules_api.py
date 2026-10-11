"""Rules API (SPEC F9, F12, §6.3; plan step 8.3): the catalog with the user's switches, turning a
rule off and on again.

Like test_goals.py these commit for real: events are heard by a LISTEN connection of the test.
Users get `@jobs.example.com` addresses and are deleted by the `clean` fixture. They live in
Moscow; their only data are valid 5 h nights on D−2, D−1 and D, so at 09:00 on D (Moscow) R1
fires with the anchor D and nothing else has enough data.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.db import create_sessionmaker
from app.services.rules.catalog import CATALOG
from app.services.rules.engine import evaluate_user
from tests.integration.test_goals import api_user, listen, of_type
from tests.integration.test_ingest_jobs import wipe

pytestmark = pytest.mark.xfail(strict=True, reason="step 8.3: not implemented")

D = date(2026, 10, 10)
# 09:00 on D in Moscow.
MORNING = datetime(2026, 10, 10, 6, 0, tzinfo=UTC)


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


async def short_nights(engine: AsyncEngine, user_id: uuid.UUID, *nights: date) -> None:
    """Valid 5 h nights on `nights` (wake days) written straight into daily_summaries."""
    async with engine.begin() as conn:
        for night in nights:
            await conn.execute(
                text(
                    "INSERT INTO daily_summaries (user_id, local_date, status, wear_minutes,"
                    " sleep_minutes, night_valid, computed_at)"
                    " VALUES (:u, :d, 'partial', 600, 300, true, :at)"
                ),
                {"u": user_id, "d": night, "at": MORNING},
            )


async def evaluate(engine: AsyncEngine, user_id: uuid.UUID, now: datetime = MORNING) -> None:
    """The rules evaluated and committed, as the worker does at the end of a job."""
    async with create_sessionmaker(engine)() as session:
        await evaluate_user(session, user_id, now)
        await session.commit()


async def recommendations(engine: AsyncEngine, user_id: uuid.UUID) -> list[dict]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT id, rule_code, status, opened_at, resolved_at, resolve_reason, feedback"
                " FROM recommendations WHERE user_id = :u ORDER BY opened_at, rule_code"
            ),
            {"u": user_id},
        )
        return [dict(row._mapping) for row in result]


async def user_with_open_r1(engine: AsyncEngine, user_id: uuid.UUID) -> dict:
    await short_nights(engine, user_id, D - timedelta(days=2), D - timedelta(days=1), D)
    await evaluate(engine, user_id)
    [opened] = await recommendations(engine, user_id)
    assert (opened["rule_code"], opened["status"]) == ("R1", "open")
    return opened


async def test_list_rules_with_enabled_flag(clean: None, settings: Settings) -> None:
    async with api_user(settings, "rules-list") as (client, clock, _user_id):
        response = await client.get("/api/rules")
        assert response.status_code == 200, response.text
        rules = response.json()
        # The catalog in its order, every rule on for a new user (no user_rules row).
        assert rules == [
            {
                "code": info.code,
                "title": info.title,
                "description": info.description,
                "params": info.params,
                "enabled": True,
                "changed_at": None,
            }
            for info in CATALOG
        ]

        clock.at = MORNING
        off = await client.patch("/api/rules/R2", json={"enabled": False})
        assert off.status_code == 200, off.text
        assert off.json() == rules[1] | {"enabled": False, "changed_at": "2026-10-10T06:00:00Z"}

        listed = (await client.get("/api/rules")).json()
        assert [(r["code"], r["enabled"]) for r in listed] == [
            ("R1", True),
            ("R2", False),
            ("R3", True),
            ("R4", True),
            ("R5", True),
            ("R6", True),
        ]

        assert (await client.patch("/api/rules/R9", json={"enabled": False})).status_code == 404
        assert (await client.patch("/api/rules/R1", json={"enabled": "maybe"})).status_code == 422
        assert (await client.patch("/api/rules/R1", json={})).status_code == 422


async def test_disable_closes_open_as_closed_rule_disabled(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with api_user(settings, "rules-off") as (client, clock, user_id):
        opened = await user_with_open_r1(db_engine, user_id)

        clock.at = MORNING + timedelta(hours=1)
        async with listen(settings.database_url, user_id) as events:
            response = await client.patch("/api/rules/R1", json={"enabled": False})
            assert response.status_code == 200, response.text
            found = await events.until("rule.toggled")
        # The tabs hear of the closed recommendation before the switch.
        assert [e["type"] for e in found] == ["recommendation.resolved", "rule.toggled"]
        assert of_type(found, "recommendation.resolved") == [
            {"id": str(opened["id"]), "rule_code": "R1", "status": "closed_rule_disabled"}
        ]

        [closed] = await recommendations(db_engine, user_id)
        assert closed["id"] == opened["id"]
        assert closed["status"] == "closed_rule_disabled"
        assert closed["resolved_at"] == clock.at
        assert closed["resolve_reason"] == "rule_disabled"

        # A disabled rule is not evaluated: the same short nights open nothing.
        await evaluate(db_engine, user_id, clock.at + timedelta(hours=1))
        assert [r["status"] for r in await recommendations(db_engine, user_id)] == [
            "closed_rule_disabled"
        ]


async def test_history_preserved_after_disable(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with api_user(settings, "rules-history") as (client, clock, user_id):
        opened = await user_with_open_r1(db_engine, user_id)
        clock.at = MORNING + timedelta(minutes=10)
        rated = await client.put(
            f"/api/recommendations/{opened['id']}/feedback", json={"value": "useful"}
        )
        assert rated.status_code == 200, rated.text

        clock.at = MORNING + timedelta(hours=1)
        assert (await client.patch("/api/rules/R1", json={"enabled": False})).status_code == 200

        # The recommendation stays in the history of the rule, with its feedback.
        response = await client.get("/api/recommendations?rule=R1")
        assert response.status_code == 200, response.text
        [item] = response.json()
        assert item["id"] == str(opened["id"])
        assert item["status"] == "closed_rule_disabled"
        assert item["opened_at"] == "2026-10-10T06:00:00Z"
        assert item["resolved_at"] == "2026-10-10T07:00:00Z"
        assert item["feedback"] == "useful"
        assert (await client.get("/api/recommendations?status=open")).json() == []


async def test_reenable_triggers_evaluation(
    clean: None, settings: Settings, db_engine: AsyncEngine
) -> None:
    async with api_user(settings, "rules-on") as (client, clock, user_id):
        await user_with_open_r1(db_engine, user_id)
        clock.at = MORNING + timedelta(hours=1)
        assert (await client.patch("/api/rules/R1", json={"enabled": False})).status_code == 200

        # Turned on again: evaluated at once, without the worker; the nights are still short.
        clock.at = MORNING + timedelta(hours=2)
        async with listen(settings.database_url, user_id) as events:
            response = await client.patch("/api/rules/R1", json={"enabled": True})
            assert response.status_code == 200, response.text
            assert response.json()["enabled"] is True
            found = await events.until("rule.toggled")

        old, new = await recommendations(db_engine, user_id)
        assert old["status"] == "closed_rule_disabled"
        assert (new["rule_code"], new["status"], new["opened_at"]) == ("R1", "open", clock.at)

        # Opening tells the bell and the tabs (SPEC F9): a notification and its events.
        types = [e["type"] for e in found]
        assert types == ["notification.created", "recommendation.opened", "rule.toggled"]
        [created] = of_type(found, "notification.created")
        assert of_type(found, "recommendation.opened") == [
            {"id": str(new["id"]), "rule_code": "R1", "anchor_date": D.isoformat()}
        ]
        feed = (await client.get("/api/notifications")).json()
        assert feed["unread"] == 1
        [item] = feed["items"]
        assert (item["id"], item["type"]) == (created["id"], "recommendation.opened")
        assert item["payload"] == {
            "recommendation_id": str(new["id"]),
            "rule_code": "R1",
            "title": "Недосып",
            "anchor_date": D.isoformat(),
        }


async def test_toggle_emits_event(clean: None, settings: Settings, db_engine: AsyncEngine) -> None:
    async with api_user(settings, "rules-event") as (client, clock, user_id):
        clock.at = MORNING
        async with listen(settings.database_url, user_id) as events:
            assert (await client.patch("/api/rules/R2", json={"enabled": False})).status_code == 200
            assert of_type(await events.until("rule.toggled"), "rule.toggled") == [
                {"code": "R2", "enabled": False}
            ]

            # The same state again changes nothing: no event, the time of the switch stays.
            again = await client.patch("/api/rules/R2", json={"enabled": False})
            assert again.status_code == 200, again.text
            assert again.json()["changed_at"] == "2026-10-10T06:00:00Z"
            assert await events.quiet() == []

            clock.at = MORNING + timedelta(minutes=5)
            assert (await client.patch("/api/rules/R2", json={"enabled": True})).status_code == 200
            assert of_type(await events.until("rule.toggled"), "rule.toggled") == [
                {"code": "R2", "enabled": True}
            ]
