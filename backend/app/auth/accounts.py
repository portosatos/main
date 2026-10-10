"""Account creation and password checks, shared by the auth API and the demo seed."""

import asyncio
import functools
import zoneinfo
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password, verify_password
from app.models import User, UserTimezone


class EmailTakenError(Exception):
    pass


@functools.cache
def _known_timezones() -> frozenset[str]:
    return frozenset(zoneinfo.available_timezones())


def is_valid_timezone(tz: str) -> bool:
    """An IANA zone name from the tz database (tzdata), e.g. "Europe/Moscow"."""
    return tz in _known_timezones()


async def hash_password_async(password: str) -> str:
    # argon2 takes tens of milliseconds of CPU: keep it off the event loop.
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password_hash: str, password: str) -> bool:
    return await asyncio.to_thread(verify_password, password_hash, password)


@functools.cache
def _dummy_hash() -> str:
    return hash_password("dummy password for timing")


async def find_user_by_email(db: AsyncSession, email: str) -> User | None:
    # The column is citext, so the comparison ignores letter case.
    return await db.scalar(select(User).where(User.email == email))


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    """The user if the email and password match. An unknown email costs the same argon2 check,
    so response time does not reveal which emails are registered."""
    user = await find_user_by_email(db, email)
    if user is None:
        await verify_password_async(_dummy_hash(), password)
        return None
    if not await verify_password_async(user.password_hash, password):
        return None
    return user


async def create_user(
    db: AsyncSession, *, email: str, password: str, timezone: str, now: datetime
) -> User:
    """Insert the user and the first record of their time zone history, valid from `now`
    (SPEC F5). Commits. Raises EmailTakenError if the email is taken in any letter case."""
    user = User(
        email=email,
        password_hash=await hash_password_async(password),
        notify_email=email,
        created_at=now,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise EmailTakenError(email) from exc
    db.add(UserTimezone(user_id=user.id, tz=timezone, valid_from=now, created_at=now))
    await db.commit()
    return user
