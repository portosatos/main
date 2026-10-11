"""R6 «Нет активности» (SPEC F9): 5 complete days in a row, each under 15 active minutes; closes on
a complete day with at least 15 active minutes."""

from datetime import date, timedelta

from app.services.rules.base import Day, Facts, Rule, Verdict, yesterday

PARAMS = {"days": 5, "active_minutes": 15}


def is_known(day: Day) -> bool:
    return day.status == "complete" and day.active_minutes is not None


def active(day: Day) -> int:
    return day.active_minutes or 0


def snapshot(day: Day) -> dict[str, object]:
    return {"date": day.local_date.isoformat(), "active_minutes": day.active_minutes}


def evaluate(facts: Facts, at: date) -> Verdict:
    """The days of the window end with `at`; closing looks at that day only."""
    last = facts.day(at)
    if is_known(last) and active(last) >= PARAMS["active_minutes"]:
        return Verdict("close", {"day": snapshot(last)})
    window = [facts.day(at - timedelta(days=i)) for i in reversed(range(PARAMS["days"]))]
    if not all(is_known(day) for day in window):
        return Verdict("unknown")
    context = {
        "days": [snapshot(day) for day in window],
        "active_minutes": PARAMS["active_minutes"],
    }
    if all(active(day) < PARAMS["active_minutes"] for day in window):
        return Verdict("fire", context)
    return Verdict("hold", context)


# Anchor yesterday, the 5 days end with it.
RULE = Rule("R6", window_days=PARAMS["days"], anchor=yesterday, evaluate=evaluate)
