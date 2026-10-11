"""The rule engine (SPEC F9): the state machine of a (user, rule) pair and the evaluation of a
user's enabled rules against the stored recommendations.

`plan_actions` is pure: verdicts of the enabled rules and the codes with an open recommendation
in, the actions out — `fire` without an open one opens, `close` with an open one resolves,
everything else changes nothing. `evaluate_user` loads the facts and applies the actions in the
caller's transaction (the worker's, which holds the user lock); the partial unique index on open
recommendations stops a second open one even if two evaluations race.

Step 8.1 writes the recommendations only: the bell, the events and the e-mail outbox come with
steps 8.3 and 9.x.
"""

import uuid
from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Literal

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailySummary, Recommendation, UserRule
from app.models.rule import OPEN
from app.services.goals import GoalKind, load_goal_book
from app.services.localtime import TzHistory, load_tz_history
from app.services.rules import r1, r2, r3, r4, r5, r6
from app.services.rules.base import Day, Facts, Rule, default_goal

log = structlog.get_logger(__name__)

# The rules the engine evaluates, in the order of the catalog.
RULES: tuple[Rule, ...] = (r1.RULE, r2.RULE, r3.RULE, r4.RULE, r5.RULE, r6.RULE)
# The dates the rules may read start this far before today (R4: two weeks before a Sunday).
LOOKBACK = timedelta(days=max(rule.window_days for rule in RULES))


@dataclass(frozen=True)
class Action:
    code: str
    kind: Literal["open", "resolve"]
    anchor_date: date
    context: dict[str, Any] = field(default_factory=dict)


def plan_actions(
    rules: Sequence[Rule],
    facts: Facts,
    *,
    enabled: Collection[str],
    open_codes: Collection[str],
) -> list[Action]:
    """The actions of the enabled `rules` on `facts`; `open_codes` — the rules with an open
    recommendation. A disabled rule is not evaluated at all."""
    actions = []
    for rule in rules:
        if rule.code not in enabled:
            continue
        at = rule.anchor(facts)
        verdict = rule.evaluate(facts, at)
        is_open = rule.code in open_codes
        if verdict.kind == "fire" and not is_open:
            actions.append(Action(rule.code, "open", at, verdict.context))
        elif verdict.kind == "close" and is_open:
            actions.append(Action(rule.code, "resolve", at, verdict.context))
        # fire with an open one, close with none, hold, unknown: nothing changes (SPEC F6, F9)
    return actions


def day_of(summary: DailySummary) -> Day:
    return Day(
        summary.local_date,
        status=summary.status,  # type: ignore[arg-type]
        wear_minutes=summary.wear_minutes,
        steps=summary.steps,
        active_minutes=summary.active_minutes,
        sleep_minutes=summary.sleep_minutes,
        sleep_start=summary.sleep_start,
        sleep_end=summary.sleep_end,
        night_valid=summary.night_valid,
        resting_hr=summary.resting_hr,
        peak_hr=summary.peak_hr,
    )


def make_facts(
    days: Iterable[Day],
    history: TzHistory,
    now: datetime,
    goal: Callable[[GoalKind, date], float] = default_goal,
) -> Facts:
    """The facts of `days`: today is the local date of `now` (Clock) by the user's zones, and
    local times are in the zone in effect at each instant."""
    return Facts(
        days,
        history.local_date(now),
        goal,
        local_time=lambda ts: ts.astimezone(history.zone_at(ts)),
    )


async def users_with_recent_data(session: AsyncSession, now: datetime) -> list[uuid.UUID]:
    """The users with a daily summary the rules may read at `now` (the hourly evaluation)."""
    raise NotImplementedError("step 8.2")


async def load_facts(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> Facts:
    """The user's summaries the rules may read, today by `now` and the user's time zone, and the
    steps and sleep goals of every date."""
    history = await load_tz_history(session, user_id)
    today = history.local_date(now)
    book = await load_goal_book(session, user_id, history)
    summaries = await session.scalars(
        select(DailySummary).where(
            DailySummary.user_id == user_id,
            DailySummary.local_date.between(today - LOOKBACK, today),
        )
    )
    return make_facts([day_of(s) for s in summaries], history, now, book.target)


async def evaluate_user(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> list[Action]:
    """Evaluate the user's enabled rules and open or resolve their recommendations; `now` is
    from Clock. Returns the actions applied. A rule without a user_rules row is enabled."""
    disabled = set(
        await session.scalars(
            select(UserRule.rule_code).where(UserRule.user_id == user_id, ~UserRule.enabled)
        )
    )
    enabled = {rule.code for rule in RULES} - disabled
    if not enabled:
        return []
    open_codes = set(
        await session.scalars(
            select(Recommendation.rule_code).where(
                Recommendation.user_id == user_id, Recommendation.status == "open"
            )
        )
    )
    facts = await load_facts(session, user_id, now)
    applied = []
    for action in plan_actions(RULES, facts, enabled=enabled, open_codes=open_codes):
        if action.kind == "open":
            changed = await session.scalar(
                pg_insert(Recommendation)
                .values(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    rule_code=action.code,
                    status="open",
                    opened_at=now,
                    anchor_date=action.anchor_date,
                    context=action.context,
                )
                .on_conflict_do_nothing(index_elements=["user_id", "rule_code"], index_where=OPEN)
                .returning(Recommendation.id)
            )
        else:
            changed = await session.scalar(
                update(Recommendation)
                .where(
                    Recommendation.user_id == user_id,
                    Recommendation.rule_code == action.code,
                    Recommendation.status == "open",
                )
                .values(status="resolved", resolved_at=now, resolve_reason="auto")
                .returning(Recommendation.id)
            )
        if changed is not None:  # else a concurrent evaluation got there first
            applied.append(action)
            log.info(
                "recommendation_" + ("opened" if action.kind == "open" else "resolved"),
                user_id=str(user_id),
                rule=action.code,
                anchor_date=action.anchor_date.isoformat(),
                recommendation_id=str(changed),
            )
    return applied
