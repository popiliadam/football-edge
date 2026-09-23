"""Holdout erişim kuralı (tasarım §5.3, D8) prose'da kalmaz: holdout yalnız izinli yerde açılır.

Her açılış `holdout_access_log`a düşer ve faz kapıları açılış sayısını ister (Faz 2: sıfır). Kaydı
atlamanın üç yolu burada yakalanır: `open_holdout`ı izinsiz bir modülden çağırmak; anahtarın modüle
özel mührünü (`_HOLDOUT_SEAL`) `holdout.py` dışında anmak — mühürle elle kurulan bir `HoldoutKey`
açılışı kayda yazmadan holdout'u açardı; ve bütün dönemleri dönen `_load_all`ı (R96) kilit yolunun
dışında anmak — holdout satırları `history/` paketinden anahtarsız çıkmaz. Aynı satırları
`_load_all`sız kuran ham yol da korunur (R119): `load_files` (önbellek baytı), `parse_file`
(bayt → maç, dönem süzmez) ve `sync._parsed` (ikisinin birleşimi).

`open_holdout` yalnız `src/football_edge/backtest/final_eval.py`de anılabilir; o dosya Faz 3'te
yazılır, yani Faz 2 boyunca hiçbir yerde. `_load_all` ve ham yolun üç adı yalnız `history/sync.py`
(senkron ve `load_matches`) ve `history/__main__.py` (kilit komutu) içinde: kilit ve senkron
holdout satırını zorunlu olarak ayrıştırır. Bir `def` anma değil, tanımdır — `store.py` ve
`football_data.py` izin listesinde olmadan temiz kalır.
Taranan: `src/` ve `scripts/` altındaki her `.py`, özyinelemeli (`tests/` taranmaz: testler
holdout'u taklit bağlantıyla açar).

Anma biçimleri: ad (çağrı, atama), öznitelik (`holdout.open_holdout`), `from … import` (takma adlı
da), holdout modülünden `*` ve adı TAM taşıyan her dize sabiti: `getattr(x, "open_holdout")`,
`holdout.__dict__["open_holdout"]`, `f.__globals__["_HOLDOUT_SEAL"]`, `vars(m)["_HOLDOUT_SEAL"]`,
`__import__(…, fromlist=["open_holdout"])`. Docstring, yorum ve adı başka metinle birlikte taşıyan
dize anma sayılmaz. Bilinen sınırlar: hesaplanmış adlar (`"open_" + "holdout"`) ve adı daha uzun
bir metnin içinde taşıyan dizeler (`exec("open_holdout(c)")`, `attrgetter("h.open_holdout")`)
görünmez — bu test kazara girişi durdurur, kasıtlı kaçışı kırmızı takım denetimi (Task 11) arar.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RULE = "(tasarım §5.3, D8)"
FINAL_EVAL = "src/football_edge/backtest/final_eval.py"
HOLDOUT_MODULE = "src/football_edge/history/holdout.py"
SYNC_MODULE = "src/football_edge/history/sync.py"
HISTORY_CLI = "src/football_edge/history/__main__.py"
STORE_MODULE = "src/football_edge/history/store.py"
PARSER_MODULE = "src/football_edge/history/football_data.py"
PYTHON_ROOTS = ("src", "scripts")
# Korunan ad → (anılabildiği dosyalar, neden). Yollar depo köküne göre, tam eşleşme.
GUARDED: dict[str, tuple[frozenset[str], str]] = {
    "open_holdout": (
        frozenset({FINAL_EVAL}),
        "holdout yalnız son değerlendirmede açılır; açılış kayda düşer",
    ),
    "_HOLDOUT_SEAL": (
        frozenset({HOLDOUT_MODULE}),
        "mühürle elle kurulan anahtar açılışı kayda yazmaz",
    ),
    # 12i (Faz 3): anahtar yalnız tanımlandığı, tüketildiği ve açıldığı üç modülde anılır;
    # işçiler anahtar değil seçilmiş satır alır.
    "HoldoutKey": (
        frozenset({HOLDOUT_MODULE, SYNC_MODULE, FINAL_EVAL}),
        "anahtar yalnız final_eval'de açılır ve load_matches'e verilir (12i)",
    ),
    "_load_all": (
        frozenset({SYNC_MODULE, HISTORY_CLI}),
        "bütün dönemleri döner; holdout satırları history/'den anahtarsız çıkmaz (R96)",
    ),
    # Ham yol (R119): önbellek baytı → dönem süzülmemiş maçlar. `_load_all`ın anmadığı bir
    # modül bu üçüyle holdout satırlarını `open_holdout`suz ve kayda düşmeden kurardı.
    "load_files": (
        frozenset({SYNC_MODULE, HISTORY_CLI}),
        "önbellek baytını döner; ayrıştırılınca holdout satırları anahtarsız çıkar (R119)",
    ),
    "parse_file": (
        frozenset({SYNC_MODULE, HISTORY_CLI}),
        "dönem süzmez; holdout satırlarını anahtarsız kurar (R119)",
    ),
    "_parsed": (
        frozenset({SYNC_MODULE, HISTORY_CLI}),
        "önbellek baytından bütün dönemlerin maçlarını kurar (R119)",
    ),
}

Finding = tuple[int, str, str]  # (satır, korunan ad, anma biçimi)


def rule_violations(source: str, path: str) -> list[str]:
    """`path`teki korunan adların izinsiz BÜTÜN anmaları, satır sırasıyla."""
    findings = sorted(_findings(ast.parse(source, filename=path)))
    return [
        f"{path}:{line}: {form} — {GUARDED[name][1]} {RULE}"
        for line, name, form in findings
        if path not in GUARDED[name][0]
    ]


def _findings(tree: ast.AST) -> Iterator[Finding]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in GUARDED:
            yield node.lineno, node.id, f"{node.id} adı"
        elif isinstance(node, ast.Attribute) and node.attr in GUARDED:
            yield node.lineno, node.attr, f".{node.attr} erişimi"
        elif isinstance(node, ast.ImportFrom):
            yield from _import_findings(node)
        elif isinstance(node, ast.Constant):
            yield from _constant_findings(node)


def _import_findings(node: ast.ImportFrom) -> Iterator[Finding]:
    module = "." * node.level + (node.module or "")
    for alias in node.names:
        if alias.name in GUARDED:
            yield node.lineno, alias.name, f"from {module} import {alias.name}"
        elif alias.name == "*" and module.rsplit(".", 1)[-1] == "holdout":
            # `*` open_holdout'u getirir ve adı gizler; mühür `_` ile başladığı için gelmez.
            yield node.lineno, "open_holdout", f"from {module} import *"


def _constant_findings(node: ast.Constant) -> Iterator[Finding]:
    # Adı TAM taşıyan dize anmadır: `getattr(m, "…")`, `m.__dict__["…"]`, `f.__globals__["…"]`,
    # `vars(m)["…"]`, `fromlist=["…"]` adı hep böyle taşır. Adı başka metinle taşıyan dize değil.
    if isinstance(node.value, str) and node.value in GUARDED:
        yield node.lineno, node.value, f"{node.value!r} dizesi"


def _python_files(root: Path) -> list[Path]:
    return sorted(path for sub in PYTHON_ROOTS for path in (root / sub).rglob("*.py"))


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _scan(root: Path) -> list[str]:
    return [
        found
        for path in _python_files(root)
        for found in rule_violations(path.read_text(encoding="utf-8"), _rel(path, root))
    ]


# ── Koruma 1: dedektör kırmızı verebiliyor mu ──────────────────────────────────────────────

ELSEWHERE = "src/football_edge/market/efficiency.py"
REFERENCES = [
    'open_holdout(conn, purpose="son", git_sha=sha, now=now)',
    "from football_edge.history.holdout import open_holdout",
    "from .holdout import open_holdout as ac",
    "key = holdout.open_holdout(conn, purpose='x', git_sha=sha, now=now)",
    "opener = holdout.open_holdout",
    'getattr(holdout, "open_holdout")',
    'holdout.__dict__["open_holdout"]',
    '__import__("football_edge.history.holdout", fromlist=["open_holdout"])',
    "from football_edge.history.holdout import *",
    "from football_edge.history.holdout import _HOLDOUT_SEAL",
    "make(opened_at=t, purpose='x', git_sha=s, _seal=holdout._HOLDOUT_SEAL)",
    "from football_edge.history.holdout import HoldoutKey",
    "def f(key: holdout.HoldoutKey) -> None: ...",
    'select_periods.__globals__["_HOLDOUT_SEAL"]',
    'vars(holdout)["_HOLDOUT_SEAL"]',
    "from football_edge.history.sync import _load_all",
    "rows = sync._load_all(conn, catalog)",
    "_load_all(conn, catalog)",
    'getattr(sync, "_load_all")',
    'sync.__dict__["_load_all"]',
    "from football_edge.history.store import load_files",
    "files = store.load_files(conn, paths)",
    'getattr(store, "load_files")',
    "from football_edge.history.football_data import parse_file",
    "from .football_data import parse_file as ayristir",
    "result = football_data.parse_file(content, league=lg, season=None)",
    'vars(football_data)["parse_file"]',
    "from football_edge.history.sync import _parsed",
    "matches = sync._parsed(path, content, league)",
]
MENTIONS = [
    '"""open_holdout yalnız final_eval.py\'de çağrılır."""',
    'def f() -> None:\n    """open_holdout burada çağrılmaz."""\n',
    "# open_holdout(conn)",
    'LOGGER.info("open_holdout çağrılmadı")',
    "from football_edge.history.holdout import HOLDOUT, select_periods",
    "open_holdout_count = 0",
    "log_fetch(conn, rows_parsed=len(result.matches))",
    '"""parse_file dönem süzmez; load_files önbellek baytını döner."""',
]


