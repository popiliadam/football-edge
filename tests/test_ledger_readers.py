"""Defterin tek okuyucusu ve tek yazarı (Faz 6 İz B §5.1/3, §6.4/3a).

(1) Zincir okuyucusu (`collect._ledger_rows`, `_ledger_row`, `_anchor_break`) iki ilişkiden okur —
`odds_snapshots` ve `site_audit.ledger_rows` — ve yalnız bu kapalı kümeden; ikinci bir okuyucu
yazılmaz. (2) Anlık görüntünün kesimi (`max(id)`) defter yazımlarının `lock_ledger` ile
serileştiği varsayımına dayanır: `odds_snapshots`a INSERT yapan tek yol `db.insert_snapshots`tir ve
ilk ifadesi kilittir. Kilitsiz bir yazar eklenirse bu dosya kırmızı olur. Canlı DB'ye elle SQL ile
yazmayı durdurmaz (§12.4/14).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import pytest

from football_edge.anchors import Anchor
from football_edge.collect import (
    _LEDGER_COLUMNS,
    LEDGER_AUDIT_VIEW,
    LEDGER_RELATIONS,
    LEDGER_TABLE,
    _anchor_break,
    _ledger_row,
    _ledger_rows,
)
from tests.fake_db import LEDGER_COLUMNS, FakeChainDb, chained_rows

REPO = Path(__file__).resolve().parent.parent
WRITE = re.compile(r"\b(?:insert\s+into|copy)\s+(?:public\.)?odds_snapshots\b", re.IGNORECASE)


class _Recording:
    """`FakeChainDb`in gönderilen SQL'i kaydeden sargısı."""

    def __init__(self) -> None:
        self.db = FakeChainDb(chained_rows(3))
        self.seen: list[str] = []

    def cursor(self) -> Any:
        cursor = self.db.cursor()
        original = cursor.execute

        def execute(sql: str, params: Any = None) -> None:
            self.seen.append(" ".join(sql.split()))
            original(sql, params)

        cursor.execute = execute  # type: ignore[method-assign]
        return cursor


def test_the_hashed_columns_are_one_tuple_shared_with_the_test_fake() -> None:
    assert _LEDGER_COLUMNS == LEDGER_COLUMNS


@pytest.mark.parametrize("relation", [LEDGER_TABLE, LEDGER_AUDIT_VIEW])
def test_every_reader_reads_the_relation_it_is_given(relation: str) -> None:
    db = _Recording()
    rows = _ledger_rows(db, None, relation=relation)  # type: ignore[arg-type]
    _ledger_row(db, 2, relation=relation)  # type: ignore[arg-type]
    _anchor_break(db, Anchor(Path("x"), 3, 3, str(rows[-1]["row_hash"])), relation=relation)  # type: ignore[arg-type]

    assert db.seen and all(text.split(" FROM ")[1].split()[0] == relation for text in db.seen)


def test_a_relation_outside_the_closed_set_is_refused() -> None:
    with pytest.raises(ValueError, match="bilinmeyen defter ilişkisi"):
        _ledger_rows(FakeChainDb(chained_rows(1)), None, relation="odds_snapshots; drop")  # type: ignore[arg-type]
    assert {"odds_snapshots", "site_audit.ledger_rows"} == LEDGER_RELATIONS


def test_the_only_ledger_writer_is_insert_snapshots_and_it_locks_first() -> None:
    """Envanter: `odds_snapshots`a yazan metin yalnız `db.INSERT_SNAPSHOTS`; SQL fonksiyonu yok."""
    writers = sorted(
        path.relative_to(REPO).as_posix()
        for root in ("src", "scripts", "db/migrations")
        for path in (REPO / root).rglob("*")
        if path.suffix in {".py", ".sql", ".sh"} and WRITE.search(path.read_text(encoding="utf-8"))
    )
    tree = ast.parse((REPO / "src/football_edge/db.py").read_text(encoding="utf-8"))
    users = sorted(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(isinstance(n, ast.Name) and n.id == "INSERT_SNAPSHOTS" for n in ast.walk(node))
    )
    (writer,) = [
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "insert_snapshots"
    ]
    first = [
        s
        for s in writer.body
        if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
    ][0]

    assert writers == ["src/football_edge/db.py"]
    assert users == ["insert_snapshots"]
    assert isinstance(first, ast.Expr) and ast.unparse(first) == "lock_ledger(conn)"
