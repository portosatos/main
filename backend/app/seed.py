"""Seed data applied on every api start (SPEC §4): the demo user. Idempotent.

Run: python -m app.seed (the api container does it after migrations). The demo user comes from
DEMO_USER_EMAIL / DEMO_USER_PASSWORD / DEMO_USER_TIMEZONE; an empty password skips the seed.
"""

import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.accounts import (
    EmailTakenError,
    create_user,
    find_user_by_email,
    hash_password_async,
    is_valid_timezone,
    verify_password_async,
)
from app.clock import Clock, create_clock
from app.config import Settings
from app.db import create_engine, create_sessionmaker
from app.logging import configure_logging

log = structlog.get_logger(__name__)


async def seed_demo_user(
    session: AsyncSession, clock: Clock, *, email: str, password: str, timezone: str
) -> None:
    """Create the demo user if missing. If it exists, only its password follows the environment
    (ADR-026): the id, the data and the time zone history stay as they are."""
    if not is_valid_timezone(timezone):
        raise ValueError(f"DEMO_USER_TIMEZONE is not an IANA time zone: {timezone!r}")
    user = await find_user_by_email(session, email)
    if user is None:
        try:
            await create_user(
                session, email=email, password=password, timezone=timezone, now=await clock.now()
            )
        except EmailTakenError:
            return  # created concurrently by another process
        log.info("demo_user_created", email=email)
        return
    if not await verify_password_async(user.password_hash, password):
        user.password_hash = await hash_password_async(password)
        await session.commit()
        log.info("demo_user_password_updated", email=email)


async def run(settings: Settings) -> None:
    if not settings.demo_user_password:
        log.info("demo_user_seed_skipped", reason="DEMO_USER_PASSWORD is empty")
        return
    engine = create_engine(settings)
    try:
        sessionmaker = create_sessionmaker(engine)
        async with sessionmaker() as session:
            await seed_demo_user(
                session,
                create_clock(settings, sessionmaker),
                email=settings.demo_user_email,
                password=settings.demo_user_password,
                timezone=settings.demo_user_timezone,
            )
    finally:
        await engine.dispose()


def main() -> None:
    configure_logging()
    asyncio.run(run(Settings()))


if __name__ == "__main__":
    main()
