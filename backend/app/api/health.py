"""GET /api/health: liveness plus database check (worker tick is added in step 3.2, ADR-021)."""

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.db import check_db

router = APIRouter()


@router.get("/api/health")
async def health(request: Request) -> JSONResponse:
    settings = request.app.state.settings
    if await check_db(request.app.state.engine, settings.db_health_timeout_s):
        return JSONResponse({"status": "ok", "db": "ok"})
    return JSONResponse(
        {"status": "unavailable", "db": "unreachable"},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
