"""GET /api/health: liveness, database check and the worker's last tick (SPEC §4, ADR-021).

The worker does not affect the status code: the api container's healthcheck uses this route and
the worker starts only after the api is healthy (compose).
"""

import asyncio

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.db import check_db
from app.worker.heartbeat import last_beat

router = APIRouter()


async def worker_state(request: Request) -> dict[str, str | None]:
    """{"status": "ok" | "stale" | "unknown", "last_tick_at": ISO time or None}."""
    settings = request.app.state.settings
    async with asyncio.timeout(settings.db_health_timeout_s):
        async with request.app.state.sessionmaker() as session:
            beat_at = await last_beat(session)
        now = await request.app.state.clock.now()
    if beat_at is None:
        return {"status": "unknown", "last_tick_at": None}
    fresh = (now - beat_at).total_seconds() <= settings.worker_stale_after_s
    return {"status": "ok" if fresh else "stale", "last_tick_at": beat_at.isoformat()}


@router.get("/api/health")
async def health(request: Request) -> JSONResponse:
    settings = request.app.state.settings
    if await check_db(request.app.state.engine, settings.db_health_timeout_s):
        try:
            worker = await worker_state(request)
        except Exception:  # e.g. migrations not applied yet: the api itself is still alive
            worker = {"status": "unknown", "last_tick_at": None}
        return JSONResponse({"status": "ok", "db": "ok", "worker": worker})
    return JSONResponse(
        {"status": "unavailable", "db": "unreachable"},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
