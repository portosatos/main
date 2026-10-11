"""Settings routes (SPEC F10, F11, §6.3; ADR-051): the address for digests, quiet hours and the
time zone history.

PATCH changes only the fields sent; a field set to the value it has changes nothing. A move adds an
entry to the history and queues the job `tz_changed`, which recomputes the dates it changed and
evaluates the rules (services/timezones.py). The user's tabs hear of a change with
`settings.changed {fields}` when it commits. The digest dispatcher reads the address, the quiet
hours and the zone on its next tick (ADR-050).
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ClockDep, SessionDep
from app.auth.deps import CurrentUserDep
from app.models import User, UserTimezone
from app.schemas.settings import (
    SettingsOut,
    SettingsPatch,
    TimezoneIn,
    TimezoneOut,
    TimezonesOut,
    format_hhmm,
)
from app.services import events
from app.services.localtime import TzHistory, load_tz_history
from app.services.timezones import HISTORY_START, TZ_CHANGED, entries, job_payload
from app.worker.queue import enqueue

router = APIRouter(prefix="/api/settings", tags=["settings"])

SETTINGS_CHANGED = "settings.changed"


async def settings_out(session: AsyncSession, user: User, now: datetime) -> SettingsOut:
    history = await load_tz_history(session, user.id)
    return SettingsOut(
        notify_email=user.notify_email,
        quiet_enabled=user.quiet_enabled,
        quiet_start=format_hhmm(user.quiet_start),
        quiet_end=format_hhmm(user.quiet_end),
        timezone=history.zone_at(now).key,
    )


@router.get("")
async def get_settings(user: CurrentUserDep, session: SessionDep, clock: ClockDep) -> SettingsOut:
    return await settings_out(session, user, await clock.now())


@router.patch("")
async def patch_settings(
    body: SettingsPatch, user: CurrentUserDep, session: SessionDep, clock: ClockDep
) -> SettingsOut:
    """Change the fields sent; the answer is all the settings."""
    changed = [name for name, value in body.changes().items() if getattr(user, name) != value]
    if changed:
        for name in changed:
            setattr(user, name, getattr(body, name))
        await events.publish(session, user.id, SETTINGS_CHANGED, {"fields": changed})
        await session.commit()
    return await settings_out(session, user, await clock.now())


async def timezones_out(session: AsyncSession, user: User, now: datetime) -> TimezonesOut:
    records = (
        await session.scalars(select(UserTimezone).where(UserTimezone.user_id == user.id))
    ).all()
    items = [TimezoneOut(**vars(entry)) for entry in entries(records, now)]
    return TimezonesOut(current=next(i.tz for i in items if i.current), items=items)


@router.get("/timezones")
async def list_timezones(
    user: CurrentUserDep, session: SessionDep, clock: ClockDep
) -> TimezonesOut:
    """The time zone history, newest first, the entry in effect now marked."""
    return await timezones_out(session, user, await clock.now())


@router.post("/timezones", status_code=status.HTTP_201_CREATED)
async def add_timezone(
    body: TimezoneIn, user: CurrentUserDep, session: SessionDep, clock: ClockDep
) -> TimezonesOut:
    """A move to `tz` from `valid_from` (now by default) until the next entry of the history;
    the answer is the whole history."""
    now = await clock.now()
    valid_from = body.valid_from or now
    if valid_from.tzinfo is None:  # the local time of the new zone (ADR-051)
        valid_from = valid_from.replace(tzinfo=ZoneInfo(body.tz))
    valid_from = valid_from.astimezone(UTC)
    if valid_from > now:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="«Действует с» не может быть позже текущего момента",
        )
    if valid_from <= HISTORY_START:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="«Действует с» — не раньше 1970 года"
        )

    records = (
        await session.scalars(select(UserTimezone).where(UserTimezone.user_id == user.id))
    ).all()
    if any(r.valid_from == valid_from for r in records):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="С этого момента в истории уже есть пояс"
        )
    if TzHistory(records).zone_at(valid_from).key == body.tz:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Этот пояс уже действует в это время")
    valid_to = min((r.valid_from for r in records if r.valid_from > valid_from), default=None)

    first = min(records, key=lambda r: r.valid_from)
    if valid_from < first.valid_from:
        # The first entry covers the time before it: keep that time in its zone (ADR-051).
        session.add(
            UserTimezone(user_id=user.id, tz=first.tz, valid_from=HISTORY_START, created_at=now)
        )
    session.add(UserTimezone(user_id=user.id, tz=body.tz, valid_from=valid_from, created_at=now))
    try:
        await session.flush()
    except IntegrityError:  # the same moment added by a concurrent request
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="С этого момента в истории уже есть пояс"
        ) from None
    await enqueue(
        session,
        kind=TZ_CHANGED,
        user_id=user.id,
        payload=job_payload(valid_from, valid_to),
        now=now,
    )
    await events.publish(session, user.id, SETTINGS_CHANGED, {"fields": ["timezone"]})
    await session.commit()
    return await timezones_out(session, user, now)
