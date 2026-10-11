"""Schemas of /api/devices (SPEC F2, §6.3)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

MAX_NAME_LENGTH = 100


class DeviceOut(BaseModel):
    id: uuid.UUID
    external_id: str
    kind: Literal["watch", "phone"]
    name: str
    created_at: datetime
    # The start of the last minute some record of the device covers; null: no data yet.
    last_data_at: datetime | None


class DeviceRename(BaseModel):
    # Trimmed; blank or longer than 100 characters → 422.
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_NAME_LENGTH)
    ]
