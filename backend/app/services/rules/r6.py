"""R6 «Нет активности» (SPEC F9): 5 complete days in a row, each under 15 active minutes; closes on
a complete day with at least 15 active minutes."""

from datetime import date

from app.services.rules.base import Facts, Rule, Verdict, yesterday

PARAMS = {"days": 5, "active_minutes": 15}


def evaluate(facts: Facts, at: date) -> Verdict:
    raise NotImplementedError("step 8.2")


# Anchor yesterday, the 5 days end with it.
RULE = Rule("R6", window_days=PARAMS["days"], anchor=yesterday, evaluate=evaluate)