@pytest.mark.leakage
@pytest.mark.parametrize("snippet", REFERENCES)
def test_detector_sees_every_reference_form_once(snippet: str) -> None:
    violations = rule_violations(snippet, ELSEWHERE)

    assert len(violations) == 1, f"tek ihlal bekleniyordu: {snippet!r} → {violations}"


@pytest.mark.leakage
@pytest.mark.parametrize("snippet", MENTIONS)
def test_detector_ignores_mere_mentions(snippet: str) -> None:
    assert rule_violations(snippet, ELSEWHERE) == []


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("snippet", "path"),
    [
        ("from football_edge.history.holdout import open_holdout", FINAL_EVAL),
        (
            "key = HoldoutKey(opened_at=t, purpose=p, git_sha=s, _seal=_HOLDOUT_SEAL)",
            HOLDOUT_MODULE,
        ),
        ("matches = _load_all(conn, catalog)", SYNC_MODULE),
        ("from football_edge.history.sync import _load_all", HISTORY_CLI),
        ("files = load_files(conn, paths)", SYNC_MODULE),
        ("result = parse_file(content, league=league, season=season)", SYNC_MODULE),
        ("matches = _parsed(path, content, league)", SYNC_MODULE),
        ("from football_edge.history.store import load_files", HISTORY_CLI),
        ("from football_edge.history.football_data import parse_file", HISTORY_CLI),
        # Tanım anma değildir: tanımlayan modüller izin listesinde olmadan temiz kalır.
        ("def load_files(conn, paths):\n    return {}\n", STORE_MODULE),
        ("def parse_file(content, *, league, season):\n    return None\n", PARSER_MODULE),
    ],
)
def test_each_guarded_name_is_allowed_only_in_its_files(snippet: str, path: str) -> None:
    assert rule_violations(snippet, path) == []


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("snippet", "path"),
    [
        ("open_holdout(conn)", "scripts/final_eval.py"),
        ("open_holdout(conn)", "src/football_edge/history/final_eval.py"),
        ("_HOLDOUT_SEAL", "src/football_edge/backtest/holdout.py"),
        ("_load_all(conn, catalog)", "src/football_edge/backtest/sync.py"),
        ("_load_all(conn, catalog)", "src/football_edge/market/__main__.py"),
        ("load_files(conn, paths)", "src/football_edge/backtest/sync.py"),
        ("parse_file(content, league=lg, season=None)", "src/football_edge/market/__main__.py"),
        ("_parsed(path, content, league)", "scripts/sync.py"),
    ],
)
def test_allow_list_matches_the_exact_path_not_the_file_name(snippet: str, path: str) -> None:
    assert len(rule_violations(snippet, path)) == 1


