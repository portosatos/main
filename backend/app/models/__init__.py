"""SQLAlchemy models. Base.metadata (with every model imported here) is the target of Alembic
autogenerate."""

from app.models.base import Base
from app.models.dev_clock import DevClock
from app.models.device import Device
from app.models.goal import Goal, GoalAchievement
from app.models.ingest import HrPoint, IngestJob, SleepRaw, StepsRaw
from app.models.jobs import Job, WorkerHeartbeat
from app.models.minutes import CoverageMinute, SleepMinute, StepsMinute
from app.models.notification import Notification
from app.models.session import AuthSession
from app.models.summary import DailySummary
from app.models.user import User, UserTimezone

__all__ = [
    "AuthSession",
    "Base",
    "CoverageMinute",
    "DailySummary",
    "DevClock",
    "Device",
    "Goal",
    "GoalAchievement",
    "HrPoint",
    "IngestJob",
    "Job",
    "Notification",
    "SleepMinute",
    "SleepRaw",
    "StepsMinute",
    "StepsRaw",
    "User",
    "UserTimezone",
    "WorkerHeartbeat",
]
