"""R1 «Недосып» (SPEC F9): 3 valid nights in a row, each under 6 h of sleep; closes on a valid
night of at least 7 h. A night is the sleep of its wake day; its validity does not depend on the
day's status (SPEC F6)."""

from datetime import date

from app.services.rules.base import Facts, Rule, Verdict

PARAMS = {"nights": 3, "short_hours": 6, "close_hours": 7}


def anchor(facts: Facts) -> date:
    raise NotImplementedError("step 8.1")


def evaluate(facts: Facts, at: date) -> Verdict:
    raise NotImplementedError("step 8.1")


RULE = Rule("R1", window_days=PARAMS["nights"], anchor=anchor, evaluate=evaluate)
