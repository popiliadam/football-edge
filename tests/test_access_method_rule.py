"""Erişim yöntemi kuralı (spec §3.2.1, R77) prose'da kalmaz: yasak araçlar koda giremez.

Sayfayı okumak serbest; kaynağın engelini ya da kimlik denetimini aşmak yasak. Parmak izini
gizleyen/taklit eden, bot kontrolünü atlatan ya da User-Agent taklit eden araçlar üç eksende
aranır: A) `src/` ve `scripts/` Python kaynağı onları import etmez (AST); B) `uv.lock` ve
`pyproject.toml` onları bildirmez; C) iş akışları ve kabuk betikleri onları kurmaz.

`FORBIDDEN` tablosu spec'teki "ve benzerleri"nin TAMAMI DEĞİLDİR; otorite spec'tir — tabloda
olmayan bir araç izinli değil, yalnız bu testin görmediği bir araçtır. Kuralın davranış tarafı
(403/429'da kimlik ya da yol değiştirip yeniden denemek, proxy döndürmek) burada ölçülmez.

YASAK DEĞİL: `playwright`, `selenium`, `httpx`, `requests`, taban `scrapling` — dürüst kimlikli
başsız tarayıcı ve ayrıştırıcı §3.2.1'de izinli. Scrapling'de yasak olan fetcher tarafıdır:
`StealthyFetcher` ve oturumları, ve onu çeken her ekstra (`scrapling[...]`).

Bilinen sınırlar (A görmez): hesaplanmış string'ler (`"cam" + "oufox"`), `exec`/`eval`, alt
süreçte `python -m ...`. Arkalarındaki ağ B eksenidir: paket kurulu değilse çalışmaz.
"""

from __future__ import annotations

import ast
import re
import tomllib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
LOCK = REPO / "uv.lock"
PYPROJECT = REPO / "pyproject.toml"
RULE = "(spec §3.2.1, R77)"

# (dağıtım adı, import kökü, neden) — modül ve kilit listeleri YALNIZ buradan türer.
FORBIDDEN: tuple[tuple[str, str, str], ...] = (
    ("camoufox", "camoufox", "parmak izi taklit eden Firefox türevi (spec §3.2.1 adıyla)"),
    (
        "undetected-chromedriver",
        "undetected_chromedriver",
        "bot tespitinden kaçmak için yamanmış chromedriver (spec §3.2.1 adıyla)",
    ),
    ("nodriver", "nodriver", "undetected-chromedriver'ın ardılı, aynı amaç"),
    ("zendriver", "zendriver", "nodriver çatalı, aynı amaç"),
    ("patchright", "patchright", "tespit edilmemek için yamanmış Playwright çatalı"),
    ("undetected-playwright", "undetected_playwright", "tespit edilmemek için yamanmış Playwright"),
    ("playwright-stealth", "playwright_stealth", "başsız tarayıcının otomasyon izini gizler"),
    ("selenium-stealth", "selenium_stealth", "Selenium'un otomasyon izini gizler"),
    ("browserforge", "browserforge", "sahte tarayıcı başlığı ve parmak izi üretir"),
    (
        "apify-fingerprint-datapoints",
        "apify_fingerprint_datapoints",
        "parmak izi taklidi için veri kümesi",
    ),
    ("curl-cffi", "curl_cffi", "TLS/HTTP2 tarayıcı parmak izi taklidi (curl-impersonate)"),
    ("tls-client", "tls_client", "TLS parmak izi taklidi"),
    ("cloudscraper", "cloudscraper", "Cloudflare bot kontrolünü atlatır"),
    ("cfscrape", "cfscrape", "Cloudflare bot kontrolünü atlatır"),
    ("fake-useragent", "fake_useragent", "User-Agent taklidi ve döndürme (R2)"),
    ("botasaurus", "botasaurus", "bot tespitini aşmak için kurulmuş çatı"),
)
FORBIDDEN_DISTRIBUTIONS = {distribution: reason for distribution, _, reason in FORBIDDEN}
FORBIDDEN_MODULES = {module: reason for _, module, reason in FORBIDDEN}
INSTALL_REASONS = {name: reason for dist, module, reason in FORBIDDEN for name in (dist, module)}

# Scrapling paketi serbest (ayrıştırıcı); yasak olan parmak izini gizleyen fetcher tarafı.
SCRAPLING_NAMES = frozenset({"StealthyFetcher", "StealthySession", "AsyncStealthySession"})
SCRAPLING_REASON = "Scrapling'in tarayıcı parmak izini gizleyen fetcher'ı (spec §3.2.1 adıyla)"
# PyPI scrapling 0.4.15: her ekstra (`ai`/`shell`/`rag`/`all` dahil) `fetchers`ı çeker — curl_cffi,
# patchright, browserforge, …; taban paket yalnız ayrıştırıcıdır (lxml, cssselect, orjson, …).
SCRAPLING_EXTRAS_REASON = "Scrapling ekstrası parmak izi taklit eden fetcher'ları çeker"
DYNAMIC_IMPORTS = frozenset({"import_module", "__import__"})

