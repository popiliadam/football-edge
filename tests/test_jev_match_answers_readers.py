"""`jev_match_answers` okuyucu mühürü (Plan 2 Task 3, inceleme turu 1 bulgu 9).

Tablo kademe 2 cevaplarının yanında `side_status:<taraf>:<sonuç>` İŞARET satırları da taşır
(`tier2.STATUS_PREFIX`): olasılık `{sonuç: 1}`, maliyet 0. İşareti cevap sanan bir özellik
okuyucusu ona soru diye bakar; cevabı işaret sanan bir sayaç tarafı "cevaplanmış" sayar. Kural
(`jev_item_answers` mühürünün eşi, aynı statik tarayıcı): `src`teki her SELECT metni adı aşağıda
yazılı bir okuyucudur ya da kırmızıdır, ve her okuyucunun YÖNÜ adıyla sabittir:

- `MARKER_READERS`: YALNIZ `asked` işaretlerini okur (`question_id = ANY(%s)`), sabitin her
  kullanımı `ASKED_MARKERS`i parametre verir (M-3: cevaplanmış taraf, R181: seçim dilimi).
- `ANSWER_READERS`: cevapları okur, işareti DIŞLAR (`AND NOT starts_with(question_id, %s)`,
  `STATUS_PREFIX`). Bugün yok — Plan 3'ün özellik okuyucusu buraya adıyla eklenir.

Tarayıcının bilinen sınırları `test_jev_item_answers_readers.py` belgesindedir.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.test_jev_item_answers_readers import _statements

SRC = Path(__file__).resolve().parent.parent / "src" / "football_edge"
TABLE = "jev_match_answers"
MARKER_READERS = frozenset(
    {
        ("features/tier2.py", "_ANSWERED"),
        # seçim dilimi sayacı (Plan 2 Task 4, R181): yalnız `asked` işaretinin VARLIĞI
        ("features/slice.py", "SLICE_SQL"),
    }
)
ANSWER_READERS: frozenset[tuple[str, str]] = frozenset()
# INSERT'in SELECT'i `unnest`ten okur; tablo adı metinde YALNIZ INSERT hedefi olarak geçer.
NOT_READERS = frozenset({("features/tier2.py", "INSERT_MATCH_ANSWERS")})
# Tablo takma adı (`a.question_id`) da aynı süzgeçtir: dilim sayacı EXISTS ile `model_predictions`a
# bağlanır ve sütunları nitelikle yazar (Plan 2 Task 4).
MARKERS_ONLY = re.compile(r"\bAND\s+(?:\w+\.)?question_id\s*=\s*ANY\(%s\)")
# İşaret okuyucusunda süzgeci delen biçimler: `OR` dalı ve satır yorumu (inceleme 8).
LOOSE = re.compile(r"\bOR\b|--", re.IGNORECASE)
EXCLUDES_MARKERS = re.compile(r"\bAND\s+NOT\s+starts_with\(question_id, %s\)")
ASKED_MARKERS = "ASKED_MARKERS"


def marker_faults(text: str) -> list[str]:
    """İşaret okuyucusu metninin kusurları: `asked` süzgeci yok, tablo bir kez geçmiyor (alt sorgu
    ya da öz-birleşim süzgeçsiz satır okur), `OR` ya da `--` süzgeci deler."""
    faults = []
    if not MARKERS_ONLY.search(text):
        faults.append("asked süzgeci yok")
    if text.lower().count(TABLE) != 1:
        faults.append(f"{TABLE} bir kez geçmiyor")
    if LOOSE.search(text):
        faults.append("OR ya da -- yorum")
    return faults


def unsealed(root: Path) -> list[str]:
    known = MARKER_READERS | ANSWER_READERS | NOT_READERS
    return [
        f"{sql.path}:{sql.line} {sql.name or '<adsız>'}"
        for sql in _statements(root, TABLE)
        if (sql.path, sql.name) not in known
    ]


def _passes_markers(root: Path, path: str, constant: str) -> bool:
    """Sabitin her yüklenişi, `ASKED_MARKERS`i de argüman alan bir çağrının içinde mi?"""
    tree = ast.parse((root / path).read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    uses = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == constant and isinstance(node.ctx, ast.Load)
    ]

    def wrapped(use: ast.Name) -> bool:
        return any(
            any(arg is use for arg in call.args)
            and any(
                isinstance(n, ast.Name) and n.id == ASKED_MARKERS
                for arg in call.args
                for n in ast.walk(arg)
            )
            for call in calls
        )

    return bool(uses) and all(wrapped(use) for use in uses)


def test_every_select_on_jev_match_answers_is_a_named_marker_aware_reader() -> None:
    assert unsealed(SRC) == [], (
        f"{TABLE} okuyan yeni SELECT: işareti (`STATUS_PREFIX`) dışlamalı ya da yalnız `asked` "
        "işaretini okumalı, sonra MARKER_READERS / ANSWER_READERS'a adıyla eklenmeli"
    )


def test_the_allowlisted_readers_keep_their_direction_and_still_exist() -> None:
    """Liste bayatlamaz; her okuyucunun yönü metinde ve (işaret okuyucusunda) çağrıda sabit."""
    found = {(sql.path, sql.name): sql.text for sql in _statements(SRC, TABLE)}

    assert set(found) == MARKER_READERS | ANSWER_READERS | NOT_READERS
    assert not MARKER_READERS & ANSWER_READERS
    assert {r: marker_faults(found[r]) for r in MARKER_READERS if marker_faults(found[r])} == {}
    assert [r for r in MARKER_READERS if not _passes_markers(SRC, *r)] == []
    assert [r for r in ANSWER_READERS if not EXCLUDES_MARKERS.search(found[r])] == []
    assert all(
        found[other].count(TABLE) == 1 and f"INSERT INTO {TABLE}" in found[other]
        for other in NOT_READERS
    )


ESCAPES = {
    "düz": 'Q = "SELECT * FROM jev_match_answers"',
    "f-string": 'T = "jev_match_answers"\nQ = f"SELECT * FROM {T}"',
    "büyük-harf": 'Q = "SELECT match_id FROM JEV_MATCH_ANSWERS"',
    "artı": 'T = "jev_" + "match_answers"\nQ = "SELECT match_id FROM " + T',
}


@pytest.mark.parametrize("body", ESCAPES.values(), ids=ESCAPES.keys())
def test_a_new_reader_of_the_match_table_is_red(tmp_path: Path, body: str) -> None:
    (tmp_path / "mod.py").write_text(body + "\n", encoding="utf-8")

    (only,) = unsealed(tmp_path)
    assert only.startswith("mod.py:") and only.endswith(" Q")


MARKER_BODY = """_ANSWERED = "SELECT match_id FROM jev_match_answers WHERE question_id = ANY(%s)"

