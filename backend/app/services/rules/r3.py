"""R3 «Повышенный пульс в покое» (SPEC F9): 2 days in a row with the resting pulse at least 7 bpm
over the baseline — the mean of the 14 days before the two, at least 7 values; closes when the
resting pulse is under the baseline + 4 (hysteresis)."""

from datetime import date

from app.services.rules.base import Facts, Rule, Verdict, yesterday

PARAMS = {"days": 2, "baseline_days": 14, "baseline_min_values": 7, "rise_bpm": 7, "close_bpm": 4}


def evaluate(facts: Facts, at: date) -> Verdict:
    raise NotImplementedError("step 8.2")


# Anchor yesterday, the two days and the 14 before them.
RULE = Rule(
    "R3",
    window_days=1 + PARAMS["days"] + PARAMS["baseline_days"] - 1,
    anchor=yesterday,
    evaluate=evaluate,
)