PYTHON_ROOTS = (REPO / "src", REPO / "scripts")
INSTALL_GLOBS = (".github/workflows/*.yml", ".github/workflows/*.yaml", "scripts/*.sh", "verify.sh")

Finding = tuple[int, str, str]  # (satır, ne bulundu, neden)


# ── A. Python kaynağı (AST) ────────────────────────────────────────────────────


def python_violations(source: str, path: str) -> list[str]:
    """`source` metnindeki yasak import ve erişimlerin HEPSİ, satır sırasıyla."""
    findings = sorted(_findings(ast.parse(source, filename=path)))
    return [f"{path}:{line}: {found} — {reason} {RULE}" for line, found, reason in findings]


def _findings(tree: ast.AST) -> Iterator[Finding]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from _import_findings(node)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            yield from _import_from_findings(node)
        elif isinstance(node, ast.Attribute) and node.attr in SCRAPLING_NAMES:
            yield node.lineno, f".{node.attr} erişimi", SCRAPLING_REASON
        elif isinstance(node, ast.Call):
            yield from _call_findings(node)


def _root(module: str) -> str:
    return module.split(".")[0]


def _import_findings(node: ast.Import) -> Iterator[Finding]:
    for alias in node.names:
        reason = FORBIDDEN_MODULES.get(_root(alias.name))
        if reason:
            yield node.lineno, f"import {alias.name}", reason


def _import_from_findings(node: ast.ImportFrom) -> Iterator[Finding]:
    module = node.module or ""
    names = [alias.name for alias in node.names]
    reason = FORBIDDEN_MODULES.get(_root(module))
    if reason:
        yield node.lineno, f"from {module} import {', '.join(names)}", reason
    elif _root(module) == "scrapling":
        for name in names:
            if name == "*" or name in SCRAPLING_NAMES:  # `*` StealthyFetcher'ı da getirir
                yield node.lineno, f"from {module} import {name}", SCRAPLING_REASON


def _call_findings(node: ast.Call) -> Iterator[Finding]:
    callee = _callee(node.func)
    if callee in DYNAMIC_IMPORTS:
        module = _string_arg(node, 0) or ""
        reason = FORBIDDEN_MODULES.get(_root(module))
        if reason:
            yield node.lineno, f"{callee}({module!r})", reason
    elif callee == "getattr":
        name = _string_arg(node, 1)
        if name in SCRAPLING_NAMES:
            yield node.lineno, f"getattr(..., {name!r})", SCRAPLING_REASON


def _callee(func: ast.expr) -> str | None:
    """`f(...)` ve `x.f(...)` için `f`: `importlib.import_module` da yakalanır."""
    if isinstance(func, ast.Name):
        return func.id
    return func.attr if isinstance(func, ast.Attribute) else None


def _string_arg(node: ast.Call, index: int) -> str | None:
    arg = node.args[index] if index < len(node.args) else None
    return arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None


# ── B. Bağımlılık bildirimi (kilit ve pyproject) ───────────────────────────────


def normalise(name: str) -> str:
    """PEP 503: küçük harf, `-`/`_`/`.` dizileri tek `-`."""
    return re.sub(r"[-_.]+", "-", name).lower()


def lock_package_names(text: str) -> set[str]:
    """`uv.lock` metnindeki her `[[package]]` adı, normalize."""
    return {normalise(package["name"]) for package in tomllib.loads(text)["package"]}


def lock_violations(text: str) -> list[str]:
    forbidden = lock_package_names(text).intersection(FORBIDDEN_DISTRIBUTIONS)
    return [f"{name} — {FORBIDDEN_DISTRIBUTIONS[name]} {RULE}" for name in sorted(forbidden)]


def pyproject_violations(text: str) -> list[str]:
    requirements = _declared_requirements(tomllib.loads(text))
    reasons = ((requirement, _requirement_reason(requirement)) for requirement in requirements)
    return [f"{requirement} — {reason} {RULE}" for requirement, reason in reasons if reason]


def _declared_requirements(document: dict[str, Any]) -> list[str]:
    project = document.get("project", {})
    groups = [
        project.get("dependencies", []),
        *project.get("optional-dependencies", {}).values(),
        *document.get("dependency-groups", {}).values(),
    ]
    # PEP 735 `{include-group = ...}` bir gereksinim değil, başka bir grubun adıdır.
    return [item for group in groups for item in group if isinstance(item, str)]


