"""Stream mode: htgen --stream --url http://localhost:8000 --batch-size 1000 --rate 5

Logs in with an e-mail and a password (POST /api/auth/login, the session cookie) and posts the
records in batches to POST /api/ingest/batch (docs/DATA_FORMAT.md): every batch carries the
devices of the meta line. Only the standard library: the generator has no HTTP dependency.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from http.cookies import SimpleCookie
from itertools import batched
from typing import TextIO

# The API takes at most this many records in one batch (SPEC F3).
MAX_BATCH = 5000
DEFAULT_URL = "http://localhost:8000"
DEFAULT_BATCH = 1000
# The demo user of .env.example, when neither the options nor the env name one.
DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo12345"
SESSION_COOKIE = "ht_session"
# Every mutating request of the API needs it (CSRF protection, ADR-026).
CSRF_HEADERS = {"X-Requested-With": "ht"}
TIMEOUT_S = 60


class StreamError(Exception):
    """The API refused or could not be reached; the message says why, in Russian."""


@dataclass(frozen=True)
class Target:
    url: str
    email: str
    password: str
    batch_size: int
    rate: float | None  # batches per second; None — no pause


def _post(url: str, body: bytes, cookie: str | None = None) -> tuple[dict, str | None]:
    """POST JSON; the answer and its Set-Cookie header."""
    headers = {"Content-Type": "application/json", **CSRF_HEADERS}
    if cookie:
        headers["Cookie"] = cookie
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            answer = json.loads(response.read() or b"{}")
            return answer, response.headers.get("Set-Cookie")
    except urllib.error.HTTPError as error:
        raise StreamError(f"HTTP {error.code}: {_detail(error)}") from None
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        raise StreamError(f"нет связи с {url}: {reason}") from None


def _detail(error: urllib.error.HTTPError) -> str:
    try:
        detail = json.loads(error.read()).get("detail")
    except (ValueError, AttributeError):
        detail = None
    return str(detail or error.reason)


def login(target: Target) -> str:
    """The session cookie of the user, as a Cookie header value."""
    body = json.dumps({"email": target.email, "password": target.password}).encode()
    try:
        _, set_cookie = _post(f"{target.url}/api/auth/login", body)
    except StreamError as error:
        raise StreamError(f"вход {target.email}: {error}") from None
    morsel = SimpleCookie(set_cookie or "").get(SESSION_COOKIE)
    if morsel is None:
        raise StreamError(f"вход {target.email}: API не вернул cookie {SESSION_COOKIE}")
    return f"{SESSION_COOKIE}={morsel.value}"


def send(lines: Iterator[str], target: Target, log: TextIO | None = None) -> int:
    """Log in and post the records of `lines` (meta line first) in batches, reporting each to
    `log` (stderr); the number of records sent."""
    log = log or sys.stderr
    cookie = login(target)
    meta = json.loads(next(lines))
    devices = json.dumps(meta.get("devices", []), ensure_ascii=False)
    sent = 0
    started = time.monotonic()
    for number, batch in enumerate(batched(lines, target.batch_size), start=1):
        if target.rate and number > 1:
            # Batch k leaves (k - 1) / rate seconds after the first one.
            time.sleep(max(0.0, started + (number - 1) / target.rate - time.monotonic()))
        # The lines are JSON already: the body is put together without parsing them again.
        body = f'{{"devices":{devices},"records":[{",".join(batch)}]}}'.encode()
        try:
            answer, _ = _post(f"{target.url}/api/ingest/batch", body, cookie)
        except StreamError as error:
            raise StreamError(f"пачка {number}: {error}") from None
        sent += len(batch)
        print(
            f"пачка {number}: {len(batch)} записей → задача {answer.get('job_id')}",
            file=log,
            flush=True,
        )
    print(f"отправлено {sent} записей", file=log, flush=True)
    return sent
