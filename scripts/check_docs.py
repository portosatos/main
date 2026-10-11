"""Documentation checker for the hand-over (SPEC section 8, stage 13; docs/plan.md step 13.2).

Usage:
    python scripts/check_docs.py              # the repository this script lives in
    python scripts/check_docs.py --root PATH  # another project directory

Checks:
- README.md has every required "## " section (README_MISSING_SECTION) and none of them is
  empty (README_EMPTY_SECTION);
- docs/STATUS.md has a table with "#", "Статус" and "Чем доказано" columns that lists every
  criterion 1-23 of SPEC section 9 exactly once (STATUS_MISSING_CRITERION,
  STATUS_DUPLICATE_CRITERION), with a status of "работает", "частично" or "нет"
  (STATUS_BAD_VALUE) and non-empty evidence (STATUS_NO_EVIDENCE);
- relative links in README.md and docs/**/*.md point to existing files (LINK_BROKEN); links in
  code, external URLs and anchors are skipped, so is docs/agent-session/ (exports of sessions);
- docs/NEXT.md exists and has content besides headings and quotes (NEXT_EMPTY).

Exit code: 0 if everything is fine, 1 if there are problems, 2 on usage errors. Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

README_SECTIONS = [
    "Чем делали",
    "Состояние",
    "Предварительные требования",
    "Запуск",
    "Демо",
    "Тесты",
    "Документация",
    "Шаблоны и генераторы",
    "Что дальше",
]
CRITERIA = range(1, 24)
STATUS_VALUES = {"работает", "частично", "нет"}
SKIP_LINK_DIRS = ("docs/agent-session/",)

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REF_LINK_RE = re.compile(r"^\s*\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+\"[^\"]*\")?\s*$")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
LINE_SUFFIX_RE = re.compile(r":L?\d+(?:-L?\d+)?$")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, code: str, message: str) -> None:
        self.errors.append(f"ERROR {code}: {message}")


def strip_code(text: str) -> list[str]:
    """Lines of the text with fenced blocks blanked out and inline code removed."""
    lines: list[str] = []
    fence: str | None = None
    for line in COMMENT_RE.sub("", text).splitlines():
        match = FENCE_RE.match(line)
        if fence is not None:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
                fence = None
            lines.append("")
            continue
        if match:
            fence = match.group(1)
            lines.append("")
            continue
        lines.append(INLINE_CODE_RE.sub("", line))
    return lines


def has_content(lines: list[str]) -> bool:
    return any(line.strip() and not line.lstrip().startswith(("#", ">")) for line in lines)


def check_readme(root: Path, report: Report) -> None:
    path = root / "README.md"
    if not path.is_file():
        report.error("README_MISSING_SECTION", "README.md not found")
        return
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    raw = path.read_text(encoding="utf-8")
    for line in raw.splitlines():
        if line.startswith("## "):
            current = sections.setdefault(line[3:].strip(), [])
        elif current is not None:
            current.append(line)
    for title in README_SECTIONS:
        found = [body for heading, body in sections.items() if heading.startswith(title)]
        if not found:
            report.error("README_MISSING_SECTION", f'README.md: no "## {title}" section')
        elif not any(has_content(COMMENT_RE.sub("", "\n".join(b)).splitlines()) for b in found):
            report.error("README_EMPTY_SECTION", f'README.md: section "## {title}" is empty')


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def plain(cell: str) -> str:
    return re.sub(r"[*_`]", "", cell).strip().lower()


def check_status(root: Path, report: Report) -> None:
    path = root / "docs" / "STATUS.md"
    if not path.is_file():
        report.error("STATUS_MISSING_CRITERION", "docs/STATUS.md not found")
        return
    lines = strip_code(path.read_text(encoding="utf-8"))
    seen: dict[int, int] = {}
    i = 0
    while i + 1 < len(lines):
        header, separator = lines[i], lines[i + 1]
        if not (header.lstrip().startswith("|") and re.match(r"^\s*\|[\s:|-]+\|\s*$", separator)):
            i += 1
            continue
        columns = [plain(c) for c in split_row(header)]
        i += 2
        if not columns or columns[0] != "#" or "статус" not in columns:
            continue
        status_col = columns.index("статус")
        evidence_col = next((n for n, c in enumerate(columns) if "доказ" in c), None)
        while i < len(lines) and lines[i].lstrip().startswith("|"):
            cells = split_row(lines[i])
            lineno = i + 1
            i += 1
            if not cells or not cells[0].isdigit():
                continue
            number = int(cells[0])
            if number not in CRITERIA:
                continue
            if number in seen:
                report.error(
                    "STATUS_DUPLICATE_CRITERION",
                    f"docs/STATUS.md:{lineno}: criterion {number} again"
                    f" (first at line {seen[number]})",
                )
                continue
            seen[number] = lineno
            status = plain(cells[status_col]) if status_col < len(cells) else ""
            if status not in STATUS_VALUES:
                report.error(
                    "STATUS_BAD_VALUE",
                    f"docs/STATUS.md:{lineno}: criterion {number}: status {status!r},"
                    f" expected one of {', '.join(sorted(STATUS_VALUES))}",
                )
            evidence = (
                cells[evidence_col]
                if evidence_col is not None and evidence_col < len(cells)
                else ""
            )
            if not evidence.strip(" -—"):
                report.error(
                    "STATUS_NO_EVIDENCE",
                    f"docs/STATUS.md:{lineno}: criterion {number}: no evidence",
                )
    for number in CRITERIA:
        if number not in seen:
            report.error(
                "STATUS_MISSING_CRITERION", f"docs/STATUS.md: criterion {number} not listed"
            )


def link_targets(text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for lineno, line in enumerate(strip_code(text), start=1):
        found += [(lineno, m.group(1)) for m in LINK_RE.finditer(line)]
        ref = REF_LINK_RE.match(line)
        if ref:
            found.append((lineno, ref.group(1)))
    return found


def check_links(root: Path, report: Report) -> None:
    files = [root / "README.md", *sorted((root / "docs").rglob("*.md"))]
    for path in files:
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(SKIP_LINK_DIRS):
            continue
        for lineno, target in link_targets(path.read_text(encoding="utf-8")):
            if target.startswith("#") or SCHEME_RE.match(target):
                continue
            clean = LINE_SUFFIX_RE.sub("", unquote(target.split("#", 1)[0].split("?", 1)[0]))
            if not clean:
                continue
            base = root if clean.startswith("/") else path.parent
            if not (base / clean.lstrip("/")).exists():
                report.error("LINK_BROKEN", f"{rel}:{lineno}: {target} does not exist")


def check_next(root: Path, report: Report) -> None:
    path = root / "docs" / "NEXT.md"
    if not path.is_file():
        report.error("NEXT_EMPTY", "docs/NEXT.md not found")
    elif not has_content(strip_code(path.read_text(encoding="utf-8"))):
        report.error("NEXT_EMPTY", "docs/NEXT.md has only headings and quotes")


def run(root: Path) -> Report:
    report = Report()
    check_readme(root, report)
    check_status(root, report)
    check_links(root, report)
    check_next(root, report)
    return report


def main(argv: list[str] | None = None) -> int:
    if hasattr(
        sys.stdout, "reconfigure"
    ):  # Cyrillic messages through pipes on Windows (cp1251 by default)
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Check README.md, docs/STATUS.md, docs/NEXT.md and links."
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="project directory (default: the repository of this script)",
    )
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        parser.error(f"--root is not a directory: {root}")

    report = run(root)
    for line in report.errors:
        print(line)
    if report.errors:
        print(f"check_docs: {len(report.errors)} problem(s)")
        return 1
    print("check_docs: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