@pytest.mark.leakage
def test_violations_name_path_line_and_reason() -> None:
    source = "import os\nfrom football_edge.history.holdout import open_holdout\nopen_holdout(c)\n"
    reason = GUARDED["open_holdout"][1]

    assert rule_violations(source, "scripts/x.py") == [
        f"scripts/x.py:2: from football_edge.history.holdout import open_holdout — {reason} {RULE}",
        f"scripts/x.py:3: open_holdout adı — {reason} {RULE}",
    ]


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.leakage
def test_tree_scan_walks_both_roots_recursively(tmp_path: Path) -> None:
    """Dosyaya "ulaşmak" yetmez: okunduğu ve bulgunun köke göreli yolla geldiği ölçülür."""
    _write(tmp_path, "src/paket/alt/derin.py", "open_holdout(conn)\n")
    _write(tmp_path, "scripts/araclar/betik.py", "from x.holdout import open_holdout\n")
    _write(tmp_path, "tests/test_x.py", "open_holdout(conn)\n")

    found = {violation.split(":", 1)[0] for violation in _scan(tmp_path)}

    assert found == {"src/paket/alt/derin.py", "scripts/araclar/betik.py"}


# ── Koruma 2: tarama gerçek kaynağa ulaşıyor ─────────────────────────────────────────────────


