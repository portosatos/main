"""Tests for scripts/check_process.py.

Each test builds a throwaway git repository, checks that a valid history passes (exit 0),
then introduces exactly one violation and expects exit 1 with a specific error code.
The script is run as a CLI, the way it is used in Done When and CI.
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "check_process.py"
WORKLOG = "docs/WORKLOG.md"
TRAILER = "\n\nStage: 0.1\n"

pytestmark = pytest.mark.xfail(strict=True, reason="step 0.1: not implemented")

HEADER = "# WORKLOG\n\nЖурнал работы.\n"
START = "\n## 2026-10-10T10:00:00+03:00 — Шаг 0.1 начат: репозиторий и журналы\n- План: ...\n"
FEATURE = "\n## 2026-10-10T11:00:00+03:00 — Фича готова: проверка процесса\n- Коммит: ...\n"
END = "\n## 2026-10-10T12:00:00+03:00 — Шаг 0.1 завершён\n- Итог: ...\n"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "core.autocrlf", "false")
    return repo


def write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def append(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    write(repo, rel, path.read_text(encoding="utf-8") + text)


def commit(repo: Path, message: str, files: dict[str, str] | None = None) -> None:
    for rel, text in (files or {}).items():
        write(repo, rel, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", message)


def run_check(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, f"expected exit 0\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def assert_error(result: subprocess.CompletedProcess[str], code: str) -> None:
    output = result.stdout + result.stderr
    assert result.returncode == 1, f"expected exit 1 with {code}\n{output}"
    assert code in output, f"expected error code {code}\n{output}"


def valid_step_repo(tmp_path: Path) -> Path:
    """A finished step 0.1: start entry, red tests, feature, end entry."""
    repo = init_repo(tmp_path)
    commit(repo, "docs: start worklog" + TRAILER, {WORKLOG: HEADER + START})
    commit(repo, "test(process): checker tests (red)" + TRAILER, {"tests/test_x.py": "x = 1\n"})
    commit(repo, "feat(process): checker" + TRAILER, {"x.py": "x = 1\n"})
    append(repo, WORKLOG, FEATURE + END)
    commit(repo, "docs(worklog): step 0.1 finished" + TRAILER)
    return repo


def test_worklog_timestamps_must_be_monotonic(tmp_path: Path) -> None:
    repo = valid_step_repo(tmp_path)
    assert_ok(run_check(repo, "--step", "0.1"))

    append(repo, WORKLOG, "\n## 2026-10-10T11:30:00+03:00 — Запись задним числом\n")
    commit(repo, "docs(worklog): late entry" + TRAILER)

    assert_error(run_check(repo, "--step", "0.1"), "WORKLOG_NOT_MONOTONIC")


def test_worklog_rejects_timestamp_without_offset(tmp_path: Path) -> None:
    repo = valid_step_repo(tmp_path)
    assert_ok(run_check(repo, "--step", "0.1"))

    append(repo, WORKLOG, "\n## 2026-10-10T13:00:00 — Время без смещения\n")
    commit(repo, "docs(worklog): entry without offset" + TRAILER)

    assert_error(run_check(repo, "--step", "0.1"), "WORKLOG_NO_OFFSET")


def test_step_requires_start_and_end_entries(tmp_path: Path) -> None:
    repo = valid_step_repo(tmp_path)
    assert_ok(run_check(repo, "--step", "0.1"))

    no_end = init_repo(tmp_path / "no_end")
    commit(no_end, "docs: start worklog" + TRAILER, {WORKLOG: HEADER + START})
    commit(no_end, "test(process): checker tests (red)" + TRAILER)
    commit(no_end, "feat(process): checker" + TRAILER)
    assert_error(run_check(no_end, "--step", "0.1"), "STEP_NO_END")

    no_start = init_repo(tmp_path / "no_start")
    commit(no_start, "docs: worklog" + TRAILER, {WORKLOG: HEADER + FEATURE + END})
    commit(no_start, "test(process): checker tests (red)" + TRAILER)
    commit(no_start, "feat(process): checker" + TRAILER)
    assert_error(run_check(no_start, "--step", "0.1"), "STEP_NO_START")


def test_worklog_append_only_detects_deleted_lines(tmp_path: Path) -> None:
    repo = valid_step_repo(tmp_path)
    assert_ok(run_check(repo, "--step", "0.1"))

    text = (repo / WORKLOG).read_text(encoding="utf-8")
    write(repo, WORKLOG, text.replace("- План: ...\n", ""))
    commit(repo, "docs(worklog): tidy up" + TRAILER)

    assert_error(run_check(repo, "--step", "0.1"), "WORKLOG_NOT_APPEND_ONLY")


def test_commit_requires_conventional_format(tmp_path: Path) -> None:
    repo = valid_step_repo(tmp_path)
    assert_ok(run_check(repo, "--step", "0.1"))

    commit(repo, "Added some stuff" + TRAILER)

    assert_error(run_check(repo, "--step", "0.1"), "COMMIT_NOT_CONVENTIONAL")


def test_commit_requires_stage_trailer(tmp_path: Path) -> None:
    repo = valid_step_repo(tmp_path)
    assert_ok(run_check(repo, "--step", "0.1"))

    commit(repo, "fix(process): typo\n\nStage: 0\n")

    assert_error(run_check(repo, "--step", "0.1"), "COMMIT_NO_STAGE")


def test_step_requires_test_commit_before_feat_commit(tmp_path: Path) -> None:
    repo = valid_step_repo(tmp_path)
    assert_ok(run_check(repo, "--step", "0.1"))

    feat_first = init_repo(tmp_path / "feat_first")
    commit(feat_first, "docs: start worklog" + TRAILER, {WORKLOG: HEADER + START})
    commit(feat_first, "feat(process): checker" + TRAILER)
    commit(feat_first, "test(process): checker tests" + TRAILER)
    append(feat_first, WORKLOG, END)
    commit(feat_first, "docs(worklog): step 0.1 finished" + TRAILER)

    assert_error(run_check(feat_first, "--step", "0.1"), "STEP_TEST_NOT_BEFORE_FEAT")


def test_all_mode_allows_unfinished_last_step_only(tmp_path: Path) -> None:
    repo = valid_step_repo(tmp_path)
    next_start = "\n## 2026-10-10T13:00:00+03:00 — Шаг 0.2 начат: скелет backend\n"
    append(repo, WORKLOG, next_start)
    commit(repo, "docs(worklog): step 0.2 started\n\nStage: 0.2\n")
    commit(repo, "test(backend): health tests (red)\n\nStage: 0.2\n")
    assert_ok(run_check(repo, "--all"))

    append(repo, WORKLOG, "\n## 2026-10-10T14:00:00+03:00 — Шаг 0.3 начат: скелет frontend\n")
    commit(repo, "docs(worklog): step 0.3 started\n\nStage: 0.3\n")

    assert_error(run_check(repo, "--all"), "STEP_NO_END")
