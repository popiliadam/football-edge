"""`jev_item_answers` okuyucu mühürü (DEFERRED 17a; son inceleme I-3).

Tablo cevapların yanında `t1_failed:<n>` İŞARET satırları da taşır (`tier1.FAILED_PREFIX`):
olasılık yok, maliyet 0, `choice` = sebep. İşareti cevap sanan bir okuyucu haberi "sorulmuş" sayar
ya da kapıya sahte bir satır sokar. Kural: `src`teki her SELECT metni ya işareti `FAILED_PREFIX`
parametresiyle süzen, adı aşağıda yazılı bir okuyucudur ya da kırmızıdır (dosya:satır ile).
Satırlarını süzmeden `gates_from`a veren okuyucu ayrı `GATES_READERS` kümesine BİLİNÇLE eklenir ve
sabiti kullanılan her fonksiyon `gates_from`u çağırmalıdır; `gates_from`un işareti yok saydığını
`test_feature_tier1.py::test_gates_ignore_failure_markers` sabitler.

Metin STATİK olarak kurulur (17h, son inceleme M-4/M-5): sabit, f-string, `+` birleştirme, `%` ve
`.format` biçimleme, `psycopg.sql.SQL/Identifier/Literal` parçaları; parçadaki ad aynı modülün düz
metin sabitine (`TABLO = "jev_item_answers"`) çözülür. Postgres tırnaksız adı küçük harfe indirdiği
için büyük harf tablo adı da okumadır.

Bilinen sınırlar (bilinçli kaçışı değil kazara girişi durdurur, Faz 3 §3.1/12): başka modülden
import edilen ya da nitelikle okunan sabit (`modul.TABLO`), fonksiyon içinde çalışma anında kurulan
ad, `db/migrations` altındaki VIEW/fonksiyon gövdeleri ve `scripts/` taranmaz; `gates_from`a verme
yalnız aynı fonksiyon gövdesinde aranır (fonksiyonlar arası veri akışı izlenmez).
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

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
# Satırlarını süzgeç yerine `gates_from`a veren okuyucular (bugün yok). Buradaki bir sabitin
# kullanıldığı her fonksiyon `gates_from`u çağırmalıdır (`misrouted`).
GATES_READERS: frozenset[tuple[str, str]] = frozenset()
GATES = "gates_from"
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


# `psycopg.sql` birleştirme parçaları: argümanları metnin parçasıdır.
_SQL_PARTS = frozenset({"SQL", "Identifier", "Literal"})


def _constants(tree: ast.Module) -> dict[str, str]:
    """Modül düzeyinde düz metin sabitleri (`AD = "…"`): yalnız bileşik metnin PARÇASI olunca
    çözülür — `execute(_ASKED)` gibi tek başına kullanılan ad yeni bir okuma değildir."""
    found: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        else:
            continue
        if (
            isinstance(target, ast.Name)
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        ):
            found[target.id] = value.value
    return found


class _Static:
    """Bir ifadenin statik metni; okunan her alt düğüm `used`a düşer (ayrıca taranmasın diye)."""

    def __init__(self, names: dict[str, str]) -> None:
        self.names = names
        self.used: set[ast.AST] = set()

    def text(self, node: ast.AST) -> str | None:
        self.used.add(node)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            # f-string tek metin sayılır: SELECT ve tablo adı ayrı parçalara düşse de yakalanır.
            return "".join(self._piece(part) or "{}" for part in node.values)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self._joined((node.left, node.right), "")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            return self._joined((node.left, node.right), " ")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "format":
                values = (node.func.value, *node.args, *(kw.value for kw in node.keywords))
                return self._joined(values, " ")
            if node.func.attr in _SQL_PARTS:
                return self._joined(node.args, " ")
        return None

    def _piece(self, node: ast.AST) -> str | None:
        self.used.add(node)
        if isinstance(node, ast.Name):
            return self.names.get(node.id)
        if isinstance(node, ast.FormattedValue):
            return self._piece(node.value)
        if isinstance(node, ast.Tuple):
            return self._joined(node.elts, " ")
        return self.text(node)

    def _joined(self, nodes: Iterable[ast.AST], glue: str) -> str | None:
        pieces = [self._piece(node) for node in nodes]
        if all(piece is None for piece in pieces):
            return None
        return glue.join("{}" if piece is None else piece for piece in pieces)


def _reads(text: str) -> bool:
    # Tırnaksız ad Postgres'te küçük harfe iner: `FROM JEV_ITEM_ANSWERS` aynı tabloyu okur.
    return TABLE in text.lower() and SELECT.search(text) is not None


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
        static = _Static(_constants(tree))
        # `ast.walk` genişlik önceliklidir: bileşik ifade parçalarından önce gelir, parçaları
        # `used`a düşer ve ayrıca okunmaz (aynı metin iki kez sayılmaz).
        for node in ast.walk(tree):
            if node in static.used or not isinstance(node, ast.expr):
                continue
            text = static.text(node)
            if text is not None and _reads(text):
                name = _owner(node, parents)
                yield Sql(path.relative_to(root).as_posix(), name, node.lineno, text)


def unsealed(
    root: Path, known: frozenset[tuple[str, str]] = READERS | NOT_READERS | GATES_READERS
) -> list[str]:
    """Adı listede olmayan her `jev_item_answers` SELECT'i, `dosya:satır ad` olarak."""
    return [
        f"{sql.path}:{sql.line} {sql.name or '<adsız>'}"
        for sql in _statements(root)
        if (sql.path, sql.name) not in known
    ]


