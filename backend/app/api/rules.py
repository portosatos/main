"""Rule routes (SPEC F9, §6.3): R1–R6 with the user's switch, turning a rule off and on.

A rule without a user_rules row is on. Turning it off closes its open recommendation as
`closed_rule_disabled` (the history stays); turning it on evaluates the rules at once, in the
same transaction, so a condition that still holds opens a recommendation without waiting for the
worker (ADR-048). The tabs hear `recommendation.*` first, then `rule.toggled`. Switching to the
state the rule is already in changes nothing and sends nothing.
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ClockDep, SessionDep
from app.auth.deps import CurrentUserDep
from app.models import Recommendation, Rule, UserRule
from app.schemas.rules import RuleOut, RuleSwitch
from app.services import events
from app.services.rules.engine import evaluate_user, publish_resolved

router = APIRouter(prefix="/api/rules", tags=["rules"])

CLOSED_RULE_DISABLED = "closed_rule_disabled"


async def _rules(
    session: AsyncSession, user_id: uuid.UUID, code: str | None = None
) -> list[RuleOut]:
    query = (
        select(Rule, UserRule)
        .outerjoin(UserRule, (UserRule.rule_code == Rule.code) & (UserRule.user_id == user_id))
        .order_by(Rule.sort_order)
    )
    if code is not None:
        query = query.where(Rule.code == code)
    rows = await session.execute(query)
    return [
        RuleOut(
            code=rule.code,
            title=rule.title,
            description=rule.description,
            params=rule.params,
            enabled=switch is None or switch.enabled,
            changed_at=switch.changed_at if switch else None,
        )
        for rule, switch in rows.all()
    ]


@router.get("")
async def list_rules(user: CurrentUserDep, session: SessionDep) -> list[RuleOut]:
    """R1–R6 in the catalog's order, each with the user's switch."""
    return await _rules(session, user.id)


@router.patch("/{code}")
async def switch_rule(
    code: str, body: RuleSwitch, user: CurrentUserDep, session: SessionDep, clock: ClockDep
) -> RuleOut:
    """Turn the rule on or off; an unknown code is 404."""
    found = await _rules(session, user.id, code)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Правило не найдено")
    if found[0].enabled == body.enabled:
        return found[0]

    now = await clock.now()
    await session.execute(
        pg_insert(UserRule)
        .values(user_id=user.id, rule_code=code, enabled=body.enabled, changed_at=now)
        .on_conflict_do_update(
            index_elements=["user_id", "rule_code"],
            set_={"enabled": body.enabled, "changed_at": now},
        )
    )
    if body.enabled:
        await evaluate_user(session, user.id, now)
    else:
        closed = await session.scalar(
            update(Recommendation)
            .where(
                Recommendation.user_id == user.id,
                Recommendation.rule_code == code,
                Recommendation.status == "open",
            )
            .values(status=CLOSED_RULE_DISABLED, resolved_at=now, resolve_reason="rule_disabled")
            .returning(Recommendation.id)
        )
        if closed is not None:
            await publish_resolved(session, user.id, closed, code, CLOSED_RULE_DISABLED)
    await events.publish(session, user.id, "rule.toggled", {"code": code, "enabled": body.enabled})
    await session.commit()
    return (await _rules(session, user.id, code))[0]
