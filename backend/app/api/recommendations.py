"""Recommendation routes (SPEC F9, §6.3): the active ones and the history, and the feedback.

Only the session user's recommendations are listed or rated; another user's id is 404, as a
missing one. Feedback goes on any recommendation, open or closed: the same value again keeps
its time, a new value gets a new time, DELETE clears both. A change tells the user's tabs with
`recommendation.feedback` (ADR-048).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ClockDep, SessionDep
from app.auth.deps import CurrentUserDep
from app.models import Recommendation
from app.schemas.recommendations import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    FeedbackIn,
    FeedbackValue,
    RecommendationOut,
    RuleCode,
    Status,
)
from app.services import events
from app.services.rules.catalog import TITLES

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


def _out(rec: Recommendation) -> RecommendationOut:
    return RecommendationOut(
        id=rec.id,
        rule_code=rec.rule_code,
        title=TITLES[rec.rule_code],
        status=rec.status,  # type: ignore[arg-type]
        opened_at=rec.opened_at,
        anchor_date=rec.anchor_date,
        context=rec.context,
        resolved_at=rec.resolved_at,
        resolve_reason=rec.resolve_reason,
        feedback=rec.feedback,  # type: ignore[arg-type]
        feedback_at=rec.feedback_at,
    )


async def _own(session: AsyncSession, user_id: uuid.UUID, rec_id: uuid.UUID) -> Recommendation:
    rec = await session.scalar(
        select(Recommendation).where(Recommendation.id == rec_id, Recommendation.user_id == user_id)
    )
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Рекомендация не найдена")
    return rec


async def _set_feedback(
    session: AsyncSession, rec: Recommendation, value: FeedbackValue | None, clock: ClockDep
) -> RecommendationOut:
    if rec.feedback != value:
        rec.feedback = value
        rec.feedback_at = None if value is None else await clock.now()
        await events.publish(
            session, rec.user_id, "recommendation.feedback", {"id": str(rec.id), "feedback": value}
        )
        await session.commit()
    return _out(rec)


@router.get("")
async def list_recommendations(
    user: CurrentUserDep,
    session: SessionDep,
    status: Annotated[list[Status] | None, Query(description="Repeat for several")] = None,
    rule: RuleCode | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> list[RecommendationOut]:
    """The user's recommendations, newest first. «Активные» is status=open, «История» is
    status=resolved&status=closed_rule_disabled."""
    query = select(Recommendation).where(Recommendation.user_id == user.id)
    if status:
        query = query.where(Recommendation.status.in_(status))
    if rule is not None:
        query = query.where(Recommendation.rule_code == rule)
    rows = await session.scalars(
        query.order_by(Recommendation.opened_at.desc(), Recommendation.id).limit(limit)
    )
    return [_out(rec) for rec in rows]


@router.put("/{rec_id}/feedback")
async def put_feedback(
    rec_id: uuid.UUID, body: FeedbackIn, user: CurrentUserDep, session: SessionDep, clock: ClockDep
) -> RecommendationOut:
    """«Полезно» or «Не полезно»."""
    return await _set_feedback(session, await _own(session, user.id, rec_id), body.value, clock)


@router.delete("/{rec_id}/feedback")
async def delete_feedback(
    rec_id: uuid.UUID, user: CurrentUserDep, session: SessionDep, clock: ClockDep
) -> RecommendationOut:
    """Clear the feedback; clearing none is fine."""
    return await _set_feedback(session, await _own(session, user.id, rec_id), None, clock)
