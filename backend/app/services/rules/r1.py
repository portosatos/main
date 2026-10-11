"""R1 «Недосып» (SPEC F9): 3 valid nights in a row, each under 6 h of sleep; closes on a valid
night of at least 7 h. A night is the sleep of its wake day; its validity does not depend on the
day's status (SPEC F6)."""

from datetime import date, timedelta

from app.services.rules.base import Day, Facts, Rule, Verdict

PARAMS = {"nights": 3, "short_hours": 6, "close_hours": 7}


def anchor(facts: Facts) -> date:
    """Today if last night is valid, else yesterday (SPEC F9)."""
    today = facts.today
    return today if is_known(facts.day(today)) else today - timedelta(days=1)


def is_known(day: Day) -> bool:
    return day.night_valid and day.sleep_minutes is not None


def slept(day: Day) -> int:
    return day.sleep_minutes or 0


def snapshot(day: Day) -> dict[str, object]:
    return {"date": day.local_date.isoformat(), "sleep_minutes": day.sleep_minutes}


def evaluate(facts: Facts, at: date) -> Verdict:
    """The nights of the window end with the night of `at`; closing looks at that night only."""
    last = facts.day(at)
    if is_known(last) and slept(last) >= PARAMS["close_hours"] * 60:
        return Verdict("close", {"night": snapshot(last)})
    window = [facts.day(at - timedelta(days=i)) for i in reversed(range(PARAMS["nights"]))]
    if not all(is_known(night) for night in window):
        return Verdict("unknown")
    context = {
        "nights": [snapshot(night) for night in window],
        "short_hours": PARAMS["short_hours"],
    }
    if all(slept(night) < PARAMS["short_hours"] * 60 for night in window):
        return Verdict("fire", context)
    return Verdict("hold", context)


RULE = Rule("R1", window_days=PARAMS["nights"], anchor=anchor, evaluate=evaluate)
