"""`jev_item_answers` okuyucu mühürü (DEFERRED 17a; son inceleme I-3).

Tablo cevapların yanında `t1_failed:<n>` İŞARET satırları da taşır (`tier1.FAILED_PREFIX`):
olasılık yok, maliyet 0, `choice` = sebep. İşareti cevap sanan bir okuyucu haberi "sorulmuş" sayar
ya da kapıya sahte bir satır sokar. Kural: `src`teki her SELECT metni ya işareti `FAILED_PREFIX`
parametresiyle süzen, adı aşağıda yazılı bir okuyucudur ya da kırmızıdır (dosya:satır ile).
Satırlarını `gates_from`a veren yeni bir okuyucu da buraya BİLİNÇLE eklenir; `gates_from`un işareti
yok saydığını `test_feature_tier1.py::test_gates_ignore_failure_markers` sabitler.

Sınır: metin bir sabit ya da f-string olarak yazılmalıdır — `"SELECT ..." + tablo` gibi çalışma
anında birleştirilen parçaları kural görmez.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "football_edge"
TABLE = "jev_item_answers"
SELECT = re.compile(r"\bselect\b", re.IGNORECASE)
# İşareti süzdüğü KANITLI okuyucular: (dosya, sabitin adı). İkisi de `FAILED_PREFIX`i
# `starts_with(question_id, %s)` parametresine verir (`asked_item_ids`, `failed_attempts`).
READERS = frozenset(
    {
        ("features/tier1.py", "_ASKED"),
        ("features/tier1.py", "_ATTEMPTS"),
    }
)
# Tabloyu OKUMAYAN ama iki sözcüğü de taşıyan metin: INSERT'in SELECT'i `unnest`ten okur; tablo
# adı metinde YALNIZ INSERT hedefi olarak geçer (aşağıdaki test bunu da sınar).
NOT_READERS = frozenset({("features/tier1.py", "INSERT_ITEM_ANSWERS")})
MARKER_FILTER = "starts_with(question_id, %s)"
# Süzgecin YÖNÜ okuyucuya göre sabittir (son inceleme I-1): `_ASKED` cevapları okur, işareti
# DIŞLAR; `_ATTEMPTS` yalnız işaretleri sayar. `NOT` düşerse `_ASKED` cevaplanmış haberi
# sorulmamış sayar ve her koşuda yeniden satın alır — alt dize denetimi bunu göremiyordu.
DIRECTION = {
    ("features/tier1.py", "_ASKED"): re.compile(r"\bAND\s+NOT\s+starts_with\(question_id, %s\)"),
    ("features/tier1.py", "_ATTEMPTS"): re.compile(r"\bAND\s+starts_with\(question_id, %s\)"),
}


@dataclass(frozen=True)
class Sql:
    path: str
    name: str | None  # metnin atandığı ad; satır içi metin (`execute("SELECT …")`) adsızdır
    line: int
    text: str


def _text(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        # f-string tek metin sayılır: SELECT ve tablo adı ayrı parçalara düşse de yakalanır.
        return "".join(
            part.value if isinstance(part, ast.Constant) else "{}" for part in node.values
        )
    return None


def _reads(text: str) -> bool:
    return TABLE in text and SELECT.search(text) is not None


def _owner(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str | None:
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, ast.Assign) and len(current.targets) == 1:
            target = current.targets[0]
            return target.id if isinstance(target, ast.Name) else None
        if isinstance(current, ast.AnnAssign):
            return current.target.id if isinstance(current.target, ast.Name) else None
        current = parents.get(current)
    return None


def _statements(root: Path) -> Iterator[Sql]:
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if isinstance(parents.get(node), ast.JoinedStr):
                continue  # f-string'in parçası: bütünü ayrıca okunur
            text = _text(node)
            if isinstance(node, ast.expr) and text is not None and _reads(text):
                name = _owner(node, parents)
                yield Sql(path.relative_to(root).as_posix(), name, node.lineno, text)


def unsealed(root: Path) -> list[str]:
    """Adı listede olmayan her `jev_item_answers` SELECT'i, `dosya:satır ad` olarak."""
    known = READERS | NOT_READERS
    return [
        f"{sql.path}:{sql.line} {sql.name or '<adsız>'}"
        for sql in _statements(root)
        if (sql.path, sql.name) not in known
    ]


def test_every_select_on_jev_item_answers_is_a_named_marker_aware_reader() -> None:
    assert unsealed(SRC) == [], (
        f"{TABLE} okuyan yeni SELECT: işaret satırlarını (`FAILED_PREFIX`) süzmeli ya da "
        "satırlarını `gates_from`a vermeli, sonra READERS'a adıyla eklenmeli"
    )


def test_the_allowlisted_readers_filter_markers_and_still_exist() -> None:
    """Liste bayatlamaz: silinen okuyucu listeden de düşer; kalan her okuyucu işareti süzer."""
    found = {(sql.path, sql.name): sql.text for sql in _statements(SRC)}

    assert set(found) == READERS | NOT_READERS
    assert all(MARKER_FILTER in found[reader] for reader in READERS)
    assert set(DIRECTION) == READERS, "her okuyucunun süzgeç yönü adıyla yazılı olmalı"
    wrong = [name for (_, name), rule in DIRECTION.items() if not rule.search(found[(_, name)])]
    assert wrong == [], f"süzgeç yönü yanlış: {wrong}"
    assert all(
        found[other].count(TABLE) == 1 and f"INSERT INTO {TABLE}" in found[other]
        for other in NOT_READERS
    )
