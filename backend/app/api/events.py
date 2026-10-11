"""SSE route (SPEC F12, §6.3): GET /api/events, the event stream of the session's user.

Step 5.1 interface stub: the stream comes with the feature commit.
"""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/events")
async def events() -> None:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="Не реализовано")
