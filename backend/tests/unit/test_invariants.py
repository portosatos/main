"""Code invariants from CLAUDE.md, section 5."""

import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"
CLOCK_FILE = APP_DIR / "clock.py"

# Direct reads of the system time. app.clock.Clock is the only place allowed to make them.
FORBIDDEN_NOW = re.compile(r"\b(?:datetime\.(?:now|utcnow)|date\.today|time\.time)\(")


def test_forbidden_pattern_matches_known_calls() -> None:
    for call in ("datetime.now(UTC)", "datetime.utcnow()", "date.today()", "time.time()"):
        assert FORBIDDEN_NOW.search(call), call
    for allowed in ("time.monotonic()", "clock.now()", "datetime.fromisoformat(s)"):
        assert not FORBIDDEN_NOW.search(allowed), allowed


def test_no_direct_now_calls_outside_clock() -> None:
    offenders = [
        f"{path.relative_to(APP_DIR.parent)}:{lineno}: {line.strip()}"
        for path in sorted(APP_DIR.rglob("*.py"))
        if path != CLOCK_FILE
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if FORBIDDEN_NOW.search(line)
    ]
    assert offenders == [], "read time through app.clock.Clock:\n" + "\n".join(offenders)
    # The exception must be real: Clock itself is where the system time is read.
    assert FORBIDDEN_NOW.search(CLOCK_FILE.read_text(encoding="utf-8")), (
        "app/clock.py must read the system time (datetime.now(UTC))"
    )