_NAME_END = re.compile(r"[\[<>=!~;\s]")


def _requirement_reason(requirement: str) -> str | None:
    """Ad: ilk `[`, `<`, `>`, `=`, `!`, `~`, `;` ya da boşluktan önceki kısım, normalize."""
    head = requirement.strip()
    raw_name = _NAME_END.split(head, maxsplit=1)[0]
    name = normalise(raw_name)
    if name == "scrapling" and head[len(raw_name) :].lstrip().startswith("["):
        return SCRAPLING_EXTRAS_REASON
    return FORBIDDEN_DISTRIBUTIONS.get(name)


# ── C. Çalışma zamanında kurulum (iş akışları, kabuk betikleri) ───────────────

_INSTALL_PATTERN = re.compile(
    r"\b(?:" + "|".join(map(re.escape, INSTALL_REASONS)) + r")\b|scrapling\[", re.IGNORECASE
)


def install_violations(text: str, path: str) -> list[str]:
    violations = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = None if line.lstrip().startswith("#") else _INSTALL_PATTERN.search(line)
        if match:
            # Tablodaki bir ad değilse eşleşen `scrapling[`dir.
            reason = INSTALL_REASONS.get(match[0].lower(), SCRAPLING_EXTRAS_REASON)
            violations.append(f"{path}:{number}: {line.strip()} — {reason} {RULE}")
    return violations


def _python_files() -> list[Path]:
    return sorted(path for root in PYTHON_ROOTS for path in root.rglob("*.py"))


def _install_files() -> list[Path]:
    return sorted(path for pattern in INSTALL_GLOBS for path in REPO.glob(pattern))


def _rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def _scan(paths: list[Path], scan: Callable[[str, str], list[str]]) -> list[str]:
    return [found for path in paths for found in scan(path.read_text(encoding="utf-8"), _rel(path))]


# ── Koruma 1: tarayıcı kırmızı verebiliyor mu ──────────────────────────────────

FORBIDDEN_PYTHON = [
    "import camoufox",
    "import camoufox.sync_api",
    "import undetected_chromedriver as uc",
    "from curl_cffi import requests",
    "from nodriver.core import browser",
    "from scrapling import StealthyFetcher",
    "from scrapling.fetchers import AsyncStealthySession as Session",
    "from scrapling import *",
    "from scrapling.fetchers import *",
    "fetcher = scrapling.StealthyFetcher()",
    'importlib.import_module("camoufox.sync_api")',
    'import_module("cloudscraper")',
    '__import__("fake_useragent")',
    'getattr(scrapling, "StealthySession")',
]
ALLOWED_PYTHON = [
    "import httpx",
    "from scrapling.parser import Selector",
    "from scrapling import Selector",
    "import playwright.sync_api",
    "from protego import Protego",
    "stealthy = True",
    '"""camoufox bu projede kullanılmaz."""',
    "from . import camoufox",
    "from .camoufox import yardimci",
]


@pytest.mark.parametrize("snippet", FORBIDDEN_PYTHON)
def test_python_scan_catches_every_forbidden_form(snippet: str) -> None:
    assert python_violations(snippet, "ornek.py"), f"tarayıcı yasak biçimi görmedi: {snippet!r}"


@pytest.mark.parametrize("snippet", ALLOWED_PYTHON)
def test_python_scan_allows_honest_tools_and_mere_mentions(snippet: str) -> None:
    assert python_violations(snippet, "ornek.py") == []


def test_python_scan_reports_every_violation_with_path_and_line() -> None:
    """İlk ihlalde durmaz; her biri `<yol>:<satır>: <bulgu> — <neden> (spec §3.2.1, R77)`."""
    source = "import httpx\nimport camoufox\nfrom scrapling import StealthyFetcher\n"

    assert python_violations(source, "ornek.py") == [
        f"ornek.py:2: import camoufox — {FORBIDDEN_MODULES['camoufox']} {RULE}",
        f"ornek.py:3: from scrapling import StealthyFetcher — {SCRAPLING_REASON} {RULE}",
    ]


LOCK_TEMPLATE = 'version = 1\n\n[[package]]\nname = "httpx"\n\n[[package]]\nname = "NAME"\n'


@pytest.mark.parametrize("spelling", ["curl-cffi", "Curl_CFFI"])
def test_lock_scan_catches_a_forbidden_package_in_any_spelling(spelling: str) -> None:
    violations = lock_violations(LOCK_TEMPLATE.replace("NAME", spelling))

    assert violations == [f"curl-cffi — {FORBIDDEN_DISTRIBUTIONS['curl-cffi']} {RULE}"]


