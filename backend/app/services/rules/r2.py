"""R2 «Мало шагов» (SPEC F9): 3 complete days in a row, each under 50 % of the steps goal in
effect on that day; closes on a complete day with the steps goal met."""

from datetime import date, timedelta

from app.services.rules.base import Day, Facts, Rule, Verdict

PARAMS = {"days": 3, "goal_share": 0.5}


def anchor(facts: Facts) -> date:
    """Yesterday: today is not over yet (SPEC F9)."""
    return facts.today - timedelta(days=1)


def is_known(day: Day) -> bool:
    return day.status == "complete" and day.steps is not None


def walked(day: Day) -> int:
    return day.steps or 0


def snapshot(facts: Facts, day: Day) -> dict[str, object]:
    goal = facts.goal("steps", day.local_date)
    return {"date": day.local_date.isoformat(), "steps": day.steps, "goal": goal}


def evaluate(facts: Facts, at: date) -> Verdict:
    """The days of the window end with `at`; closing looks at that day only. Every day is
    compared with its own goal (SPEC F8)."""
    last = facts.day(at)
    if is_known(last) and walked(last) >= facts.goal("steps", at):
        return Verdict("close", {"day": snapshot(facts, last)})
    window = [facts.day(at - timedelta(days=i)) for i in reversed(range(PARAMS["days"]))]
    if not all(is_known(day) for day in window):
        return Verdict("unknown")
    share = PARAMS["goal_share"]
    context = {"days": [snapshot(facts, day) for day in window], "goal_share": share}
    if all(walked(day) < share * facts.goal("steps", day.local_date) for day in window):
        return Verdict("fire", context)
    return Verdict("hold", context)


RULE = Rule("R2", window_days=PARAMS["days"], anchor=anchor, evaluate=evaluate)
