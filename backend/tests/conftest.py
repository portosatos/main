"""Shared pytest setup: marks tests by directory (unit/ -> unit, integration/ -> integration)."""

from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        kind = Path(item.path).relative_to(TESTS_DIR).parts[0]
        if kind in ("unit", "integration"):
            item.add_marker(kind)