def answered(cur):
    cur.execute(_ANSWERED, (list(ASKED_MARKERS),))
"""


@pytest.mark.parametrize(
    ("where", "matches"),
    [
        ("WHERE variant = %s AND question_id = ANY(%s)", True),
        ("WHERE a.variant = %s AND a.question_id = ANY(%s)", True),
        ("WHERE a.variant = %s AND NOT a.question_id = ANY(%s)", False),
        ("WHERE a.variant = %s AND a.match_id = ANY(%s)", False),
        ("WHERE a.question_id = ANY(%s)", False),
    ],
    ids=["düz", "takma-ad", "değil", "başka-sütun", "and-yok"],
)
def test_the_marker_filter_reads_through_a_table_alias_only(where: str, matches: bool) -> None:
    assert bool(MARKERS_ONLY.search(where)) is matches


BYPASSES = {
    "alt-sorgu": (
        "SELECT match_id FROM jev_match_answers WHERE match_id IN (SELECT match_id FROM "
        "jev_match_answers WHERE variant = %s AND question_id = ANY(%s))"
    ),
    "öz-birleşim": (
        "SELECT b.question_id FROM jev_match_answers a JOIN jev_match_answers b "
        "ON b.match_id = a.match_id WHERE a.variant = %s AND a.question_id = ANY(%s)"
    ),
    "or": (
        "SELECT match_id FROM jev_match_answers WHERE variant = %s AND question_id = ANY(%s) "
        "OR true"
    ),
    "yorum": (
        "SELECT match_id FROM jev_match_answers WHERE variant = %s --\n AND question_id = ANY(%s)"
    ),
}


@pytest.mark.parametrize("text", BYPASSES.values(), ids=BYPASSES.keys())
def test_a_marker_reader_that_slips_past_the_asked_filter_is_red(text: str) -> None:
    """Her biçim `MARKERS_ONLY`i geçer; yine de süzgeçsiz satır okur (inceleme 8)."""
    assert MARKERS_ONLY.search(text)
    assert marker_faults(text) != []


def test_a_marker_reader_executed_without_the_asked_markers_is_red(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text(MARKER_BODY, encoding="utf-8")
    assert _passes_markers(tmp_path, "mod.py", "_ANSWERED")

    loose = MARKER_BODY + "\ndef every(cur, ids):\n    cur.execute(_ANSWERED, (ids,))\n"
    (tmp_path / "mod.py").write_text(loose, encoding="utf-8")
    assert not _passes_markers(tmp_path, "mod.py", "_ANSWERED")
