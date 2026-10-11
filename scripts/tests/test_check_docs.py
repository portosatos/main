"""Tests for scripts/check_docs.py.

Each test builds a throwaway project with valid README.md, docs/STATUS.md and docs/NEXT.md,
checks that it passes (exit 0), then breaks exactly one thing and expects exit 1 with a
specific error code. The script is run as a CLI with --root, the way it is used in Done When.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check_docs.py"

README = """# Проект

Описание проекта.

## Чем делали

Claude Code, модель Claude Opus.

## Состояние

См. [STATUS](docs/STATUS.md).

## Предварительные требования

Docker.

## Запуск

```bash
docker compose up --build
```

## Демо

`scripts/demo.ps1`; ссылки в коде не проверяются: `[a](docs/missing-inline.md)`.

```text
[b](docs/missing-fenced.md)
```

## Тесты

`scripts/test.ps1`.

## Документация

- [STATUS](docs/STATUS.md#критерии)
- [NEXT](./docs/NEXT.md)
- [Сайт](https://example.com/nowhere.md)

## Шаблоны и генераторы

Vite template, shadcn/ui CLI.

## Что дальше

[NEXT](docs/NEXT.md).
"""

CRITERIA = [(n, "работает", f"тест `test_{n}`") for n in range(1, 24)]


def status_md(rows: list[tuple[int, str, str]]) -> str:
    lines = [
        "# Статус",
        "",
        "## Критерии",
        "",
        "| # | Требование | Статус | Чем доказано |",
        "|---|---|---|---|",
    ]
    lines += [f"| {n} | Критерий {n} | {status} | {evidence} |" for n, status, evidence in rows]
    lines += ["", "Назад к [README](../README.md).", ""]
    return "\n".join(lines)


NEXT = "# Что дальше\n\n- Редактирование порогов правил.\n"


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def make_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    write(root, "README.md", README)
    write(root, "docs/STATUS.md", status_md(CRITERIA))
    write(root, "docs/NEXT.md", NEXT)
    return root


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def assert_ok(root: Path) -> None:
    result = run(root)
    assert result.returncode == 0, result.stdout + result.stderr


def assert_error(root: Path, code: str) -> str:
    result = run(root)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"ERROR {code}" in result.stdout, result.stdout
    return result.stdout


def test_readme_has_required_sections(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    assert_ok(root)

    write(root, "README.md", README.replace("## Чем делали", "## Инструменты"))
    out = assert_error(root, "README_MISSING_SECTION")
    assert "Чем делали" in out

    write(root, "README.md", README.replace("## Шаблоны и генераторы", "## Прочее"))
    assert_error(root, "README_MISSING_SECTION")

    write(root, "README.md", README.replace("Claude Code, модель Claude Opus.", ""))
    out = assert_error(root, "README_EMPTY_SECTION")
    assert "Чем делали" in out


def test_status_lists_every_criterion_1_to_23_with_status_and_evidence(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    assert_ok(root)

    write(root, "docs/STATUS.md", status_md([row for row in CRITERIA if row[0] != 7]))
    out = assert_error(root, "STATUS_MISSING_CRITERION")
    assert "7" in out

    rows = [(n, s, "" if n == 12 else e) for n, s, e in CRITERIA]
    write(root, "docs/STATUS.md", status_md(rows))
    out = assert_error(root, "STATUS_NO_EVIDENCE")
    assert "12" in out

    write(root, "docs/STATUS.md", status_md([*CRITERIA, (5, "работает", "ещё раз")]))
    assert_error(root, "STATUS_DUPLICATE_CRITERION")


def test_status_values_restricted_to_works_partial_broken(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    rows = [(n, ("работает", "частично", "нет")[n % 3], e) for n, _, e in CRITERIA]
    write(root, "docs/STATUS.md", status_md(rows))
    assert_ok(root)

    rows = [(n, "готово" if n == 3 else s, e) for n, s, e in CRITERIA]
    write(root, "docs/STATUS.md", status_md(rows))
    out = assert_error(root, "STATUS_BAD_VALUE")
    assert "готово" in out


def test_relative_links_in_docs_resolve(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    write(root, "docs/API.md", "# API\n\n[Код](../backend/app/main.py:12), [SPEC](SPEC.md)\n")
    write(root, "docs/SPEC.md", "# SPEC\n")
    write(root, "backend/app/main.py", "")
    assert_ok(root)

    write(root, "docs/API.md", "# API\n\n[Пропал](./GONE.md)\n")
    out = assert_error(root, "LINK_BROKEN")
    assert "docs/API.md" in out and "GONE.md" in out

    write(root, "docs/API.md", "# API\n")
    write(root, "README.md", README.replace("(docs/NEXT.md).", "(docs/NEXTT.md)."))
    out = assert_error(root, "LINK_BROKEN")
    assert "README.md" in out


def test_next_md_not_empty(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    assert_ok(root)

    write(root, "docs/NEXT.md", "# Что дальше\n\n> Пока пусто.\n\n## Кандидаты\n")
    assert_error(root, "NEXT_EMPTY")

    (root / "docs/NEXT.md").unlink()
    assert_error(root, "NEXT_EMPTY")
