"""Process checker for the step workflow (docs/plan.md, CLAUDE.md sections 2-4).

Usage:
    python scripts/check_process.py --step X.Y   # one step: worklog + its commits
    python scripts/check_process.py --all        # whole history; last step may be unfinished

Checks:
- every "## " heading of docs/WORKLOG.md starts with an ISO timestamp with offset
  (WORKLOG_NO_OFFSET, WORKLOG_BAD_HEADING), timestamps never decrease (WORKLOG_NOT_MONOTONIC);
- WORKLOG.md was only appended to: each committed version and the working copy start with the
  previous version (WORKLOG_NOT_APPEND_ONLY);
- the step has "Шаг X.Y начат" and "Шаг X.Y завершён" entries (STEP_NO_START, STEP_NO_END);
- every commit has a "Stage: X.Y" line (COMMIT_NO_STAGE); commits of the step use Conventional
  Commits (COMMIT_NOT_CONVENTIONAL); the step has commits (STEP_NO_COMMITS) and a test(...) commit
  before its first feat(...) commit (STEP_TEST_NOT_BEFORE_FEAT).

Exit code: 0 if everything is fine, 1 if there are violations, 2 on usage errors. Stdlib only.
"""

from __future__ import annotations

import argparse
import itertools
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

WORKLOG = "docs/WORKLOG.md"

TIMESTAMP_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)(?P<offset>Z|[+-]\d{2}:\d{2})?$"
)
HEADING_RE = re.compile(r"^## (?P<ts>\S+)(?:\s+[—–-]\s+(?P<title>.*))?$")
STEP_START_RE = re.compile(r"^Шаг (?P<step>\d+\.\d+) начат\b")
STEP_END_RE = re.compile(r"^Шаг (?P<step>\d+\.\d+) завершён\b")
STAGE_RE = re.compile(r"^Stage: (?P<step>\d+\.\d+)\s*$", re.MULTILINE)
CONVENTIONAL_RE = re.compile(
    r"^(?P<type>feat|fix|docs|test|chore|build|ci|refactor|perf|style|revert)"
    r"(?:\([a-z0-9._/-]+\))?!?: \S.*$"
)
STEP_ARG_RE = re.compile(r"^\d+\.\d+$")


@dataclass
class Entry:
    line: int
    ts: datetime
    title: str


@dataclass
class Commit:
    sha: str
    subject: str
    body: str

    @property
    def short(self) -> str:
        return self.sha[:7]

    @property
    def stage(self) -> str | None:
        match = STAGE_RE.search(self.body)
        return match.group("step") if match else None

    @property
    def type(self) -> str | None:
        match = CONVENTIONAL_RE.match(self.subject)
        return match.group("type") if match else None


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, code: str, message: str) -> None:
        self.errors.append(f"ERROR {code}: {message}")


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.quotepath=off", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n")


def parse_timestamp(raw: str) -> tuple[datetime | None, bool]:
    """Return (timestamp, has_offset); timestamp is None if raw is not an ISO timestamp at all."""
    match = TIMESTAMP_RE.match(raw)
    if not match:
        return None, False
    offset = match.group("offset")
    if offset is None:
        return None, True
    date = match.group("date")
    if "." in date:  # fromisoformat before 3.11 accepts at most 6 fraction digits
        head, fraction = date.split(".")
        date = f"{head}.{fraction[:6].ljust(6, '0')}"
    return datetime.fromisoformat(date + ("+00:00" if offset == "Z" else offset)), True


def parse_worklog(text: str, report: Report) -> list[Entry]:
    entries: list[Entry] = []
    for number, line in enumerate(normalize(text).split("\n"), start=1):
        if not line.startswith("## "):
            continue
        heading = HEADING_RE.match(line)
        raw = heading.group("ts") if heading else ""
        ts, looks_like_time = parse_timestamp(raw)
        if ts is None:
            if looks_like_time:
                report.error(
                    "WORKLOG_NO_OFFSET", f"{WORKLOG}:{number}: timestamp without offset: {raw}"
                )
            else:
                report.error(
                    "WORKLOG_BAD_HEADING",
                    f"{WORKLOG}:{number}: heading must start with a timestamp",
                )
            continue
        if entries and ts < entries[-1].ts:
            report.error(
                "WORKLOG_NOT_MONOTONIC",
                f"{WORKLOG}:{number}: {raw} is earlier than the previous entry"
                f" (line {entries[-1].line})",
            )
        entries.append(Entry(number, ts, (heading.group("title") or "").strip()))
    return entries


def check_append_only(repo: Path, report: Report) -> None:
    shas = git(repo, "log", "--reverse", "--format=%H", "--", WORKLOG).split()
    versions = []
    for sha in shas:
        try:
            versions.append((sha[:7], normalize(git(repo, "show", f"{sha}:{WORKLOG}"))))
        except RuntimeError:
            versions.append((sha[:7], ""))  # file deleted in this commit
    path = repo / WORKLOG
    if path.exists():
        versions.append(("working tree", normalize(path.read_text(encoding="utf-8"))))
    for (_, previous), (label, current) in itertools.pairwise(versions):
        if not current.startswith(previous):
            report.error(
                "WORKLOG_NOT_APPEND_ONLY", f"{WORKLOG} in {label} changes or removes earlier lines"
            )


