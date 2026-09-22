"""Erişim yöntemi kuralı (spec §3.2.1, R77) prose'da kalmaz: yasak araçlar koda giremez.

Sayfayı okumak serbest; kaynağın engelini ya da kimlik denetimini aşmak yasak. Parmak izini
gizleyen/taklit eden, bot kontrolünü ya da CAPTCHA'yı aşan, User-Agent'ı ya da IP'yi döndüren
araçlar üç eksende aranır: A) `src/` ve `scripts/` Python kaynağı onları import etmez, adlarını
dize olarak da taşımaz (AST); B) `uv.lock` ve `pyproject.toml` onları bildirmez; C) iş akışları,
action'lar, kabuk betikleri ve kökteki `requirements*.txt` onları kurmaz.

`FORBIDDEN` tablosu spec'teki "ve benzerleri"nin TAMAMI DEĞİLDİR; otorite spec'tir — tabloda
olmayan bir araç izinli değil, yalnız bu testin görmediği bir araçtır. Kuralın davranış tarafı
(403/429'da kimlik ya da yol değiştirip yeniden denemek) burada ölçülmez.

YASAK DEĞİL: `playwright`, `selenium`, `httpx`, `requests`, taban `scrapling` — dürüst kimlikli
başsız tarayıcı ve ayrıştırıcı (`scrapling.parser`, `Selector`) §3.2.1'de izinli. Scrapling'in
fetcher tarafı ise BÜTÜNÜYLE yasak (R80): `scrapling.fetchers`, `scrapling.engines`,
`scrapling.fetchers.__all__`deki on ad (fetcher'ların hepsi varsayılan olarak tarayıcı kimliği
taklit eder; `ProxyRotator` proxy döndürür) ve onları çeken her ekstra (`scrapling[...]`).

Bilinen sınırlar: dize kuralı yalnız yasak adı TAM taşıyan sabiti yakalar — literal alt süreç
kurulumu (`[..., "pip", "install", "camoufox"]`) ve `import_module(name="camoufox")` artık
yakalanıyor. Hesaplanmış dizeler (`"cam" + "oufox"`), ek taşıyan dizeler (`"camoufox==0.4"`,
`"pip install camoufox"`) ve `exec`/`eval` görünmez; böyle bir çalışma zamanı kurulumu kilide
de girmez, yani B de onu görmez.
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


def normalise(name: str) -> str:
    """PEP 503: küçük harf, `-`/`_`/`.` dizileri tek `-`."""
    return re.sub(r"[-_.]+", "-", name).lower()


# (dağıtım adı, import kökü, neden) — dağıtım, modül ve ad listeleri YALNIZ buradan türer.
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
    ("2captcha-python", "twocaptcha", "CAPTCHA çözme hizmeti istemcisi"),
    ("anticaptchaofficial", "anticaptchaofficial", "CAPTCHA çözme hizmeti istemcisi"),
    ("capsolver", "capsolver", "CAPTCHA çözme hizmeti istemcisi"),
    ("requests-ip-rotator", "requests_ip_rotator", "bulut ağ geçitleri üzerinden IP döndürme"),
)
# Tablo satırı hangi yazımla girilmiş olursa olsun kilitteki (normalize) adla eşleşsin.
FORBIDDEN_DISTRIBUTIONS = {normalise(dist): reason for dist, _, reason in FORBIDDEN}
FORBIDDEN_MODULES = {module: reason for _, module, reason in FORBIDDEN}
# C ekseni ve A'nın dize kuralı: dağıtım adı ve import kökü, ikisi de normalize.
NAME_REASONS = {normalise(name): why for dist, module, why in FORBIDDEN for name in (dist, module)}

STEALTH_REASON = "Scrapling'in tarayıcı parmak izini gizleyen fetcher'ı (spec §3.2.1 adıyla)"
FETCHER_REASON = "varsayılan olarak tarayıcı kimliği taklit eder (0c ölçümü, R80)"
PROXY_REASON = "IP/proxy döndürme (spec §3.2.1)"
STAR_REASON = "`*` getirdiği adları gizler; fetcher'lar bu yoldan girebilir (R80)"
# R80 (0c ölçümü, kurulu scrapling 0.4.15): bütün fetcher'lar varsayılan olarak tarayıcı kimliği
# taklit eder, ProxyRotator taban paketle çalışır. Ayrıştırıcı (`scrapling.parser`) serbest.
SCRAPLING_MODULES = dict.fromkeys(("scrapling.fetchers", "scrapling.engines"), FETCHER_REASON)
SCRAPLING_NAMES = {  # `scrapling.fetchers.__all__`in tamamı
    **dict.fromkeys(("StealthyFetcher", "StealthySession", "AsyncStealthySession"), STEALTH_REASON),
    **dict.fromkeys(("Fetcher", "AsyncFetcher", "FetcherSession"), FETCHER_REASON),
    **dict.fromkeys(("DynamicFetcher", "DynamicSession", "AsyncDynamicSession"), FETCHER_REASON),
    "ProxyRotator": PROXY_REASON,
}
# PyPI scrapling 0.4.15: her ekstra (`ai`/`shell`/`rag`/`all` dahil) `fetchers`ı çeker — curl_cffi,
# patchright, browserforge, …; taban paket yalnız ayrıştırıcıdır (lxml, cssselect, orjson, …).
SCRAPLING_EXTRAS_REASON = "Scrapling ekstrası parmak izi taklit eden fetcher'ları çeker"
MODULE_REASONS = {**FORBIDDEN_MODULES, **SCRAPLING_MODULES}
STRING_REASONS = {**NAME_REASONS, **{normalise(m): why for m, why in SCRAPLING_MODULES.items()}}
DYNAMIC_IMPORTS = frozenset({"import_module", "__import__"})
DOCSTRING_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)

PYTHON_ROOTS = ("src", "scripts")
# Kökten özyineleme YOK: worktree'ler (`.worktrees/`, başka dalların kopyaları) ve `.venv` kökün
# altında durur; yalnız bu çapaların altı yürünür.
INSTALL_GLOBS = (
    "scripts/**/*.sh",
    ".github/**/*.yml",
    ".github/**/*.yaml",
    "verify.sh",
    "requirements*.txt",
)

Finding = tuple[int, str, str]  # (satır, ne bulundu, neden)


# ── A. Python kaynağı (AST) ────────────────────────────────────────────────────


def python_violations(source: str, path: str) -> list[str]:
    """`source` metnindeki yasak import, erişim ve dizelerin HEPSİ, satır sırasıyla."""
    findings = sorted(_findings(ast.parse(source, filename=path)))
    return [f"{path}:{line}: {found} — {reason} {RULE}" for line, found, reason in findings]


def _findings(tree: ast.AST) -> Iterator[Finding]:
    quiet = _quiet_strings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from _import_findings(node)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            yield from _import_from_findings(node)
        elif isinstance(node, ast.Attribute) and node.attr in SCRAPLING_NAMES:
            yield node.lineno, f".{node.attr} erişimi", SCRAPLING_NAMES[node.attr]
        elif isinstance(node, ast.Call):
            yield from _call_findings(node)
        elif isinstance(node, ast.Constant) and id(node) not in quiet:
            yield from _string_findings(node)


def _module_reason(module: str) -> str | None:
    """`a.b.c` için `a`, `a.b`, `a.b.c` sorulur: yasak bir yolun alt modülleri de yasak."""
    parts = module.split(".")
    prefixes = (".".join(parts[:end]) for end in range(1, len(parts) + 1))
    return next((MODULE_REASONS[prefix] for prefix in prefixes if prefix in MODULE_REASONS), None)


def _import_findings(node: ast.Import) -> Iterator[Finding]:
    for alias in node.names:
        reason = _module_reason(alias.name)
        if reason:
            yield node.lineno, f"import {alias.name}", reason


def _import_from_findings(node: ast.ImportFrom) -> Iterator[Finding]:
    module = node.module or ""
    for alias in node.names:
        reason = _from_import_reason(module, alias.name)
        if reason:
            yield node.lineno, f"from {module} import {alias.name}", reason


def _from_import_reason(module: str, name: str) -> str | None:
    """En özel neden kazanır: Scrapling adı ya da `*`, sonra modül yolu, sonra alt modül adı."""
    if module.split(".")[0] == "scrapling" and (name in SCRAPLING_NAMES or name == "*"):
        return SCRAPLING_NAMES.get(name, STAR_REASON)
    return _module_reason(module) or _module_reason(f"{module}.{name}")


def _call_findings(node: ast.Call) -> Iterator[Finding]:
    callee = _callee(node.func)
    if callee in DYNAMIC_IMPORTS:
        module = _string_arg(node, 0) or ""
        reason = _module_reason(module)
        if reason:
            yield node.lineno, f"{callee}({module!r})", reason
    elif callee == "getattr":
        name = _string_arg(node, 1)
        if name in SCRAPLING_NAMES:
            yield node.lineno, f"getattr(..., {name!r})", SCRAPLING_NAMES[name]


def _string_findings(node: ast.Constant) -> Iterator[Finding]:
    """Adı TAM taşıyan dize: `[..., "pip", "install", "camoufox"]`, `import_module(name=...)`."""
    reason = STRING_REASONS.get(normalise(node.value)) if isinstance(node.value, str) else None
    if reason:
        yield node.lineno, f"{node.value!r} dizesi", reason


def _quiet_strings(tree: ast.AST) -> set[int]:
    """Dize kuralının atladığı sabitler: docstring (anma sayılır) ve biçim 5'in zaten raporladığı
    dinamik import argümanı (aynı ihlal iki kez yazılmasın)."""
    quiet = set()
    for node in ast.walk(tree):
        if isinstance(node, DOCSTRING_OWNERS) and node.body and isinstance(node.body[0], ast.Expr):
            quiet.add(id(node.body[0].value))
        elif isinstance(node, ast.Call) and _callee(node.func) in DYNAMIC_IMPORTS and node.args:
            quiet.add(id(node.args[0]))
    return quiet


def _callee(func: ast.expr) -> str | None:
    """`f(...)` ve `x.f(...)` için `f`: `importlib.import_module` da yakalanır."""
    if isinstance(func, ast.Name):
        return func.id
    return func.attr if isinstance(func, ast.Attribute) else None


def _string_arg(node: ast.Call, index: int) -> str | None:
    arg = node.args[index] if index < len(node.args) else None
    return arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None


# ── B. Bağımlılık bildirimi (kilit ve pyproject) ───────────────────────────────


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
        # uv'nin eski alanı: uv buradan hâlâ kurar.
        document.get("tool", {}).get("uv", {}).get("dev-dependencies", []),
    ]
    # PEP 735 `{include-group = ...}` bir gereksinim değil, başka bir grubun adıdır.
    return [item for group in groups for item in group if isinstance(item, str)]


# PEP 508: ad; ekstra `[`, sürüm işleci, işaret `;`, URL `@` ya da eski biçim `(` ile biter.
_NAME_END = re.compile(r"[\[<>=!~;@(\s]")


def _requirement_reason(requirement: str) -> str | None:
    """Ad: ilk `[ < > = ! ~ ; @ (` ya da boşluktan önceki kısım, normalize."""
    head = requirement.strip()
    raw_name = _NAME_END.split(head, maxsplit=1)[0]
    name = normalise(raw_name)
    if name == "scrapling" and head[len(raw_name) :].lstrip().startswith("["):
        return SCRAPLING_EXTRAS_REASON
    return FORBIDDEN_DISTRIBUTIONS.get(name)


# ── C. Çalışma zamanında kurulum (iş akışları, betikler, requirements) ────────


def _name_pattern(name: str) -> str:
    """`curl-cffi` → `curl[-_.]+cffi`: pip `-`, `_`, `.` dizilerini aynı sayar."""
    return "[-_.]+".join(map(re.escape, name.split("-")))


_INSTALL_PATTERN = re.compile(
    r"\b(?P<name>" + "|".join(map(_name_pattern, NAME_REASONS)) + r")\b|(?P<extras>scrapling\s*\[)",
    re.IGNORECASE,
)


def install_violations(text: str, path: str) -> list[str]:
    violations = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = None if line.lstrip().startswith("#") else _INSTALL_PATTERN.search(line)
        if match:
            violations.append(f"{path}:{number}: {line.strip()} — {_install_reason(match)} {RULE}")
    return violations


def _install_reason(match: re.Match[str]) -> str:
    return SCRAPLING_EXTRAS_REASON if match["extras"] else NAME_REASONS[normalise(match["name"])]


def _python_files(root: Path) -> list[Path]:
    return sorted(path for sub in PYTHON_ROOTS for path in (root / sub).rglob("*.py"))


def _install_files(root: Path) -> list[Path]:
    return sorted(path for pattern in INSTALL_GLOBS for path in root.glob(pattern))


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _scan(
    root: Path, files: Callable[[Path], list[Path]], scan: Callable[[str, str], list[str]]
) -> list[str]:
    """`files`in kökte bulduğu her dosyayı METİN olarak `scan`e verir; yollar köke göreli."""
    return [
        found
        for path in files(root)
        for found in scan(path.read_text(encoding="utf-8"), _rel(path, root))
    ]


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
    # R80: fetcher tarafının tamamı — modül yolları, `__all__` adları, ProxyRotator.
    "import scrapling.fetchers",
    "from scrapling import fetchers",
    "from scrapling import Fetcher",
    "from scrapling.fetchers import DynamicFetcher",
    "from scrapling.fetchers import ProxyRotator",
    "from scrapling.engines.toolbelt import ProxyRotator",
    'importlib.import_module("scrapling.fetchers")',
    "rotator = toolbelt.ProxyRotator(proxies)",
    'getattr(scrapling, "DynamicFetcher")',
    # R81: CAPTCHA çözme ve IP döndürme.
    "from twocaptcha import TwoCaptcha",
    "import anticaptchaofficial",
    "import capsolver",
    "from requests_ip_rotator import ApiGateway",
    # Dize kuralı: import deyimi olmadan kurulum ve yükleme.
    'subprocess.run([sys.executable, "-m", "pip", "install", "camoufox"])',
    'importlib.import_module(name="camoufox")',
]
ALLOWED_PYTHON = [
    "import httpx",
    "import scrapling",
    "from scrapling.parser import Selector",
    "from scrapling import Selector",
    "import playwright.sync_api",
    "from protego import Protego",
    "stealthy = True",
    '"""camoufox bu projede kullanılmaz."""',
    'def kur():\n    """camoufox"""\n',
    'log.info("camoufox bu projede yasak")',
    "from . import camoufox",
    "from .camoufox import yardimci",
]


@pytest.mark.parametrize("snippet", FORBIDDEN_PYTHON)
def test_python_scan_catches_every_forbidden_form_once(snippet: str) -> None:
    violations = python_violations(snippet, "ornek.py")

    assert len(violations) == 1, f"tek ihlal bekleniyordu: {snippet!r} → {violations}"


@pytest.mark.parametrize("snippet", ALLOWED_PYTHON)
def test_python_scan_allows_honest_tools_and_mere_mentions(snippet: str) -> None:
    assert python_violations(snippet, "ornek.py") == []


def test_python_scan_reports_every_violation_with_path_and_line() -> None:
    """İlk ihlalde durmaz; her biri `<yol>:<satır>: <bulgu> — <neden> (spec §3.2.1, R77)`."""
    source = "import httpx\nimport camoufox\nfrom scrapling import StealthyFetcher\n"

    assert python_violations(source, "ornek.py") == [
        f"ornek.py:2: import camoufox — {FORBIDDEN_MODULES['camoufox']} {RULE}",
        f"ornek.py:3: from scrapling import StealthyFetcher — {STEALTH_REASON} {RULE}",
    ]


@pytest.mark.parametrize(
    ("snippet", "reason"),
    [
        ("from scrapling import StealthyFetcher", STEALTH_REASON),
        ("from scrapling.fetchers import ProxyRotator", PROXY_REASON),
        ("from scrapling import Fetcher", FETCHER_REASON),
        ("import scrapling.engines", FETCHER_REASON),
    ],
)
def test_python_scan_gives_each_scrapling_name_its_own_reason(snippet: str, reason: str) -> None:
    assert python_violations(snippet, "ornek.py") == [f"ornek.py:1: {snippet} — {reason} {RULE}"]


LOCK_TEMPLATE = 'version = 1\n\n[[package]]\nname = "httpx"\n\n[[package]]\nname = "NAME"\n'


@pytest.mark.parametrize("spelling", ["curl-cffi", "Curl_CFFI"])
def test_lock_scan_catches_a_forbidden_package_in_any_spelling(spelling: str) -> None:
    violations = lock_violations(LOCK_TEMPLATE.replace("NAME", spelling))

    assert violations == [f"curl-cffi — {FORBIDDEN_DISTRIBUTIONS['curl-cffi']} {RULE}"]


@pytest.mark.parametrize("distribution", [distribution for distribution, _, _ in FORBIDDEN])
def test_lock_scan_catches_every_table_row_as_uv_writes_it(distribution: str) -> None:
    """uv kilide normalize ad yazar; satır tabloya hangi yazımla girilmiş olursa olsun eşleşmeli."""
    written = normalise(distribution)

    assert len(lock_violations(LOCK_TEMPLATE.replace("NAME", written))) == 1, written


# Her bildirim yeri ayrı sınanır: biri okunmazsa yasak gereksinim oradan sessizce girer.
PYPROJECT_SECTIONS = {
    "dependencies": "[project]\ndependencies = [REQ]\n",
    "optional-dependencies": "[project.optional-dependencies]\nkazi = [REQ]\n",
    # PEP 735 `include-group` tablosu gereksinim değildir; ayrıştırıcı onda düşmemeli.
    "dependency-groups": '[dependency-groups]\ng = ["ruff"]\ndev = [REQ, {include-group = "g"}]\n',
    # uv'nin eski alanı: uv buradan hâlâ kurar.
    "tool.uv": "[tool.uv]\ndev-dependencies = [REQ]\n",
}
PYPROJECT_FORBIDDEN = [
    "scrapling[fetchers]",
    "cloudscraper>=1",
    "camoufox@ https://örnek.invalid/x.whl",
    "camoufox(>=0.4)",
]


@pytest.mark.parametrize("section", list(PYPROJECT_SECTIONS))
@pytest.mark.parametrize("requirement", PYPROJECT_FORBIDDEN)
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
    # İmport kökü yazımı: curl_cffi'nin kendi belgelediği kurulum komutu.
    "pip install curl_cffi --upgrade",
    # Normalizasyondan sonra da dağıtımından ayrı kalan tek import kökü (2captcha-python).
    'python -c "from twocaptcha import TwoCaptcha"',
    # pip `-`, `_`, `.` dizilerini aynı sayar; ekstra köşeli parantezinden önce boşluk olabilir.
    "pip install curl.cffi",
    'uv pip install "scrapling [fetchers]"',
    "pip install 2captcha-python",
    "pip install requests-ip-rotator",
]
ALLOWED_INSTALLS = [
    "# camoufox yasak",
    "    # pip install camoufox",
    "uv pip install scrapling playwright",
    # Kelime sınırı: yasak ad daha uzun bir adın parçasıysa o araç değildir.
    "uv pip install camoufoxish",
    "uv pip install mycamoufox",
]


@pytest.mark.parametrize("line", FORBIDDEN_INSTALLS)
def test_install_scan_catches_forbidden_installs(line: str) -> None:
    violations = install_violations(f"set -e\n{line}\n", "ornek.sh")

    assert [violation.split(": ", 1)[0] for violation in violations] == ["ornek.sh:2"]


@pytest.mark.parametrize("line", ALLOWED_INSTALLS)
def test_install_scan_skips_comments_and_allowed_tools(line: str) -> None:
    assert install_violations(f"set -e\n{line}\n", "ornek.sh") == []


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ("pip install Undetected-Chromedriver", FORBIDDEN_DISTRIBUTIONS["undetected-chromedriver"]),
        ('uv pip install "scrapling [fetchers]"', SCRAPLING_EXTRAS_REASON),
    ],
)
def test_install_scan_gives_the_matched_tool_its_own_reason(line: str, reason: str) -> None:
    assert install_violations(f"{line}\n", "ornek.sh") == [f"ornek.sh:1: {line} — {reason} {RULE}"]


@pytest.mark.parametrize(
    "name", sorted({name for dist, root, _ in FORBIDDEN for name in (dist, root)})
)
def test_install_scan_catches_every_table_name_in_both_spellings(name: str) -> None:
    assert install_violations(f"pip install {name}\n", "ornek.sh"), f"{name!r} yakalanmadı"


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_python_tree_scan_reads_every_file_it_reaches(tmp_path: Path) -> None:
    """Dosyaya "ulaşmak" yetmez: okunduğu ve bulgunun köke göreli yol ve satırla geldiği ölçülür."""
    _write(tmp_path, "src/paket/temiz.py", "import httpx\n")
    _write(tmp_path, "src/paket/alt/kirli.py", "import httpx\nimport camoufox\n")

    assert _scan(tmp_path, _python_files, python_violations) == [
        f"src/paket/alt/kirli.py:2: import camoufox — {FORBIDDEN_MODULES['camoufox']} {RULE}"
    ]


def test_install_tree_scan_walks_nested_files_but_no_hidden_directory(tmp_path: Path) -> None:
    """Worktree'ler depo kökünün altında durur: kökten özyineleme başka dalları da tarardı."""
    reached = ("scripts/ops/kur.sh", ".github/actions/kur/action.yml", "requirements-scrape.txt")
    hidden = (".worktrees/wt/scripts/kur.sh", ".worktrees/wt/.github/ci.yml", ".venv/x/kur.sh")
    for relative in reached + hidden:
        _write(tmp_path, relative, "pip install cloudscraper\n")

    violations = _scan(tmp_path, _install_files, install_violations)

    assert {violation.split(":", 1)[0] for violation in violations} == set(reached)


