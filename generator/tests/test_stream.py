"""Stream mode (SPEC F13; plan step 11.1): htgen --stream logs in and posts the records in batches
to POST /api/ingest/batch.

The API here is a small test server on the standard library: it checks what the real one checks
(the CSRF header, the session cookie, the batch limit) and keeps what it received. The real API
takes these batches in backend/tests/integration/test_ingest_batch.py.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from conftest import run_htgen

from htgen.cli import main

COOKIE = "ht_session"
TOKEN = "test-session-token"
ARGS = ["--start", "2026-10-01", "--days", "2", "--seed", "3", "--hr-interval", "60"]


@dataclass
class FakeApi:
    """What the test server received and how it answers."""

    password: str = "secret-password"
    logins: list[dict[str, Any]] = field(default_factory=list)
    batches: list[dict[str, Any]] = field(default_factory=list)
    order: list[str] = field(default_factory=list)
    url: str = ""


def handler_for(api: FakeApi) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: Any) -> None:  # keep the test output clean
            pass

        def reply(self, status: int, body: dict[str, Any], cookie: str | None = None) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.headers.get("X-Requested-With") != "ht":
                return self.reply(403, {"detail": "Нужен заголовок X-Requested-With: ht"})
            if self.path == "/api/auth/login":
                api.order.append("login")
                api.logins.append(body)
                if body.get("password") != api.password:
                    return self.reply(401, {"detail": "Неверная почта или пароль"})
                return self.reply(200, {"id": "u"}, f"{COOKIE}={TOKEN}; Path=/; HttpOnly")
            if self.path == "/api/ingest/batch":
                api.order.append("batch")
                if f"{COOKIE}={TOKEN}" not in self.headers.get("Cookie", ""):
                    return self.reply(401, {"detail": "Нужен вход"})
                if len(body["records"]) > 5000:
                    return self.reply(413, {"detail": "Не больше 5000 записей"})
                api.batches.append(body)
                return self.reply(202, {"job_id": f"job-{len(api.batches)}"})
            return self.reply(404, {"detail": "Not Found"})

    return Handler


@pytest.fixture
def api() -> Iterator[FakeApi]:
    state = FakeApi()
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(state))
    state.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.xfail(strict=True, reason="step 11.1: not implemented")
def test_stream_mode_posts_batches_and_logs_in(api: FakeApi, tmp_path: Path) -> None:
    expected = run_htgen(tmp_path / "file.ndjson", *ARGS)

    code = main(
        [
            *ARGS,
            "--stream",
            "--url",
            api.url,
            "--batch-size",
            "1000",
            "--rate",
            "100",
            "--email",
            "stream@example.com",
            "--password",
            api.password,
        ]
    )

    assert code == 0
    # One login, before the batches.
    assert api.logins == [{"email": "stream@example.com", "password": api.password}]
    assert api.order[0] == "login" and api.order.count("login") == 1
    # The records of the file, in order, in full batches of 1000 and a shorter last one.
    sizes = [len(batch["records"]) for batch in api.batches]
    assert sizes[:-1] == [1000] * (len(sizes) - 1) and 0 < sizes[-1] <= 1000
    streamed = [record for batch in api.batches for record in batch["records"]]
    assert streamed == expected.records
    # Every batch names its devices, like the meta line of a file.
    assert all(batch["devices"] == expected.meta["devices"] for batch in api.batches)


@pytest.mark.xfail(strict=True, reason="step 11.1: not implemented")
def test_stream_credentials_default_to_demo_env(
    api: FakeApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Beyond the plan: without --email and --password the demo user from the env logs in."""
    monkeypatch.setenv("DEMO_USER_EMAIL", "demo-env@example.com")
    monkeypatch.setenv("DEMO_USER_PASSWORD", api.password)

    assert main([*ARGS, "--days", "1", "--stream", "--url", api.url, "--rate", "100"]) == 0
    assert api.logins == [{"email": "demo-env@example.com", "password": api.password}]
    assert api.batches


@pytest.mark.xfail(strict=True, reason="step 11.1: not implemented")
def test_stream_login_rejected_exit_1(api: FakeApi, capsys: pytest.CaptureFixture[str]) -> None:
    """Beyond the plan: a wrong password stops before any batch, with the API's reason."""
    code = main(
        [*ARGS, "--stream", "--url", api.url, "--email", "x@example.com", "--password", "wrong"]
    )

    assert code == 1
    assert api.batches == []
    assert "Неверная почта или пароль" in capsys.readouterr().err