@pytest.mark.leakage
def test_scan_reaches_the_known_sources() -> None:
    """Kök kayar ya da özyineleme düşerse kural hiçbir şeyi taramadan yeşil kalırdı."""
    scanned = {_rel(path, REPO) for path in _python_files(REPO)}
    expected = {HOLDOUT_MODULE, "src/football_edge/fetch.py", "scripts/ops_alert.py"}

    assert expected <= scanned, f"taranmayan: {sorted(expected - scanned)}"


@pytest.mark.leakage
def test_detector_sees_the_seal_in_the_real_holdout_module() -> None:
    """Gerçek dosyada pozitif kontrol: mühür yeniden adlandırılırsa kuralın yarısı sessizce söner;
    aynı metin başka bir yolda okunduğunda kırmızı vermeli."""
    source = (REPO / HOLDOUT_MODULE).read_text(encoding="utf-8")

    assert "_HOLDOUT_SEAL" in {name for _, name, _ in _findings(ast.parse(source))}
    assert rule_violations(source, HOLDOUT_MODULE) == []
    assert rule_violations(source, "src/football_edge/history/lock.py") != []


@pytest.mark.leakage
def test_detector_sees_the_raw_parse_path_in_the_real_sync_module() -> None:
    """Gerçek dosyada pozitif kontrol (R119): önbellek baytı → bütün dönemlerin maçları yolu
    `sync.py`de yaşar; adlardan biri yeniden adlandırılırsa kural o yolu sessizce görmez olur."""
    source = (REPO / SYNC_MODULE).read_text(encoding="utf-8")
    raw_path = {"load_files", "parse_file", "_parsed"}

    assert raw_path <= {name for _, name, _ in _findings(ast.parse(source))}
    assert rule_violations(source, SYNC_MODULE) == []
    assert rule_violations(source, "src/football_edge/market/sync.py") != []


# ── Depo ───────────────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_holdout_is_opened_only_where_allowed() -> None:
    violations = _scan(REPO)

    assert not violations, "holdout izinsiz açılabiliyor:\n" + "\n".join(violations)


# ── Faz 3: anahtarın akışı (12i) ve ayrıştırıcının özel yardımcıları (14h) ──────────────────


def key_misuses(source: str) -> list[str]:
    """`open_holdout`un döndürdüğü adın `load_matches(..., key=ad)` ve `del ad` DIŞINDA her
    kullanımı: anahtar döndürülemez, saklanamaz, başka bir fonksiyona verilemez."""
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    keys = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and _calls(node.value, "open_holdout")
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    return [
        f"{node.lineno}: {node.id}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and node.id in keys
        and isinstance(node.ctx, ast.Load)
        and not _is_load_matches_key(node, parents)
    ]


def _calls(node: ast.AST, name: str) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (isinstance(func, ast.Name) and func.id == name) or (
        isinstance(func, ast.Attribute) and func.attr == name
    )


def _is_load_matches_key(node: ast.Name, parents: dict[ast.AST, ast.AST]) -> bool:
    keyword = parents.get(node)
    if not isinstance(keyword, ast.keyword) or keyword.arg != "key":
        return False
    call = parents.get(keyword)
    return call is not None and _calls(call, "load_matches")


PROTECTED_MODULES = ("football_edge.history.football_data", "football_edge.history.store")
HISTORY_PACKAGE = "src/football_edge/history/"