# ── Koruma 2 ve 3: tarama boş kümeye kayıp boşa yeşil kalmasın ────────────────


def test_python_scan_reaches_the_known_sources() -> None:
    """Kök kayar ya da özyineleme düşerse A hiçbir şeyi taramadan yeşil kalırdı."""
    scanned = {_rel(path, REPO) for path in _python_files(REPO)}
    expected = {
        "src/football_edge/fetch.py",
        "src/football_edge/collectors/tff.py",
        "scripts/ops_alert.py",
    }

    assert expected <= scanned, f"A ekseni bunları taramıyor: {sorted(expected - scanned)}"


def test_install_scan_reaches_the_known_files() -> None:
    scanned = {_rel(path, REPO) for path in _install_files(REPO)}
    expected = {".github/workflows/ci.yml", "scripts/check_secrets.sh", "verify.sh"}

    assert expected <= scanned, f"C ekseni bunları taramıyor: {sorted(expected - scanned)}"


def test_lock_parser_reads_the_real_lock() -> None:
    """Ayrıştırma bozulup boş küme dönerse kilit testi boşa yeşil kalırdı."""
    names = lock_package_names(LOCK.read_text(encoding="utf-8"))
    expected = {"httpx", "protego", "psycopg"}

    assert expected <= names, f"uv.lock'tan okunamayan paketler: {sorted(expected - names)}"


# ── Depo: üç eksen ─────────────────────────────────────────────────────────────


def test_python_sources_use_no_forbidden_tool() -> None:
    violations = _scan(REPO, _python_files, python_violations)

    assert not violations, "yasak erişim aracı kodda:\n" + "\n".join(violations)


def test_lock_holds_no_forbidden_distribution() -> None:
    violations = lock_violations(LOCK.read_text(encoding="utf-8"))

    assert not violations, "uv.lock yasak dağıtım taşıyor:\n" + "\n".join(violations)


def test_pyproject_declares_no_forbidden_requirement() -> None:
    violations = pyproject_violations(PYPROJECT.read_text(encoding="utf-8"))

    assert not violations, "pyproject.toml yasak gereksinim bildiriyor:\n" + "\n".join(violations)


def test_workflows_and_scripts_install_no_forbidden_tool() -> None:
    violations = _scan(REPO, _install_files, install_violations)

    assert not violations, "çalışma zamanında yasak kurulum:\n" + "\n".join(violations)
