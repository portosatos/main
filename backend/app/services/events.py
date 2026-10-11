"""Events for the open tabs of a user (SPEC F12): publish through Postgres NOTIFY on the channel
`user_events`, every api process LISTENs and hands them to the SSE streams of that user.

`publish` sends in the caller's transaction, so a tab hears of a change only once it is
committed and a refetch sees it. The payload is `{"user_id", "type", "data"}`, under the 8000
bytes NOTIFY allows: ids and dates, never the data itself.

`EventHub` is the api side: one LISTEN connection per process (application_name `ht-events`)
and the subscriptions of its SSE streams. When the connection drops, the hub reconnects with
backoff; the events of the gap are lost, so every stream then gets `resync` and its tab refetches
everything, as after a reconnect of EventSource (ADR-039).
"""

import asyncio
import json
import uuid
from collections import defaultdict
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from types import TracebackType
from typing import Any

import asyncpg
import structlog
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)

CHANNEL = "user_events"
# Postgres refuses a NOTIFY payload of 8000 bytes or more.
MAX_PAYLOAD_BYTES = 7900
# application_name of the api's LISTEN connection (seen in pg_stat_activity).
LISTENER_APP_NAME = "ht-events"
# Reconnect backoff of the listener, in seconds.
RETRY_MIN_S = 0.2
RETRY_MAX_S = 5.0
# A quiet listener checks its connection this often, in seconds.
CHECK_S = 5.0
# Events a slow stream may lag behind; beyond that it gets `resync` instead.
QUEUE_SIZE = 1000
# Bytes one ISO date adds to a JSON list: quotes and a comma.
DATE_BYTES = len('"2026-10-11",')


@dataclass(frozen=True)
class Event:
    type: str
    data: dict[str, Any]


# Sent to a stream that may have missed events: its tab refetches everything.
RESYNC = Event("resync", {})


def encode(user_id: uuid.UUID, type: str, data: dict[str, Any]) -> str:
    payload = json.dumps(
        {"user_id": str(user_id), "type": type, "data": data},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if len(payload.encode()) > MAX_PAYLOAD_BYTES:
        raise ValueError(f"event {type} is over {MAX_PAYLOAD_BYTES} bytes")
    return payload


async def publish(
    session: AsyncSession, user_id: uuid.UUID, type: str, data: dict[str, Any]
) -> None:
    """Send the event to the user's tabs when the session's transaction commits."""
    await session.execute(select(func.pg_notify(CHANNEL, encode(user_id, type, data))))


async def publish_summary_updated(
    session: AsyncSession, user_id: uuid.UUID, dates: Iterable[date]
) -> None:
    """`summary.updated {dates}`, split into several events if one payload would be too big.
    The dates go sorted; the events of one transaction arrive in order."""
    ordered = [d.isoformat() for d in sorted(set(dates))]
    room = MAX_PAYLOAD_BYTES - len(encode(user_id, "summary.updated", {"dates": []}).encode())
    size = (room + 1) // DATE_BYTES  # the last date has no comma
    for start in range(0, len(ordered), size):
        await publish(session, user_id, "summary.updated", {"dates": ordered[start : start + size]})


class Subscription:
    """The events of one user for one SSE stream; leave the `with` block to unsubscribe."""

    def __init__(self, hub: "EventHub", user_id: uuid.UUID) -> None:
        self.hub = hub
        self.user_id = user_id
        self.queue: asyncio.Queue[Event] = asyncio.Queue(QUEUE_SIZE)

    def put(self, event: Event) -> None:
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            # The stream is too slow: drop what it has not read and let the tab refetch.
            while not self.queue.empty():
                self.queue.get_nowait()
            self.queue.put_nowait(RESYNC)

    async def get(self) -> Event:
        return await self.queue.get()

    def __enter__(self) -> "Subscription":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.hub.unsubscribe(self)


class EventHub:
    """LISTEN on `user_events` in this process and fan the events out to subscriptions."""

    def __init__(self, database_url: str, *, check_s: float = CHECK_S) -> None:
        url = make_url(database_url)
        self._connect_args = {
            "user": url.username,
            "password": url.password,
            "host": url.host,
            "port": url.port,
            "database": url.database,
        }
        self.check_s = check_s
        self._subscriptions: defaultdict[uuid.UUID, set[Subscription]] = defaultdict(set)
        self._listening = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start listening in the background; a database that is down does not stop the api."""
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def wait_listening(self, seconds: float) -> bool:
        """True once the hub listens; False if it does not within `seconds`."""
        try:
            async with asyncio.timeout(seconds):
                await self._listening.wait()
        except TimeoutError:
            return False
        return True

    def subscribe(self, user_id: uuid.UUID) -> Subscription:
        subscription = Subscription(self, user_id)
        self._subscriptions[user_id].add(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        streams = self._subscriptions.get(subscription.user_id)
        if streams is not None:
            streams.discard(subscription)
            if not streams:
                del self._subscriptions[subscription.user_id]

    def _dispatch(self, user_id: uuid.UUID, event: Event) -> None:
        for subscription in list(self._subscriptions.get(user_id, ())):
            subscription.put(event)

    def _on_notify(self, conn: object, pid: int, channel: str, payload: str) -> None:
        try:
            message = json.loads(payload)
            user_id = uuid.UUID(message["user_id"])
            event = Event(message["type"], message["data"])
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("event_dropped", error=repr(exc), payload=payload[:200])
            return
        self._dispatch(user_id, event)

    async def _run(self) -> None:
        delay = RETRY_MIN_S
        connected_before = False
        while True:
            try:
                conn = await asyncpg.connect(
                    **self._connect_args,
                    timeout=self.check_s,
                    server_settings={"application_name": LISTENER_APP_NAME},
                )
            except Exception as exc:  # the database is down or unreachable: try again later
                log.warning("events_connect_failed", error=repr(exc), retry_s=delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, RETRY_MAX_S)
                continue
            try:
                await self._listen(conn, reconnect=connected_before)
            except Exception as exc:  # a dead connection fails the check: reconnect
                log.warning("events_connection_failed", error=repr(exc))
            finally:
                self._listening.clear()
                conn.terminate()
            delay = RETRY_MIN_S
            connected_before = True

    async def _listen(self, conn: asyncpg.Connection, *, reconnect: bool) -> None:
        """LISTEN on `conn` until it is lost; after a reconnect every stream gets `resync`."""
        lost = asyncio.Event()
        conn.add_termination_listener(lambda _: lost.set())
        await conn.add_listener(CHANNEL, self._on_notify)
        self._listening.set()
        log.info("events_listening", reconnect=reconnect)
        if reconnect:
            for streams in list(self._subscriptions.values()):
                for subscription in list(streams):
                    subscription.put(RESYNC)
        while not lost.is_set():
            with suppress(TimeoutError):
                async with asyncio.timeout(self.check_s):
                    await lost.wait()
            if not lost.is_set():
                await conn.fetchval("SELECT 1", timeout=self.check_s)
        log.warning("events_connection_lost")
