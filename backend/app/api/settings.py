"""Settings routes (SPEC F10, F11, §6.3; ADR-051): the address for digests and quiet hours.

PATCH changes only the fields sent; a field set to the value it has changes nothing. The user's
tabs hear of a change with `settings.changed {fields}` when it commits. The digest dispatcher
reads the address and the quiet hours on its next tick (ADR-050).
"""

from datetime import datetime

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ClockDep, SessionDep
from app.auth.deps import CurrentUserDep
from app.models import User
from app.schemas.settings import SettingsOut, SettingsPatch, format_hhmm
from app.services import events
from app.services.localtime import load_tz_history

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