def _calls(function: ast.AST, name: str) -> bool:
    return any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == name)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == name)
        )
        for node in ast.walk(function)
    )


def misrouted(root: Path, gates_readers: frozenset[tuple[str, str]]) -> list[str]:
    """`gates_readers`teki sabitin HİÇ kullanılmadığı ya da `gates_from` çağırmayan bir fonksiyonda
    (veya modül düzeyinde) kullanıldığı her okuyucu, `dosya ad` olarak."""
    wrong: list[str] = []
    for path, constant in sorted(gates_readers):
        tree = ast.parse((root / path).read_text(encoding="utf-8"))
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        uses = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id == constant and isinstance(node.ctx, ast.Load)
        ]
        feeds = [_calls(_function(use, parents), GATES) for use in uses]
        if not feeds or not all(feeds):
            wrong.append(f"{path} {constant}")
    return wrong


def _function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST:
    """En içteki fonksiyon; modül düzeyindeki kullanım için kendisi (hiçbir çağrı taşımaz)."""
    current = parents.get(node)
    while current is not None:
        if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
            return current
        current = parents.get(current)
    return node


def test_every_select_on_jev_item_answers_is_a_named_marker_aware_reader() -> None:
    assert unsealed(SRC) == [], (
        f"{TABLE} okuyan yeni SELECT: işaret satırlarını (`FAILED_PREFIX`) süzmeli ya da "
        "satırlarını `gates_from`a vermeli, sonra READERS'a adıyla eklenmeli"
    )


def test_the_allowlisted_readers_filter_markers_and_still_exist() -> None:
    """Liste bayatlamaz: silinen okuyucu listeden de düşer; kalan her okuyucu işareti süzer."""
    found = {(sql.path, sql.name): sql.text for sql in _statements(SRC)}

    assert set(found) == READERS | NOT_READERS | GATES_READERS
    assert not READERS & GATES_READERS, "okuyucu ya süzer ya gates_from'a verir"
    assert misrouted(SRC, GATES_READERS) == []
    assert all(MARKER_FILTER in found[reader] for reader in READERS)
    assert set(DIRECTION) == READERS, "her okuyucunun süzgeç yönü adıyla yazılı olmalı"
    wrong = [name for (_, name), rule in DIRECTION.items() if not rule.search(found[(_, name)])]
    assert wrong == [], f"süzgeç yönü yanlış: {wrong}"
    assert all(
        found[other].count(TABLE) == 1 and f"INSERT INTO {TABLE}" in found[other]
        for other in NOT_READERS
    )


