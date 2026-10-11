"""Goal routes (SPEC F8, §6.3): the current goals and changing them.

PUT adds a version for every kind whose target changed, in effect from now (Clock) on: the past
days keep their goals (ADR-043). The user's tabs hear of it with `goal.changed`. A goal lowered
to today's value or below is met at once: today's achievements are recorded as after a recompute.
"""

from fastapi import APIRouter

from app.api.deps import ClockDep, SessionDep
from app.auth.deps import CurrentUserDep
from app.models import Goal
from app.schemas.goals import GoalOut, GoalsIn
from app.services import events
from app.services.goals import KINDS, GoalBook, load_goal_book, record_achievements
from app.services.localtime import load_tz_history

router = APIRouter(prefix="/api/goals", tags=["goals"])


def _out(book: GoalBook) -> list[GoalOut]:
    return [GoalOut(**vars(book.current(kind))) for kind in KINDS]


@router.get("")
async def get_goals(user: CurrentUserDep, session: SessionDep) -> list[GoalOut]:
    """The goals in effect now: steps, then sleep."""
    return _out(await load_goal_book(session, user.id))


@router.put("")
async def put_goals(
    body: GoalsIn, user: CurrentUserDep, session: SessionDep, clock: ClockDep
) -> list[GoalOut]:
    """New targets; the same ones again change nothing."""
    now = await clock.now()
    book = await load_goal_book(session, user.id)
    targets = {"steps": body.steps, "sleep": round(body.sleep, 2)}
    changed = [kind for kind in KINDS if targets[kind] != book.current(kind).target]
    if changed:
        session.add_all(
            Goal(user_id=user.id, kind=kind, target=targets[kind], valid_from=now, created_at=now)
            for kind in changed
        )
        await session.flush()
        await events.publish(session, user.id, "goal.changed", {"kinds": changed})
        history = await load_tz_history(session, user.id)
        await record_achievements(session, user.id, [history.local_date(now)], now, history)
        await session.commit()
        book = await load_goal_book(session, user.id)
    return _out(book)
