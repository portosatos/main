"""Schemas of /api/auth/*."""

import uuid
from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.auth.accounts import is_valid_timezone


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    # The browser's zone (Intl.DateTimeFormat().resolvedOptions().timeZone), SPEC F1.
    timezone: str = Field(examples=["Europe/Moscow"])

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        if not is_valid_timezone(value):
            raise ValueError("unknown IANA time zone")
        return value


class LoginRequest(BaseModel):
    email: str = Field(max_length=320)
    # Bounded so a huge body cannot keep argon2 busy; any real password fits.
    password: str = Field(max_length=1024)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    notify_email: str | None
    # The user's local date now: Clock (dev offset included) and the zone history (SPEC F0, F5).
    today: date
    # The zone in effect now by the history (SPEC F5).
    timezone: str
