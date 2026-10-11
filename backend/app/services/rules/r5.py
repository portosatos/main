"""R5 «Нерегулярный отбой» (SPEC F9): the standard deviation of the bedtimes of the last 7 nights
is over 90 min; closes under 60 min. At least 5 of the 7 nights must be valid. Bedtimes are local
wall-clock times on the circle of the day: 23:30 and 00:30 are 60 min apart, not 23 h."""

import math
from collections.abc import Sequence
from datetime import date, timedelta
from statistics import fmean

from app.services.rules.base import Day, Facts, Rule, Verdict, has_night, last_night

PARAMS = {"nights": 7, "min_nights": 5, "stdev_minutes": 90, "close_minutes": 60}
DAY = 24 * 60


def signed_diff(a: float, b: float) -> float:
    """`a` − `b` on the circle of the day: the shortest way, from −720 to 720 minutes."""
    return (a - b + DAY / 2) % DAY - DAY / 2


def circular_diff(a: float, b: float) -> float:
    """The shortest distance between two times of day, in minutes after midnight."""
    return abs(signed_diff(a, b))


def circular_mean(minutes: Sequence[float]) -> float:
    """The mean direction of times of day on the circle (minutes after midnight)."""
    angles = [2 * math.pi * m / DAY for m in minutes]
    mean = math.atan2(fmean(map(math.sin, angles)), fmean(map(math.cos, angles)))
    return (mean / (2 * math.pi) * DAY) % DAY


def circular_stdev(minutes: Sequence[float]) -> float:
    """The standard deviation of times of day (minutes after midnight) on the circle of the day:
    the population stdev of the shortest differences from the circular mean, so 23:30 and 00:30
    spread like 12:00 and 13:00 (ADR-047)."""
    center = circular_mean(minutes)
    return math.sqrt(fmean(signed_diff(m, center) ** 2 for m in minutes))


def bedtime(facts: Facts, night: Day) -> float:
    """The local wall-clock start of the night's main session, minutes after midnight."""
    assert night.sleep_start is not None
    local = facts.local_time(night.sleep_start)
    return local.hour * 60 + local.minute + local.second / 60


def evaluate(facts: Facts, at: date) -> Verdict:
    """The 7 nights end with the night of `at`; only valid ones count, at least 5."""
    window = [facts.day(at - timedelta(days=i)) for i in reversed(range(PARAMS["nights"]))]
    nights = [night for night in window if has_night(night)]
    if len(nights) < PARAMS["min_nights"]:
        return Verdict("unknown")
    beds = [bedtime(facts, night) for night in nights]
    stdev = circular_stdev(beds)
    context = {
        "nights": [
            {"date": n.local_date.isoformat(), "bedtime": f"{int(b) // 60:02d}:{int(b) % 60:02d}"}
            for n, b in zip(nights, beds, strict=True)
        ],
        "stdev_minutes": round(stdev, 1),
        "threshold_minutes": PARAMS["stdev_minutes"],
    }
    if stdev < PARAMS["close_minutes"]:
        return Verdict("close", context)
    if stdev > PARAMS["stdev_minutes"]:
        return Verdict("fire", context)
    return Verdict("hold", context)


# Anchor today or yesterday, the 7 nights end with it.
RULE = Rule("R5", window_days=1 + PARAMS["nights"] - 1, anchor=last_night, evaluate=evaluate)