def private_accesses(source: str, path: str) -> list[str]:
    """14h: `history/` dışından ayrıştırıcının ve önbelleğin `_`-önekli adlarına erişim."""
    if path.startswith(HISTORY_PACKAGE):
        return []
    tree = ast.parse(source)
    aliases: set[str] = set()
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases |= {
                alias.asname or alias.name
                for alias in node.names
                if alias.name in PROTECTED_MODULES
            }
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                full = f"{node.module}.{alias.name}"
                if full in PROTECTED_MODULES:
                    aliases.add(alias.asname or alias.name)
                elif node.module in PROTECTED_MODULES and alias.name.startswith("_"):
                    found.append(f"{path}:{node.lineno}: from {node.module} import {alias.name}")
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr.startswith("_")
            and not node.attr.startswith("__")
            and _root(node.value) in aliases
        ):
            found.append(f"{path}:{node.lineno}: .{node.attr} erişimi")
    return found


def _root(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        dotted = _root(node.value)
        return None if dotted is None else f"{dotted}.{node.attr}"
    return None


@pytest.mark.leakage
def test_the_real_final_eval_hands_the_key_only_to_load_matches() -> None:
    source = (REPO / FINAL_EVAL).read_text(encoding="utf-8")

    assert "open_holdout(" in source, "kural boşa yeşil kalmasın: final_eval anahtarı açıyor"
    assert key_misuses(source) == []


KEY_MISUSES = [
    "key = open_holdout(c, purpose=p, git_sha=s, now=n)\nreturn key",
    "key = open_holdout(c, purpose=p, git_sha=s, now=n)\nself.key = key",
    "key = holdout.open_holdout(c, purpose=p, git_sha=s, now=n)\nevaluate(rows, key)",
    "key = open_holdout(c, purpose=p, git_sha=s, now=n)\nkeys = [key]",
    "key = open_holdout(c, purpose=p, git_sha=s, now=n)\nselect_periods(m, periods=x, key=key)",
    "key = open_holdout(c, purpose=p, git_sha=s, now=n)\nload_matches(c, catalog, None, key)",
]


@pytest.mark.leakage
@pytest.mark.parametrize("snippet", KEY_MISUSES)
def test_every_other_use_of_the_key_is_a_misuse(snippet: str) -> None:
    assert len(key_misuses(snippet)) == 1


@pytest.mark.leakage
def test_handing_the_key_to_load_matches_and_deleting_it_is_allowed() -> None:
    snippet = (
        "key = open_holdout(c, purpose=p, git_sha=s, now=n)\n"
        "rows = load_matches(c, catalog, lock=lock, key=key)\n"
        "del key\n"
    )

    assert key_misuses(snippet) == []


PRIVATE_ACCESSES = [
    "from football_edge.history.football_data import _records",
    "from football_edge.history.store import _LOAD_FILES",
    "from football_edge.history import football_data\nfootball_data._decode(b'x')",
    "from football_edge.history import store as s\ns._LOAD_FILES",
    "import football_edge.history.football_data as fd\nfd._row(ctx, rec)",
    "import football_edge.history.football_data\nfootball_edge.history.football_data._context(r)",
]


@pytest.mark.leakage
@pytest.mark.parametrize("snippet", PRIVATE_ACCESSES)
def test_private_parser_helpers_are_closed_outside_history(snippet: str) -> None:
    assert len(private_accesses(snippet, ELSEWHERE)) == 1


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("snippet", "path"),
    [
        ("from football_edge.history.football_data import parse", ELSEWHERE),
        ("from football_edge.history import football_data\nfootball_data.__name__", ELSEWHERE),
        ("from football_edge.history.football_data import _records", SYNC_MODULE),
        ("from football_edge.backtest import harness\nharness._context(0, m, t)", ELSEWHERE),
    ],
)
def test_public_names_dunders_and_the_history_package_stay_clean(snippet: str, path: str) -> None:
    assert private_accesses(snippet, path) == []


@pytest.mark.leakage
def test_no_module_outside_history_reaches_the_private_parser_helpers() -> None:
    violations = [
        found
        for path in _python_files(REPO)
        for found in private_accesses(path.read_text(encoding="utf-8"), _rel(path, REPO))
    ]

    assert not violations, "ayrıştırıcının özel yardımcılarına erişim:\n" + "\n".join(violations)
