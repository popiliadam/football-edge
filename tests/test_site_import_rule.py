"""H1f: `football_edge.site`in GEÇİŞLİ import kapanışı holdout'a ve tarihsel tabana ulaşamaz.

Faz 6 İz B tasarımı §2 H1f. Bekçi YASAK LİSTEYLE kodlanır (izin listesiyle değil): boş
`football_edge.history` paket `__init__`i kapanışta meşru olarak durur; `history.types`
`market.devig` ve `market.consensus` üzerinden bilinçli olarak kapanıştadır. İki katman: (1) AST ile
her modülün `import`larını — fonksiyon içindekiler dâhil — ve dize LİTERALİYLE yapılan dinamik
importları (`importlib.import_module("…")`, `import_module(name="…")`, `__import__("…")`;
göreli literal `import_module("..x", __package__)` da) izleyerek kapanışı kurar; (2) ayrı bir
süreçte paketin her modülünü import edip `sys.modules`i okur. Bilinen sınır: adı ya da paketi
HESAPLANMIŞ (literal olmayan) dizeyle yapılan import
(`importlib.import_module("football_edge." + ad)`) (1)'de görünmez; (2) onu yalnız import anında
çalışan kodda yakalar.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
ROOT = "football_edge.site"
FORBIDDEN = (
    "football_edge.history.store",
    "football_edge.history.lock",
    "football_edge.history.holdout",
    "football_edge.history.football_data",
    "football_edge.history.sync",
    "football_edge.history.catalog",
    "football_edge.backtest",
    "football_edge.live.context",
)

pytestmark = pytest.mark.leakage


def _path_of(module: str, src: Path = SRC) -> Path | None:
    base = src.joinpath(*module.split("."))
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    return None


def _with_parents(module: str) -> set[str]:
    parts = module.split(".")
    return {".".join(parts[:end]) for end in range(1, len(parts) + 1)}


_DYNAMIC_IMPORTS = frozenset({"import_module", "__import__"})


def _argument(node: ast.Call, position: int, keyword: str) -> ast.expr | None:
    if len(node.args) > position:
        return node.args[position]
    return next((kw.value for kw in node.keywords if kw.arg == keyword), None)


def _literal_import(node: ast.Call, package: str) -> str | None:
    """Dize literaliyle yapılan dinamik importun mutlak adı; literal değilse `None` (sınır)."""
    func = node.func
    called = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    name = _argument(node, 0, "name")
    if called not in _DYNAMIC_IMPORTS or not isinstance(name, ast.Constant):
        return None
    if not isinstance(name.value, str):
        return None
    relative = name.value[: len(name.value) - len(name.value.lstrip("."))]
    if not relative:
        return name.value
    anchor_arg = _argument(node, 1, "package")
    if isinstance(anchor_arg, ast.Constant) and isinstance(anchor_arg.value, str):
        anchor = anchor_arg.value
    elif isinstance(anchor_arg, ast.Name) and anchor_arg.id == "__package__":
        anchor = package
    else:
        return None
    parts = anchor.split(".")[: len(anchor.split(".")) - len(relative) + 1]
    return ".".join([*parts, name.value[len(relative) :]])


def _imports(module: str, src: Path = SRC) -> set[str]:
    """`module`ün doğrudan yüklediği `football_edge` modülleri (üst paketler dâhil)."""
    path = _path_of(module, src)
    if path is None:
        return set()
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                anchor = package.split(".")[: len(package.split(".")) - node.level + 1]
                base = ".".join([*anchor, *([node.module] if node.module else [])])
            else:
                base = node.module or ""
            found.add(base)
            found |= {
                f"{base}.{alias.name}"
                for alias in node.names
                if _path_of(f"{base}.{alias.name}", src) is not None
            }
        elif isinstance(node, ast.Call):
            target = _literal_import(node, package)
            if target is not None:
                found.add(target)
    return {
        name
        for module_name in found
        if module_name.startswith("football_edge")
        for name in _with_parents(module_name)
    }


def closure(roots: set[str], src: Path = SRC) -> set[str]:
    seen: set[str] = set()
    pending = [name for root in roots for name in _with_parents(root)]
    while pending:
        current = pending.pop()
        if current not in seen:
            seen.add(current)
            pending.extend(_imports(current, src) - seen)
    return seen


def forbidden_in(modules: set[str]) -> list[str]:
    return sorted(
        name
        for name in modules
        if any(name == banned or name.startswith(banned + ".") for banned in FORBIDDEN)
    )


def _site_modules() -> set[str]:
    package = SRC / "football_edge" / "site"
    return {
        ".".join(path.relative_to(SRC).with_suffix("").parts).removesuffix(".__init__")
        for path in package.rglob("*.py")
    }


def test_the_site_package_has_modules_to_scan() -> None:
    assert {ROOT, f"{ROOT}.contract", f"{ROOT}.schema"} <= _site_modules()


def test_the_static_closure_reaches_no_forbidden_module() -> None:
    reached = closure(_site_modules())

    assert forbidden_in(reached) == [], "site kapanışı yasaklı modüle ulaşıyor"


def test_the_static_walker_follows_imports_transitively(tmp_path: Path) -> None:
    """Pozitif kontrol: iki adım ötedeki, fonksiyon içinde import edilen yasaklı modül görünür."""
    package = tmp_path / "football_edge"
    for name, body in {
        "__init__.py": "",
        "site/__init__.py": "",
        "site/a.py": "from football_edge.market import b\n",
        "market/__init__.py": "",
        "market/b.py": "def f():\n    from ..history import holdout\n    return holdout\n",
        "history/__init__.py": "",
        "history/holdout.py": "",
    }.items():
        (package / name).parent.mkdir(parents=True, exist_ok=True)
        (package / name).write_text(body, encoding="utf-8")

    reached = closure({"football_edge.site.a"}, src=tmp_path)

    assert forbidden_in(reached) == ["football_edge.history.holdout"]


@pytest.mark.parametrize(
    "call",
    [
        'importlib.import_module("football_edge.history.holdout")',
        'importlib.import_module(name="football_edge.history.holdout")',
        'import_module("football_edge.history.holdout")',
        '__import__("football_edge.history.holdout")',
        'importlib.import_module("..history.holdout", __package__)',
        'importlib.import_module(".holdout", package="football_edge.history")',
    ],
)
def test_the_static_walker_sees_literal_dynamic_imports(tmp_path: Path, call: str) -> None:
    """Pozitif kontrol: dize literaliyle, fonksiyon içinde yapılan import da kapanıştadır."""
    package = tmp_path / "football_edge"
    for name, body in {
        "__init__.py": "",
        "site/__init__.py": "",
        "site/c.py": (
            "import importlib\nfrom importlib import import_module\n\n\n"
            f"def f():\n    return {call}\n"
        ),
        "history/__init__.py": "",
        "history/holdout.py": "",
    }.items():
        (package / name).parent.mkdir(parents=True, exist_ok=True)
        (package / name).write_text(body, encoding="utf-8")

    reached = closure({"football_edge.site.c"}, src=tmp_path)

    assert forbidden_in(reached) == ["football_edge.history.holdout"]


_PROBE = """
import importlib, sys
for name in sys.argv[1:]:
    importlib.import_module(name)
print(",".join(sorted(m for m in sys.modules if m.startswith("football_edge"))))
"""


def test_importing_every_site_module_loads_no_forbidden_module() -> None:
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, *sorted(_site_modules())],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert forbidden_in(set(result.stdout.strip().split(","))) == []
