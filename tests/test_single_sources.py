"""Tek kaynaklı sabitler (DEFERRED 16j, 17i): bir kez tanımlanır, her yer import eder."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "football_edge"


def _files_with_literal(value: object) -> set[str]:
    found: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.Constant)
            and type(node.value) is type(value)
            and node.value == value
            for node in ast.walk(tree)
        ):
            found.add(path.relative_to(SRC).as_posix())
    return found


def test_the_reference_book_literal_lives_in_one_place() -> None:
    # `football_data.BOOKS` kaynağın sütun adlarını sayar; `live/context` canlı kitap ortalamasının
    # yapısal karşılığıdır (başka kaynak) — ikisi de referans kitabın tanımı değildir.
    assert _files_with_literal("Avg") == {
        "history/types.py",
        "history/football_data.py",
        "live/context.py",
    }


def test_the_log_floor_literal_lives_in_one_place() -> None:
    assert _files_with_literal(1e-15) == {"market/metrics.py"}