TABLE_LINE = 'TABLO = "jev_item_answers"\n'
# 17h (son inceleme M-4/M-5): her kaçış tek bir okumadır ve `ad` adıyla adlandırılır.
ESCAPES = {
    "f-string-sabit": 'Q = f"SELECT * FROM {TABLO}"',
    "yüzde": 'Q = "SELECT * FROM %s" % TABLO',
    "yüzde-demet": 'Q = "SELECT %s FROM %s" % ("item_id", TABLO)',
    "format": 'Q = "SELECT * FROM {}".format(TABLO)',
    "format-ad": 'Q = "SELECT * FROM {t}".format(t=TABLO)',
    "artı": 'Q = "SELECT item_id FROM " + TABLO + " WHERE true"',
    "büyük-harf": 'Q = "SELECT item_id FROM JEV_ITEM_ANSWERS"',
    "psycopg-sql": 'Q = sql.SQL("SELECT * FROM {}").format(sql.Identifier("jev_item_answers"))',
}


def _tree(tmp: Path, body: str) -> Path:
    (tmp / "mod.py").write_text(TABLE_LINE + body + "\n", encoding="utf-8")
    return tmp


@pytest.mark.parametrize("body", ESCAPES.values(), ids=ESCAPES.keys())
def test_a_select_built_from_parts_is_still_a_read(tmp_path: Path, body: str) -> None:
    assert unsealed(_tree(tmp_path, body)) == ["mod.py:2 Q"]


def test_an_inline_concatenated_select_is_an_unnamed_read(tmp_path: Path) -> None:
    body = 'def load(cur):\n    return cur.execute("SELECT * FROM " + TABLO).fetchall()'
    assert unsealed(_tree(tmp_path, body)) == ["mod.py:3 <adsız>"]


def test_a_named_constant_used_alone_is_not_a_second_read(tmp_path: Path) -> None:
    """Adın çözülmesi yalnız bileşik metnin parçasında: `execute(Q)` Q'yu ikinci kez saymaz."""
    body = 'Q = "SELECT 1 FROM jev_item_answers"\n\ndef load(cur):\n    return cur.execute(Q)'
    assert unsealed(_tree(tmp_path, body)) == ["mod.py:2 Q"]


GATE_READER = frozenset({("mod.py", "_GATE_ROWS")})
GATE_BODY = """_GATE_ROWS = "SELECT * FROM jev_item_answers WHERE prompt_version = %s"

def gates(cur, version):
    return gates_from(cur.execute(_GATE_ROWS, (version,)).fetchall())
"""


def test_a_listed_gates_reader_that_feeds_gates_from_is_sealed(tmp_path: Path) -> None:
    root = _tree(tmp_path, GATE_BODY)

    assert unsealed(root) == ["mod.py:2 _GATE_ROWS"], "listede olmayan okuyucu kırmızı"
    assert unsealed(root, READERS | NOT_READERS | GATE_READER) == []
    assert misrouted(root, GATE_READER) == []


@pytest.mark.parametrize(
    "extra",
    [
        "\ndef peek(cur):\n    return cur.execute(_GATE_ROWS).fetchall()\n",
        "\nROWS = _GATE_ROWS\n",
    ],
    ids=["süzgeçsiz-fonksiyon", "modül-düzeyi"],
)
def test_a_listed_gates_reader_used_without_gates_from_is_red(tmp_path: Path, extra: str) -> None:
    """Listede adı olan okuyucu süzgeç yerine `gates_from`a VERMELİ: sabitin `gates_from`
    çağırmayan tek bir kullanımı işareti ham okur."""
    assert misrouted(_tree(tmp_path, GATE_BODY + extra), GATE_READER) == ["mod.py _GATE_ROWS"]


def test_a_listed_gates_reader_that_is_never_used_is_red(tmp_path: Path) -> None:
    body = GATE_BODY.split("\n\ndef", 1)[0]
    assert misrouted(_tree(tmp_path, body), GATE_READER) == ["mod.py _GATE_ROWS"]
