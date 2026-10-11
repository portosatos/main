"""Sending e-mail (SPEC F10): SMTP to Mailpit through aiosmtplib; tests pass a fake `Mailer`."""

from email.message import EmailMessage
from typing import Protocol

# The whole send is cut off after this many seconds: a hanging server must not hold the
# dispatcher's transaction and lock (ADR-050).
SMTP_TIMEOUT_S = 10.0


class Mailer(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class SmtpMailer:
    """SMTP without TLS or login: Mailpit (compose service `mailpit`, port 1025)."""

    def __init__(self, host: str, port: int, *, timeout_s: float = SMTP_TIMEOUT_S) -> None:
        self.host = host
        self.port = port
        self.timeout_s = timeout_s

    async def send(self, message: EmailMessage) -> None:
        raise NotImplementedError("step 9.2")
