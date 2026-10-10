"""The only source of "now" for the backend (CLAUDE.md, section 5).

Step 1.1 stub: the interface is fixed, the behavior is not implemented yet.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import AppEnv, Settings

OffsetReader = Callable[[], Awaitable[int]]


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
        system_now: Callable[[], datetime] | None = None,
    ) -> None:
        self.app_env = app_env

    async def read(self) -> ClockReading:
        raise NotImplementedError("step 1.1")

    async def now(self) -> datetime:
        raise NotImplementedError("step 1.1")

    def invalidate(self) -> None:
        raise NotImplementedError("step 1.1")


def create_clock(settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]) -> Clock:
    raise NotImplementedError("step 1.1")