def read_commits(repo: Path) -> list[Commit]:
    try:
        git(repo, "rev-parse", "--verify", "-q", "HEAD")
    except RuntimeError:
        return []
    raw = git(repo, "log", "--reverse", "--no-merges", "--format=%H%x1f%s%x1f%B%x1e")
    commits = []
    for record in raw.split("\x1e"):
        record = record.strip("\n")
        if record:
            sha, subject, body = record.split("\x1f", 2)
            commits.append(Commit(sha, subject, body))
    return commits


def check_commits(commits: list[Commit], report: Report) -> None:
    for commit in commits:
        if commit.stage is None:
            report.error(
                "COMMIT_NO_STAGE", f"{commit.short} '{commit.subject}' has no 'Stage: X.Y' line"
            )


def check_step(
    step: str, entries: list[Entry], commits: list[Commit], report: Report, *, finished: bool
) -> None:
    starts = [e for e in entries if (m := STEP_START_RE.match(e.title)) and m.group("step") == step]
    ends = [e for e in entries if (m := STEP_END_RE.match(e.title)) and m.group("step") == step]
    if not starts:
        report.error("STEP_NO_START", f"{WORKLOG} has no '## <time> — Шаг {step} начат: …' entry")
    if finished:
        if not ends:
            report.error("STEP_NO_END", f"{WORKLOG} has no '## <time> — Шаг {step} завершён' entry")
        elif starts and ends[-1].line < starts[0].line:
            report.error(
                "STEP_NO_END",
                f"'Шаг {step} завершён' (line {ends[-1].line}) precedes its start entry",
            )

    own = [c for c in commits if c.stage == step]
    if not own:
        report.error("STEP_NO_COMMITS", f"no commits with 'Stage: {step}'")
        return
    for commit in own:
        if commit.type is None:
            report.error(
                "COMMIT_NOT_CONVENTIONAL",
                f"{commit.short} '{commit.subject}' is not a Conventional Commit",
            )

    types = [c.type for c in own]
    if "feat" in types:
        first_feat = types.index("feat")
        if "test" not in types[:first_feat]:
            report.error(
                "STEP_TEST_NOT_BEFORE_FEAT",
                f"step {step}: no test(...) commit before the first feat(...) commit"
                f" {own[first_feat].short}",
            )
    elif finished and "test" not in types:
        report.error("STEP_TEST_NOT_BEFORE_FEAT", f"step {step}: no test(...) commit")


def steps_in_order(entries: list[Entry], commits: list[Commit]) -> list[str]:
    seen: dict[str, None] = {}
    for entry in entries:
        if match := STEP_START_RE.match(entry.title):
            seen.setdefault(match.group("step"))
    for commit in commits:
        if commit.stage:
            seen.setdefault(commit.stage)
    return list(seen)


def run(repo: Path, step: str | None) -> Report:
    report = Report()
    path = repo / WORKLOG
    if not path.exists():
        report.error("WORKLOG_MISSING", f"{WORKLOG} not found in {repo}")
        return report
    entries = parse_worklog(path.read_text(encoding="utf-8"), report)
    check_append_only(repo, report)
    commits = read_commits(repo)
    check_commits(commits, report)
    if step is not None:
        check_step(step, entries, commits, report, finished=True)
    else:
        steps = steps_in_order(entries, commits)
        for index, current in enumerate(steps):
            check_step(current, entries, commits, report, finished=index < len(steps) - 1)
    return report


def main(argv: list[str] | None = None) -> int:
    if hasattr(
        sys.stdout, "reconfigure"
    ):  # Cyrillic messages through pipes on Windows (cp1251 by default)
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Check WORKLOG entries and commits of a plan step."
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--step", help="step number from docs/plan.md, e.g. 0.1")
    target.add_argument(
        "--all", action="store_true", help="check every step; the last one may be unfinished"
    )
    parser.add_argument(
        "--repo", default=".", help="path inside the git repository (default: current dir)"
    )
    args = parser.parse_args(argv)

    if args.step is not None and not STEP_ARG_RE.match(args.step):
        parser.error(f"--step must look like X.Y, got {args.step!r}")
    try:
        repo = Path(git(Path(args.repo), "rev-parse", "--show-toplevel").strip())
        report = run(repo, args.step)
    except RuntimeError as exc:
        print(f"ERROR GIT: {exc}", file=sys.stderr)
        return 2

    for line in report.errors:
        print(line)
    scope = f"step {args.step}" if args.step else "all steps"
    if report.errors:
        print(f"check_process: {scope}: {len(report.errors)} problem(s)")
        return 1
    print(f"check_process: {scope}: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
