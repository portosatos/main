"""Seed data applied on every api start (SPEC §4): the demo user. Idempotent."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock


async def seed_demo_user(
    session: AsyncSession, clock: Clock, *, email: str, password: str, timezone: str
) -> None:
    raise NotImplementedError("step 1.2")