# Her bildirim yeri ayrı sınanır: biri okunmazsa yasak gereksinim oradan sessizce girer.
PYPROJECT_SECTIONS = {
    "dependencies": "[project]\ndependencies = [REQ]\n",
    "optional-dependencies": "[project.optional-dependencies]\nkazi = [REQ]\n",
    # PEP 735 `include-group` tablosu gereksinim değildir; ayrıştırıcı onda düşmemeli.
    "dependency-groups": '[dependency-groups]\ng = ["ruff"]\ndev = [REQ, {include-group = "g"}]\n',
}


@pytest.mark.parametrize("section", list(PYPROJECT_SECTIONS))
@pytest.mark.parametrize("requirement", ["scrapling[fetchers]", "cloudscraper>=1"])
def test_pyproject_scan_catches_forbidden_requirements(section: str, requirement: str) -> None:
    text = PYPROJECT_SECTIONS[section].replace("REQ", f'"{requirement}"')

    assert pyproject_violations(text), f"{section} içindeki {requirement!r} yakalanmadı"


@pytest.mark.parametrize("section", list(PYPROJECT_SECTIONS))
def test_pyproject_scan_allows_the_bare_scrapling_parser(section: str) -> None:
    text = PYPROJECT_SECTIONS[section].replace("REQ", '"scrapling>=0.4"')

    assert pyproject_violations(text) == []


FORBIDDEN_INSTALLS = [
    "pip install camoufox",
    'uv pip install "scrapling[fetchers]"',
    "pip install Undetected-Chromedriver",
]
ALLOWED_INSTALLS = [
    "# camoufox yasak",
    "    # pip install camoufox",
    "uv pip install scrapling playwright",
]


@pytest.mark.parametrize("line", FORBIDDEN_INSTALLS)
def test_install_scan_catches_forbidden_installs(line: str) -> None:
    violations = install_violations(f"set -e\n{line}\n", "ornek.sh")

    assert [violation.split(": ", 1)[0] for violation in violations] == ["ornek.sh:2"]


@pytest.mark.parametrize("line", ALLOWED_INSTALLS)
def test_install_scan_skips_comments_and_allowed_tools(line: str) -> None:
    assert install_violations(f"set -e\n{line}\n", "ornek.sh") == []


# ── Koruma 2 ve 3: tarama boş kümeye kayıp boşa yeşil kalmasın ────────────────


def test_python_scan_reaches_the_known_sources() -> None:
    """Kök kayar ya da özyineleme düşerse A hiçbir şeyi taramadan yeşil kalırdı."""
    scanned = {_rel(path) for path in _python_files()}
    expected = {
        "src/football_edge/fetch.py",
        "src/football_edge/collectors/tff.py",
        "scripts/ops_alert.py",
    }

    assert expected <= scanned, f"A ekseni bunları taramıyor: {sorted(expected - scanned)}"


def test_install_scan_reaches_the_known_files() -> None:
    scanned = {_rel(path) for path in _install_files()}
    expected = {".github/workflows/ci.yml", "scripts/check_secrets.sh", "verify.sh"}

    assert expected <= scanned, f"C ekseni bunları taramıyor: {sorted(expected - scanned)}"


def test_lock_parser_reads_the_real_lock() -> None:
    """Ayrıştırma bozulup boş küme dönerse kilit testi boşa yeşil kalırdı."""
    names = lock_package_names(LOCK.read_text(encoding="utf-8"))
    expected = {"httpx", "protego", "psycopg"}

    assert expected <= names, f"uv.lock'tan okunamayan paketler: {sorted(expected - names)}"


# ── Depo: üç eksen ─────────────────────────────────────────────────────────────


def test_python_sources_use_no_forbidden_tool() -> None:
    violations = _scan(_python_files(), python_violations)

    assert not violations, "yasak erişim aracı kodda:\n" + "\n".join(violations)


def test_lock_holds_no_forbidden_distribution() -> None:
    violations = lock_violations(LOCK.read_text(encoding="utf-8"))

    assert not violations, "uv.lock yasak dağıtım taşıyor:\n" + "\n".join(violations)


def test_pyproject_declares_no_forbidden_requirement() -> None:
    violations = pyproject_violations(PYPROJECT.read_text(encoding="utf-8"))

    assert not violations, "pyproject.toml yasak gereksinim bildiriyor:\n" + "\n".join(violations)


def test_workflows_and_scripts_install_no_forbidden_tool() -> None:
    violations = _scan(_install_files(), install_violations)

    assert not violations, "çalışma zamanında yasak kurulum:\n" + "\n".join(violations)
