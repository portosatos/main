"""Sending e-mail (SPEC F10): SMTP to Mailpit through aiosmtplib; tests pass a fake `Mailer`."""

import asyncio
from email.message import EmailMessage
from typing import Protocol

import aiosmtplib

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
        """Send `message`; TimeoutError when the whole exchange takes over `timeout_s`."""
        async with asyncio.timeout(self.timeout_s):
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                timeout=self.timeout_s,
                use_tls=False,
                start_tls=False,
            )
