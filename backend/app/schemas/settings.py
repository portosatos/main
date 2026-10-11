"""Schemas of /api/settings (SPEC F10, F11, §6.3; ADR-051)."""

import re
from datetime import time
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, field_validator

# Quiet hours are local times to the minute: "07:15", never "7:15" or "07:15:30".
HHMM = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


def parse_hhmm(value: object) -> time:
    if not isinstance(value, str) or not HHMM.fullmatch(value):
        raise ValueError("time must be HH:MM")
    return time.fromisoformat(value)


def empty_to_none(value: object) -> object:
    return None if value == "" else value


def format_hhmm(value: time) -> str:
    return value.strftime("%H:%M")


LocalTime = Annotated[time, BeforeValidator(parse_hhmm)]


class SettingsOut(BaseModel):
    # null: no digests are sent (SPEC F10).
    notify_email: str | None
    quiet_enabled: bool
    quiet_start: str
    quiet_end: str
    # The zone in effect now; changed through /api/settings/timezones.
    timezone: str


class SettingsPatch(BaseModel):
    """The fields to change; the ones left out stay as they are. Start equal to end means
    no quiet hours (ADR-017)."""

    model_config = ConfigDict(extra="forbid")

    notify_email: Annotated[EmailStr | None, BeforeValidator(empty_to_none)] = None
    quiet_enabled: bool | None = None
    quiet_start: LocalTime | None = None
    quiet_end: LocalTime | None = None

    @field_validator("quiet_enabled", "quiet_start", "quiet_end", mode="before")
    @classmethod
    def not_null(cls, value: object) -> object:
        # Runs only for the fields sent: a null is not a value of these.
        if value is None:
            raise ValueError("must not be null")
        return value

    def changes(self) -> dict[str, object]:
        """The fields sent, in the order of the model."""
        return {
            name: getattr(self, name)
            for name in type(self).model_fields
            if name in self.model_fields_set
        }
