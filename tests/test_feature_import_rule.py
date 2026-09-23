"""Özellik paketinin import kuralı (spec §5/4) prose'da kalmaz.

`football_edge.features` altındaki hiçbir modül holdout'u (`history.holdout`), dönem süzmeyen
tarihsel yolu (`history.sync`), holdout açılışını (`backtest.final_eval`) ve canlı sonuç/kapanış
okuyucusunu (`live.store`) import edemez: özellik karar anında bilinemeyecek bir şeye yol
bulamamalı. İki katman: (1) AST taraması doğrudan anmayı yakalar — `import`, `from … import`
(göreli dâhil), `from paket import modül`, öznitelik zinciri ve modül adını TAM taşıyan dize
(`importlib.import_module("…")`), ayrıca yasaklı bir modülün ÜST paketini bağlayan import
(`import football_edge`, `from football_edge import live`, `import football_edge.live as fl`,
`from football_edge.live import *`): bağlanan paketten yasaklı modüle öznitelikle
(`live.store.x`) ulaşılır ve bu erişim import satırında adı hiç geçirmez; (2) ayrı bir süreçte
paketin her modülü import edilir ve yasaklı modüllerin `sys.modules`e dolaylı yoldan da girmediği
ölçülür. Yasaklı modülün kardeşine tam adıyla ulaşmak (`from football_edge.live import context`)
serbesttir.
Bilinen sınır: hesaplanmış dize (`"football_edge.live." + "store"`) (1)'de görünmez; (2) onu
yalnız import anında çalışan kodda yakalar — fonksiyon içindeki hesaplanmış dize iki katmanda da
görünmez.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PACKAGE = "football_edge.features"
PACKAGE_DIR = REPO / "src" / "football_edge" / "features"
RULE = "(spec §5/4)"
FORBIDDEN = (
    "football_edge.history.holdout",
    "football_edge.history.sync",
    "football_edge.backtest.final_eval",
    "football_edge.live.store",
)


def _hit(dotted: str) -> str | None:
    for module in FORBIDDEN:
        if dotted == module or dotted.startswith(module + "."):
            return module
    return None


def _parent(dotted: str) -> str | None:
    """`dotted` yasaklı bir modülün uygun öneki (üst paketi) ise o modül."""
    for module in FORBIDDEN:
        if module.startswith(dotted + "."):
            return module
    return None


def _base(node: ast.ImportFrom, module: str) -> str:
    if node.level == 0:
        return node.module or ""
    package = module.split(".")[: -node.level]
    return ".".join([*package, *([node.module] if node.module else [])])


def _dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted(node.value)
        return None if parent is None else f"{parent}.{node.attr}"
    return None


def _findings(tree: ast.AST, module: str) -> Iterator[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if (hit := _hit(alias.name)) is not None:
                    yield node.lineno, f"import {alias.name} → {hit}"
                elif (hit := _parent(alias.name)) is not None:
                    yield node.lineno, f"import {alias.name} → {hit} üst paketi bağlanıyor"
        elif isinstance(node, ast.ImportFrom):
            base = _base(node, module)
            if (hit := _hit(base)) is not None:
                yield node.lineno, f"from {base} import … → {hit}"
                continue
            for alias in node.names:
                bound = base if alias.name == "*" else f"{base}.{alias.name}"
                if (hit := _hit(bound)) is not None:
                    yield node.lineno, f"from {base} import {alias.name} → {hit}"
                elif (hit := _parent(bound)) is not None:
                    form = f"from {base} import {alias.name}"
                    yield node.lineno, f"{form} → {hit} üst paketi bağlanıyor"
        elif isinstance(node, ast.Attribute) and _dotted(node) in FORBIDDEN:
            yield node.lineno, f"{_dotted(node)} erişimi"
        elif isinstance(node, ast.Constant) and node.value in FORBIDDEN:
            yield node.lineno, f"{node.value!r} dizesi"


def forbidden_imports(source: str, path: str, module: str) -> list[str]:
    tree = ast.parse(source, filename=path)
    return [f"{path}:{line}: {form} {RULE}" for line, form in sorted(_findings(tree, module))]


def _anchor(path: Path) -> str:
    """Göreli import'un çözüldüğü nokta; `__init__` de bir ad parçası sayılır."""
    return ".".join(path.relative_to(REPO / "src").with_suffix("").parts)


def _module_of(path: Path) -> str:
    anchor = _anchor(path)
    return anchor.removesuffix(".__init__")


def _feature_files() -> list[Path]:
    return sorted(PACKAGE_DIR.rglob("*.py"))


# ── Koruma 1: dedektör kırmızı verebiliyor mu ──────────────────────────────────────────────

