"""R4 «Сон хуже, чем на прошлой неделе» (SPEC F9): the mean sleep of the last complete ISO week
is at least 60 min under the week before; closes when the difference is under 30 min. Each week
needs at least 5 valid nights; the means are over the valid nights (SPEC F7)."""

from datetime import date, timedelta
from statistics import fmean

from app.services.rules.base import Facts, Rule, Verdict

PARAMS = {"min_nights": 5, "drop_minutes": 60, "close_minutes": 30}


def anchor(facts: Facts) -> date:
    """The Sunday of the last complete ISO week: on a Sunday the current week is not over yet."""
    return facts.today - timedelta(days=facts.today.isoweekday())


def week(facts: Facts, sunday: date) -> tuple[float, dict[str, object]] | None:
    """The mean sleep of the valid nights of the ISO week ending `sunday` and its snapshot; None
    with fewer than 5 valid nights."""
    nights = (facts.day(sunday - timedelta(days=i)) for i in range(7))
    sleep = [n.sleep_minutes for n in nights if n.night_valid and n.sleep_minutes is not None]
    if len(sleep) < PARAMS["min_nights"]:
        return None
    year, number, _ = sunday.isocalendar()
    mean = fmean(sleep)
    snapshot = {"week": f"{year}-W{number:02d}", "avg_sleep_minutes": round(mean, 1)}
    return mean, {**snapshot, "nights": len(sleep)}


def evaluate(facts: Facts, at: date) -> Verdict:
    """`at` is the Sunday of the last complete week; it is compared with the week before."""
    last, before = week(facts, at), week(facts, at - timedelta(days=7))
    if last is None or before is None:
        return Verdict("unknown")
    drop = before[0] - last[0]
    context = {
        "weeks": [before[1], last[1]],
        "drop_minutes": round(drop, 1),
        "threshold_minutes": PARAMS["drop_minutes"],
    }
    if drop < PARAMS["close_minutes"]:
        return Verdict("close", context)
    if drop >= PARAMS["drop_minutes"]:
        return Verdict("fire", context)
    return Verdict("hold", context)


# The anchor (a Sunday) is at most 7 days before today, the two weeks end with it.
RULE = Rule("R4", window_days=7 + 14 - 1, anchor=anchor, evaluate=evaluate)
