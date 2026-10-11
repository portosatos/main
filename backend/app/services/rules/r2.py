"""R2 «Мало шагов» (SPEC F9): 3 complete days in a row, each under 50 % of the steps goal in
effect on that day; closes on a complete day with the steps goal met."""

from datetime import date

from app.services.rules.base import Facts, Rule, Verdict

PARAMS = {"days": 3, "goal_share": 0.5}


def anchor(facts: Facts) -> date:
    raise NotImplementedError("step 8.1")


def evaluate(facts: Facts, at: date) -> Verdict:
    raise NotImplementedError("step 8.1")


RULE = Rule("R2", window_days=PARAMS["days"], anchor=anchor, evaluate=evaluate)
