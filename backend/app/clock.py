"""The only source of "now" for the backend (CLAUDE.md, section 5; SPEC F0).

Clock returns the system time in UTC. In APP_ENV=dev it adds the offset stored in dev_clock
(set via POST /api/dev/clock), so the api and the worker move in time together. Outside dev the
offset is never read. The offset is cached for `cache_ttl_s` (ADR-025): the process that changes
it calls invalidate(), other processes see the change within the TTL.
"""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import AppEnv, Settings
from app.models import DevClock

OffsetReader = Callable[[], Awaitable[int]]


def system_now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ClockReading:
    system_now: datetime
    offset_seconds: int
    now: datetime


class Clock:
    def __init__(
        self,
        *,
        app_env: AppEnv,
        read_offset: OffsetReader | None = None,
        cache_ttl_s: float = 1.0,
        system_now: Callable[[], datetime] = system_now_utc,
    ) -> None:
        self.app_env = app_env
        self._read_offset = read_offset
        self._cache_ttl_s = cache_ttl_s
        self._system_now = system_now
        self._cached_offset: int | None = None
        self._cached_at = 0.0

    @property
    def offset_enabled(self) -> bool:
        return self.app_env == "dev" and self._read_offset is not None

    async def read(self) -> ClockReading:
        """System time, the offset in effect and their sum, all from one system time reading."""
        system_now = self._system_now().astimezone(UTC)
        offset = await self._offset()
        return ClockReading(system_now, offset, system_now + timedelta(seconds=offset))

    async def now(self) -> datetime:
        return (await self.read()).now

    def invalidate(self) -> None:
        """Forget the cached offset: the next read goes to the database."""
        self._cached_offset = None

    async def _offset(self) -> int:
        if not self.offset_enabled:
            return 0
        fresh = time.monotonic() - self._cached_at < self._cache_ttl_s
        if self._cached_offset is None or not fresh:
            self._cached_offset = await self._read_offset()
            self._cached_at = time.monotonic()
        return self._cached_offset


async def read_dev_offset(session: AsyncSession) -> int:
    """The stored offset in seconds; 0 when it was never set."""
    offset = await session.scalar(select(DevClock.offset_seconds).where(DevClock.id == 1))
    return offset or 0


async def write_dev_offset(session: AsyncSession, offset_seconds: int) -> None:
    """Upsert the single dev_clock row. The caller commits."""
    stmt = insert(DevClock).values(id=1, offset_seconds=offset_seconds)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[DevClock.id], set_={"offset_seconds": stmt.excluded.offset_seconds}
        )
    )


def create_clock(settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]) -> Clock:
    """The clock of a process (api or worker): dev offset from the database it is connected to."""

    async def read_offset() -> int:
        async with sessionmaker() as session:
            return await read_dev_offset(session)

    return Clock(
        app_env=settings.app_env, read_offset=read_offset, cache_ttl_s=settings.clock_cache_ttl_s
    )
