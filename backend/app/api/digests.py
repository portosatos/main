"""Digest routes (SPEC F10, §6.3; ADR-050): the planned and the sent digests of the session user,
the time and the reason of the plan, and a warning when there is no address for digests.

The plan is the dispatcher's: it is stored every tick (30 s), so a new recommendation shows up in
the planned digest within a tick.
"""

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import SessionDep
from app.auth.deps import CurrentUserDep
from app.models import EmailDigest, EmailOutbox
from app.schemas.digests import DEFAULT_LIMIT, MAX_LIMIT, DigestOut, DigestsOut

router = APIRouter(prefix="/api/digests", tags=["digests"])


@router.get("")
async def list_digests(
    user: CurrentUserDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> DigestsOut:
    """The planned digest (if any) and the newest sent ones."""
    pending = (
        await session.scalar(
            select(func.count()).where(
                EmailOutbox.user_id == user.id, EmailOutbox.status == "pending"
            )
        )
        or 0
    )
    in_letter = (
        select(func.count())
        .where(EmailOutbox.digest_id == EmailDigest.id)
        .correlate(EmailDigest)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(EmailDigest, in_letter)
        .where(EmailDigest.user_id == user.id)
        .order_by(EmailDigest.sent_at.desc().nulls_first(), EmailDigest.planned_at.desc())
        .limit(limit)
    )
    items = [
        DigestOut(
            id=digest.id,
            status="planned" if digest.sent_at is None else "sent",
            local_date=digest.local_date,
            planned_at=digest.planned_at,
            plan_reason=digest.plan_reason,  # type: ignore[arg-type]
            sent_at=digest.sent_at,
            to_email=digest.to_email,
            subject=digest.subject,
            recommendations=pending if digest.sent_at is None else count,
            error=digest.error,
        )
        for digest, count in rows
    ]
    return DigestsOut(
        notify_email=user.notify_email,
        warning=None if user.notify_email else "no_notify_email",
        pending=pending,
        items=items,
    )
