"""R3 «Повышенный пульс в покое» (SPEC F9): 2 days in a row with the resting pulse at least 7 bpm
over the baseline — the mean of the 14 days before the two, at least 7 values; closes when the
resting pulse is under the baseline + 4 (hysteresis)."""

from datetime import date, timedelta
from statistics import fmean

from app.services.rules.base import Day, Facts, Rule, Verdict, yesterday

PARAMS = {"days": 2, "baseline_days": 14, "baseline_min_values": 7, "rise_bpm": 7, "close_bpm": 4}


def baseline(facts: Facts, at: date) -> dict[str, float] | None:
    """The mean resting pulse of the 14 dates before the two days ending with `at` and the number
    of values it is taken over; None with fewer than 7 values."""
    first = at - timedelta(days=PARAMS["days"] + PARAMS["baseline_days"] - 1)
    days = (facts.day(first + timedelta(days=i)) for i in range(PARAMS["baseline_days"]))
    values = [d.resting_hr for d in days if d.resting_hr is not None]
    if len(values) < PARAMS["baseline_min_values"]:
        return None
    return {"baseline": fmean(values), "baseline_values": len(values)}


def snapshot(day: Day) -> dict[str, object]:
    return {"date": day.local_date.isoformat(), "resting_hr": day.resting_hr}


def evaluate(facts: Facts, at: date) -> Verdict:
    """The two days end with `at`; closing looks at `at` only, against the same baseline (the
    rise of 7 bpm opens, under 4 bpm closes: the gap between them keeps the state steady)."""
    base = baseline(facts, at)
    last = facts.day(at)
    if base is None or last.resting_hr is None:
        return Verdict("unknown")
    level = base["baseline"]
    shown = {"baseline": round(level, 1), "baseline_values": base["baseline_values"]}
    if last.resting_hr < level + PARAMS["close_bpm"]:
        return Verdict("close", {"day": snapshot(last), **shown})
    window = [facts.day(at - timedelta(days=i)) for i in reversed(range(PARAMS["days"]))]
    if any(day.resting_hr is None for day in window):
        return Verdict("unknown")
    context = {"days": [snapshot(day) for day in window], **shown, "rise_bpm": PARAMS["rise_bpm"]}
    if all((day.resting_hr or 0) >= level + PARAMS["rise_bpm"] for day in window):
        return Verdict("fire", context)
    return Verdict("hold", context)


# Anchor yesterday, the two days and the 14 before them.
RULE = Rule(
    "R3",
    window_days=1 + PARAMS["days"] + PARAMS["baseline_days"] - 1,
    anchor=yesterday,
    evaluate=evaluate,
)
