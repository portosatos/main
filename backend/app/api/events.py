"""SSE route (SPEC F12, §6.3): GET /api/events, the event stream of the session's user.

The stream starts with `ready` (subscribed: nothing published from now on is missed), then
carries the user's events as `event: <type>` and `data: <JSON>`, with a keep-alive comment every
`sse_ping_s` seconds. Formats and the list of events: docs/API.md, ADR-039.
"""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, status
from sse_starlette import EventSourceResponse, ServerSentEvent

from app.auth.deps import current_user
from app.services.events import EventHub

router = APIRouter(prefix="/api", tags=["events"])

# How long a new stream waits for the api to LISTEN (start-up, a reconnect) before 503.
LISTEN_WAIT_S = 5.0


@router.get("/events", response_class=EventSourceResponse)
async def events(request: Request) -> EventSourceResponse:
    """SSE stream of the user's events; 401 without a session."""
    state = request.app.state
    # A session of its own, closed before the stream: an open tab must not hold a connection.
    async with state.sessionmaker() as db:
        user_id = (await current_user(request, db, state.clock)).id
    hub: EventHub = state.events
    if not await hub.wait_listening(LISTEN_WAIT_S):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="События недоступны")

    async def stream() -> AsyncIterator[ServerSentEvent]:
        with hub.subscribe(user_id) as subscription:
            yield ServerSentEvent(event="ready", data="{}")
            while True:
                event = await subscription.get()
                yield ServerSentEvent(
                    event=event.type, data=json.dumps(event.data, ensure_ascii=False)
                )

    return EventSourceResponse(stream(), ping=state.settings.sse_ping_s)
