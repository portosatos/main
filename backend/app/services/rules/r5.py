"""R5 «Нерегулярный отбой» (SPEC F9): the standard deviation of the bedtimes of the last 7 nights
is over 90 min; closes under 60 min. At least 5 of the 7 nights must be valid. Bedtimes are local
wall-clock times on the circle of the day: 23:30 and 00:30 are 60 min apart, not 23 h."""

from collections.abc import Sequence
from datetime import date

from app.services.rules.base import Facts, Rule, Verdict

PARAMS = {"nights": 7, "min_nights": 5, "stdev_minutes": 90, "close_minutes": 60}


def circular_diff(a: float, b: float) -> float:
    """The shortest distance between two times of day, in minutes after midnight."""
    raise NotImplementedError("step 8.2")


def circular_stdev(minutes: Sequence[float]) -> float:
    """The standard deviation of times of day (minutes after midnight) on the circle of the day."""
    raise NotImplementedError("step 8.2")


def anchor(facts: Facts) -> date:
    raise NotImplementedError("step 8.2")


def evaluate(facts: Facts, at: date) -> Verdict:
    raise NotImplementedError("step 8.2")


# Anchor today or yesterday, the 7 nights end with it.
RULE = Rule("R5", window_days=1 + PARAMS["nights"] - 1, anchor=anchor, evaluate=evaluate)
