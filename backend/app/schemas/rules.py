"""Schemas of /api/rules (SPEC F9, §6.3; ADR-048)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RuleOut(BaseModel):
    code: str = Field(examples=["R1"])
    title: str
    description: str
    # The thresholds of the rule (rules.params); users do not edit them.
    params: dict[str, Any]
    enabled: bool
    # When the user last switched the rule (Clock); null if never.
    changed_at: datetime | None


class RuleSwitch(BaseModel):
    """Turn the rule on or off: off closes its open recommendation, on evaluates it at once."""

    enabled: bool
