"""The digest dispatcher (SPEC F10): the worker's tick plans the digest of every user with pending
outbox entries (planner.plan_send) and sends one letter with all of them when it is due.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.notify.mailer import Mailer
from app.services.notify.planner import DIGEST_MAX_DELAY, DIGEST_WINDOW


@dataclass(frozen=True)
class DigestConfig:
    window: timedelta = DIGEST_WINDOW
    max_delay: timedelta = DIGEST_MAX_DELAY
    # The link in the letter.
    app_url: str = "http://localhost:5173"
    sender: str = "Трекер здоровья <noreply@health-tracker.local>"


DEFAULT_CONFIG = DigestConfig()


async def dispatch(
    sessionmaker: async_sessionmaker[AsyncSession],
    now: datetime,
    mailer: Mailer,
    config: DigestConfig = DEFAULT_CONFIG,
) -> int:
    """Plan the digests of the users with pending entries and send the due ones; the number sent."""
    raise NotImplementedError("step 9.2")