HERE = "football_edge.features.derive"
REFERENCES = [
    "import football_edge.live.store",
    "import football_edge.history.holdout as h",
    "import football_edge.backtest.final_eval",
    "from football_edge.live.store import load_quotes",
    "from football_edge.history.sync import load_matches",
    "from football_edge.backtest.final_eval import run_final",
    "from football_edge.live import store",
    "from football_edge.history import holdout as kilit",
    "from football_edge.backtest import final_eval",
    "from ..live.store import load_live_matches",
    "from ..live import store",
    "from ..history import sync",
    # `import a.b.c` `a`yı bağlar; öznitelik zinciri tek ihlaldir, bağlanan üst paket izinlidir.
    "import football_edge.features.types\nrows = football_edge.live.store.load_quotes(c)",
    'importlib.import_module("football_edge.live.store")',
    '__import__("football_edge.history.holdout")',
    # Üst paket bağlanırsa yasaklı modüle öznitelikle, import satırında adı geçmeden ulaşılır.
    "from football_edge import live\n\ndef f():\n    return live.store.load_quotes",
    "import football_edge.live as fl\nfl.store.load_quotes",
    "from football_edge import history\nhistory.sync.load_matches",
    "import football_edge",
    "import football_edge.backtest",
    "from .. import live",
    "from football_edge.live import *",
]
MENTIONS = [
    "from football_edge import features",
    "from .. import features",
    "from . import types",
    "from football_edge.live.context import LiveMatch",
    "from football_edge.history.types import HistMatch",
    "import football_edge.live.context",
    "from ..live.context import LiveMatch",
    "from football_edge.live import context",
    '"""football_edge.live.store burada import edilmez."""',
    "# from football_edge.live.store import load_quotes",
    "storefront = football_edge.live.storefront",
    'LOGGER.info("football_edge.history.sync çağrılmadı")',
]


@pytest.mark.leakage
@pytest.mark.parametrize("snippet", REFERENCES)
def test_detector_sees_every_reference_form_once(snippet: str) -> None:
    found = forbidden_imports(snippet, "src/football_edge/features/derive.py", HERE)

    assert len(found) == 1, f"tek ihlal bekleniyordu: {snippet!r} → {found}"


@pytest.mark.leakage
@pytest.mark.parametrize("snippet", MENTIONS)
def test_detector_ignores_allowed_modules_and_mere_mentions(snippet: str) -> None:
    assert forbidden_imports(snippet, "src/football_edge/features/derive.py", HERE) == []


@pytest.mark.leakage
def test_relative_imports_resolve_from_the_importing_module() -> None:
    """`from ..live import store` alt pakette başka bir modüle çözülür; çözüm seviyeyi saymalı."""
    snippet = "from ...live import store"

    assert forbidden_imports(snippet, "x.py", "football_edge.features.alt.derin") != []
    assert forbidden_imports(snippet, "x.py", HERE) == []


@pytest.mark.leakage
def test_violations_name_path_line_and_rule() -> None:
    source = "import math\nfrom football_edge.live.store import load_quotes\n"

    assert forbidden_imports(source, "src/football_edge/features/x.py", HERE) == [
        "src/football_edge/features/x.py:2: from football_edge.live.store import … → "
        f"football_edge.live.store {RULE}"
    ]


# ── Koruma 2: tarama gerçek kaynağa ulaşıyor ─────────────────────────────────────────────────


@pytest.mark.leakage
def test_scan_reaches_the_known_feature_modules() -> None:
    scanned = {_module_of(path) for path in _feature_files()}
    expected = {
        PACKAGE,
        f"{PACKAGE}.__main__",
        f"{PACKAGE}.types",
        f"{PACKAGE}.news",
        f"{PACKAGE}.derive",
        f"{PACKAGE}.shift",
    }

    assert expected <= scanned, f"taranmayan: {sorted(expected - scanned)}"


# ── Depo ───────────────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_no_feature_module_names_a_forbidden_module() -> None:
    violations = [
        found
        for path in _feature_files()
        for found in forbidden_imports(
            path.read_text(encoding="utf-8"), path.relative_to(REPO).as_posix(), _anchor(path)
        )
    ]

    assert not violations, "özellik paketi yasaklı modüle erişiyor:\n" + "\n".join(violations)


_PROBE = """
import importlib, sys
for name in sys.argv[1:]:
    importlib.import_module(name)
print(",".join(sorted(m for m in {forbidden} if m in sys.modules)))
"""


@pytest.mark.leakage
def test_importing_every_feature_module_loads_no_forbidden_module_even_indirectly() -> None:
    modules = [_module_of(path) for path in _feature_files()]
    probe = _PROBE.format(forbidden=repr(set(FORBIDDEN)))
    env = {**os.environ, "PYTHONPATH": str(REPO / "src")}

    result = subprocess.run(
        [sys.executable, "-c", probe, *modules],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"dolaylı yoldan yüklenen: {result.stdout.strip()}"


@pytest.mark.leakage
def test_the_indirect_probe_can_see_a_forbidden_module() -> None:
    """Pozitif kontrol: sonda yasaklı bir modülü gerçekten görebiliyor mu."""
    probe = _PROBE.format(forbidden=repr(set(FORBIDDEN)))
    env = {**os.environ, "PYTHONPATH": str(REPO / "src")}

    result = subprocess.run(
        [sys.executable, "-c", probe, "football_edge.live.store"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    # Task 2 `live.store`a `backtest.walkforward` import eder; zincir `history.holdout`u da
    # yükler (inceleme I-1).
    assert "football_edge.live.store" in result.stdout.strip().split(","), result.stderr
