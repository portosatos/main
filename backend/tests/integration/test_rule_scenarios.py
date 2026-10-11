"""Done When of step 8.2: an upload of `htgen --scenario <s>` opens the scenario's recommendation
(SPEC F9, F13); `recovery` after the other five resolves all of them.

The upload goes the way of the worker's batches — parse, classify, recompute the summaries of the
dirty dates, evaluate the rules — in a rolled-back transaction; the worker's own trigger is
tests/integration/test_rule_triggers.py. Each period is 16 days of a user in Moscow (htgen's zone)
ending on a Sunday, so the last complete ISO week ends with it; the rules are evaluated at 09:00
the next morning. A pulse point a minute keeps the files small (~40 thousand records).
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.rules.engine import evaluate_user
from app.services.summaries import recompute_dates
from tests.integration.ingest import generate, make_user, rows, upload

END = date(2026, 10, 11)  # Sunday, 2026-W41
HTGEN = ("--days", "16", "--seed", "8", "--hr-interval", "60")
# The scenario → the rules its data must open.
OPENS = {
    "short-sleep": {"R1"},
    "sedentary": {"R2", "R6"},
    "high-rhr": {"R3"},
    "irregular": {"R5"},
    "worse-week": {"R4"},
}
ALL = {"R1", "R2", "R3", "R4", "R5", "R6"}


@pytest.fixture
async def session(
    test_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with test_sessionmaker() as s:
        yield s


def morning_after(day: date) -> datetime:
    """09:00 in Moscow (UTC+3) on the day after `day`."""
    return datetime(day.year, day.month, day.day, 6, 0, tzinfo=UTC) + timedelta(days=1)


async def load_and_evaluate(
    session: AsyncSession, user_id: uuid.UUID, tmp_path: Path, last: date, *args: str
) -> None:
    """Upload htgen's file of the period ending `last`, recompute its dates, evaluate the rules
    the next morning."""
    now = morning_after(last)
    _, counts = await upload(session, user_id, generate(tmp_path, "--end", last.isoformat(), *args))
    await recompute_dates(session, user_id, counts.dirty_dates, now)
    await evaluate_user(session, user_id, now)


async def statuses(session: AsyncSession, user_id: uuid.UUID) -> dict[str, tuple[str, str | None]]:
    """{rule: (status, resolve_reason)} of the user's recommendations (one per rule here)."""
    found = await rows(
        session,
        "SELECT rule_code, status, resolve_reason FROM recommendations WHERE user_id = :u",
        u=user_id,
    )
    assert len({code for code, _, _ in found}) == len(found), found
    return {code: (status, reason) for code, status, reason in found}


# short-sleep opens R1, which is there since step 8.1.
NOT_YET = pytest.mark.xfail(strict=True, reason="step 8.2: not implemented")


@pytest.mark.parametrize(
    "scenario",
    [
        pytest.param(name, marks=() if name == "short-sleep" else NOT_YET)
        for name in [*OPENS, "recovery"]
    ],
)
async def test_scenarios_open_expected_rule(
    session: AsyncSession, tmp_path: Path, scenario: str
) -> None:
    user_id = await make_user(session, tz="Europe/Moscow")

    if scenario != "recovery":
        await load_and_evaluate(session, user_id, tmp_path, END, *HTGEN, "--scenario", scenario)

        opened = {code for code, (status, _) in (await statuses(session, user_id)).items()}
        assert OPENS[scenario] <= opened
        return

    # Two weeks earlier: all five problems at once open R1–R6 ...
    before = END - timedelta(days=14)
    await load_and_evaluate(
        session, user_id, tmp_path, before, *HTGEN, "--scenario", ",".join(OPENS)
    )
    assert await statuses(session, user_id) == {code: ("open", None) for code in ALL}
    # ... and the next two weeks of recovery resolve every one of them.
    await load_and_evaluate(
        session,
        user_id,
        tmp_path,
        END,
        *("--start", (before + timedelta(days=1)).isoformat()),
        *("--seed", "8", "--hr-interval", "60", "--scenario", "recovery"),
    )
    assert await statuses(session, user_id) == {code: ("resolved", "auto") for code in ALL}


async def test_plain_data_open_nothing(session: AsyncSession, tmp_path: Path) -> None:
    """Beyond the plan: the same period without a scenario opens no recommendation."""
    user_id = await make_user(session, tz="Europe/Moscow")

    await load_and_evaluate(session, user_id, tmp_path, END, *HTGEN)

    assert await statuses(session, user_id) == {}
