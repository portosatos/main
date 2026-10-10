from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.clock import Clock
from app.config import AppEnv

pytestmark = pytest.mark.xfail(strict=True, reason="step 1.1: not implemented")

FIXED = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def offset_reader(seconds: int) -> tuple[list[int], Callable[[], Awaitable[int]]]:
    """Fake dev_clock reader: returns `seconds` and records each call."""
    calls: list[int] = []

    async def read() -> int:
        calls.append(seconds)
        return seconds

    return calls, read


async def test_now_is_utc_aware() -> None:
    clock = Clock(app_env="prod")

    now = await clock.now()

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)
    # Real system time, not a constant: within a minute of the test's own reading.
    assert abs(now - datetime.now(UTC)) < timedelta(minutes=1)


async def test_now_is_utc_even_if_system_now_is_not() -> None:
    plus_five = timezone(timedelta(hours=5))
    clock = Clock(app_env="prod", system_now=lambda: FIXED.astimezone(plus_five))

    now = await clock.now()

    assert now == FIXED
    assert now.tzinfo is UTC


async def test_offset_applied_in_dev() -> None:
    _, read = offset_reader(3600)
    clock = Clock(app_env="dev", read_offset=read, system_now=lambda: FIXED)

    reading = await clock.read()

    assert reading.system_now == FIXED
    assert reading.offset_seconds == 3600
    assert reading.now == FIXED + timedelta(hours=1)
    assert await clock.now() == FIXED + timedelta(hours=1)


@pytest.mark.parametrize("app_env", ["prod", "test"])
async def test_offset_ignored_in_prod(app_env: AppEnv) -> None:
    calls, read = offset_reader(3600)
    clock = Clock(app_env=app_env, read_offset=read, system_now=lambda: FIXED)

    reading = await clock.read()

    assert reading.now == FIXED
    assert reading.offset_seconds == 0
    assert calls == [], "outside dev the offset must not even be read"


async def test_offset_is_cached_until_invalidated() -> None:
    calls, read = offset_reader(60)
    clock = Clock(app_env="dev", read_offset=read, cache_ttl_s=60, system_now=lambda: FIXED)

    await clock.now()
    await clock.now()
    assert len(calls) == 1, "a second call within the TTL uses the cached offset"

    clock.invalidate()
    await clock.now()
    assert len(calls) == 2
