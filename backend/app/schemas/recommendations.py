"""Schemas of /api/recommendations (SPEC F9, §6.3; ADR-048)."""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RuleCode = Literal["R1", "R2", "R3", "R4", "R5", "R6"]
Status = Literal["open", "resolved", "closed_rule_disabled"]
FeedbackValue = Literal["useful", "not_useful"]

# Recommendations GET returns by default and at most, newest first.
DEFAULT_LIMIT = 200
MAX_LIMIT = 500


class RecommendationOut(BaseModel):
    id: uuid.UUID
    rule_code: str = Field(examples=["R1"])
    title: str = Field(examples=["Недосып"])
    status: Status
    opened_at: datetime
    # The local date the rule fired on.
    anchor_date: date
    # The values the rule fired on.
    context: dict[str, Any]
    resolved_at: datetime | None
    # 'auto' (the rule's close condition) or 'rule_disabled'.
    resolve_reason: str | None
    feedback: FeedbackValue | None
    # When the current feedback was given (Clock); null without feedback.
    feedback_at: datetime | None


class FeedbackIn(BaseModel):
    value: FeedbackValue
