"""Sending e-mail (SPEC F10): SMTP to Mailpit through aiosmtplib; tests pass a fake `Mailer`."""

from email.message import EmailMessage
from typing import Protocol


class Mailer(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class SmtpMailer:
    """SMTP without TLS or login: Mailpit (compose service `mailpit`, port 1025)."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    async def send(self, message: EmailMessage) -> None:
        raise NotImplementedError("step 9.2")
