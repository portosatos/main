"""Dev-only routes (/api/dev/*). The router is included only when APP_ENV=dev (SPEC §4)."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import ClockDep, SessionDep
from app.clock import ClockReading, write_dev_offset

router = APIRouter(prefix="/api/dev", tags=["dev"])

# ADR-025: up to 10 years either way; well inside the int column.
MAX_OFFSET_SECONDS = 10 * 366 * 24 * 3600


class DevClockState(BaseModel):
    offset_seconds: int
    system_now: datetime
    now: datetime

    @classmethod
    def of(cls, reading: ClockReading) -> "DevClockState":
        return cls(
            offset_seconds=reading.offset_seconds,
            system_now=reading.system_now,
            now=reading.now,
        )


class DevClockUpdate(BaseModel):
    offset_seconds: int = Field(ge=-MAX_OFFSET_SECONDS, le=MAX_OFFSET_SECONDS, strict=True)


@router.get("/clock")
async def get_dev_clock(clock: ClockDep) -> DevClockState:
    return DevClockState.of(await clock.read())


@router.post("/clock")
async def set_dev_clock(
    body: DevClockUpdate, session: SessionDep, clock: ClockDep
) -> DevClockState:
    await write_dev_offset(session, body.offset_seconds)
    await session.commit()
    clock.invalidate()
    return DevClockState.of(await clock.read())
