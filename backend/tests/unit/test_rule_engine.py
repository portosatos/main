"""The state machine of a (user, rule) pair (SPEC F9): services/rules/engine.py::plan_actions.

A fake rule returns the verdict the test sets, so the machine is checked apart from R1–R6.
"""

from datetime import date, timedelta

import pytest

from app.services.rules.base import Facts, Rule, Verdict, VerdictKind
from app.services.rules.engine import Action, plan_actions

TODAY = date(2026, 10, 10)
NOT_IMPLEMENTED = "step 8.1: not implemented"


class FakeRule:
    """A rule whose verdict the test sets; it counts its calls."""

    def __init__(self, kind: VerdictKind, code: str = "RX") -> None:
        self.kind = kind
        self.calls = 0
        self.rule = Rule(code, window_days=1, anchor=self._anchor, evaluate=self._evaluate)

    def _anchor(self, facts: Facts) -> date:
        self.calls += 1
        return facts.today

    def _evaluate(self, facts: Facts, at: date) -> Verdict:
        self.calls += 1
        return Verdict(self.kind, {"at": at.isoformat()})


def run(fake: FakeRule, *, open_codes: set[str], today: date = TODAY) -> list[Action]:
    return plan_actions(
        [fake.rule], Facts([], today), enabled={fake.rule.code}, open_codes=open_codes
    )


@pytest.mark.xfail(strict=True, reason=NOT_IMPLEMENTED)
def test_opens_when_condition_true() -> None:
    actions = run(FakeRule("fire"), open_codes=set())

    assert actions == [Action("RX", "open", TODAY, {"at": "2026-10-10"})]


@pytest.mark.xfail(strict=True, reason=NOT_IMPLEMENTED)
def test_no_duplicate_while_still_true_next_day() -> None:
    fake = FakeRule("fire")
    assert [a.kind for a in run(fake, open_codes=set())] == ["open"]

    # The next day the condition still holds and the recommendation is open: nothing new.
    assert run(fake, open_codes={"RX"}, today=TODAY + timedelta(days=1)) == []
    # Another rule's open recommendation does not block this one.
    assert [a.kind for a in run(fake, open_codes={"RY"})] == ["open"]


@pytest.mark.xfail(strict=True, reason=NOT_IMPLEMENTED)
def test_resolves_on_close_condition() -> None:
    fake = FakeRule("close")

    assert run(fake, open_codes={"RX"}) == [Action("RX", "resolve", TODAY, {"at": "2026-10-10"})]
    # Nothing to resolve: nothing happens.
    assert run(fake, open_codes=set()) == []


@pytest.mark.xfail(strict=True, reason=NOT_IMPLEMENTED)
@pytest.mark.parametrize("kind", ["unknown", "hold"])
def test_unknown_leaves_state_unchanged(kind: VerdictKind) -> None:
    fake = FakeRule(kind)

    assert run(fake, open_codes={"RX"}) == []
    assert run(fake, open_codes=set()) == []
    assert fake.calls > 0


@pytest.mark.xfail(strict=True, reason=NOT_IMPLEMENTED)
def test_disabled_rule_not_evaluated() -> None:
    off = FakeRule("fire", code="RX")
    on = FakeRule("fire", code="RY")

    actions = plan_actions([off.rule, on.rule], Facts([], TODAY), enabled={"RY"}, open_codes=set())

    assert [a.code for a in actions] == ["RY"]
    assert off.calls == 0
    # A disabled rule with an open recommendation is not closed by the engine either (that is
    # the toggle's job, step 8.3).
    off_open = plan_actions(
        [FakeRule("close").rule], Facts([], TODAY), enabled=(), open_codes={"RX"}
    )
    assert off_open == []
