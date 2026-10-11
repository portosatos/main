"""The rule engine (SPEC F9): the state machine of a (user, rule) pair and the evaluation of a
user's enabled rules against the stored recommendations.

`plan_actions` is pure: verdicts of the enabled rules and the codes with an open recommendation
in, the actions out — `fire` without an open one opens, `close` with an open one resolves,
everything else changes nothing. `evaluate_user` loads the facts and applies the actions.
"""

import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rules.base import Facts, Rule


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


async def evaluate_user(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> list[Action]:
    raise NotImplementedError("step 8.1")
