"""Schemas of /api/goals (SPEC F8, §6.3; ADR-043)."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

# The ranges a goal may take (ADR-043).
STEPS_MIN, STEPS_MAX = 100, 100_000
SLEEP_MIN, SLEEP_MAX = 1, 16


class GoalOut(BaseModel):
    kind: Literal["steps", "sleep"]
    # Steps a day, or hours of sleep.
    target: int | float
    # When this target was set; null for the default.
    valid_from: datetime | None


class GoalsIn(BaseModel):
    """Both targets; a changed one becomes a new version from now on."""

    steps: Annotated[int, Field(ge=STEPS_MIN, le=STEPS_MAX, description="Steps a day")]
    sleep: Annotated[float, Field(ge=SLEEP_MIN, le=SLEEP_MAX, description="Hours of sleep")]
