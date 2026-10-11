"""R4 «Сон хуже, чем на прошлой неделе» (SPEC F9): the mean sleep of the last complete ISO week
is at least 60 min under the week before; closes when the difference is under 30 min. Each week
needs at least 5 valid nights; the means are over the valid nights (SPEC F7)."""

from datetime import date, timedelta

from app.services.rules.base import Facts, Rule, Verdict

PARAMS = {"min_nights": 5, "drop_minutes": 60, "close_minutes": 30}


def anchor(facts: Facts) -> date:
    """The Sunday of the last complete ISO week: on a Sunday the current week is not over yet."""
    return facts.today - timedelta(days=facts.today.isoweekday())


def evaluate(facts: Facts, at: date) -> Verdict:
    raise NotImplementedError("step 8.2")


# The anchor (a Sunday) is at most 7 days before today, the two weeks end with it.
RULE = Rule("R4", window_days=7 + 14 - 1, anchor=anchor, evaluate=evaluate)
