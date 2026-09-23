"""Erişim yöntemi kuralı (spec §3.2.1, R77 → R77b) prose'da kalmaz: sınırlar koda girer.

R77b (2026-09-23, kullanıcı kararı): Scrapling tam kullanılır ve tarayıcı parmak izi / TLS taklidi
artık yasak DEĞİL. Değişmeyen sınırlar kalır: bot doğrulaması ya da CAPTCHA çözülmez, adı verilmiş
bir bot taklit edilmez (R2), proxy/IP döndürülmez; robots, crawl-delay, `Retry-After` ve 403/429'a
uyulur. Bu test o sınırların koddan okunabilen kısmını ölçer.

SERBEST (R77b): Scrapling `Fetcher`/`DynamicFetcher`/`StealthyFetcher` ve oturumları,
`scrapling.fetchers`/`scrapling.engines`, `scrapling[fetchers]` ekstrası ve `FREED` tablosundaki
parmak izi / tarayıcı taklidi araçları (`curl_cffi`, `camoufox`, `patchright`, …). Taban `scrapling`
ayrıştırıcısı (`scrapling.parser`, `Selector`), `playwright`, `httpx`, `requests` zaten serbestti.

YASAK KALAN araçlar (`FORBIDDEN`: doğrulama çözücüler, Cloudflare atlatıcıları, `botasaurus`, IP ve
kimlik döndürücüler) üç eksende aranır: A) `src/` ve `scripts/` Python kaynağı onları import etmez,
adlarını dize olarak da taşımaz (AST); B) `uv.lock` ve `pyproject.toml` onları bildirmez; C) iş
akışları, action'lar, kabuk betikleri ve kökteki `requirements*.txt` onları kurmaz. Scrapling'in
`fetchers` dışındaki ekstraları (`ai`, `shell`, `all`) B ve C'de kırmızı kalır: R77b yalnız
`fetchers`ı açtı; `ai`/`shell` MCP sunucusu ve kabuk getirir.

Scrapling komut satırı aracı (`scrapling`, `fetchers` ekstrasıyla gelir) fetcher'ları geçidin
dışında koşturur: C ekseni ve A'nın her dize sabiti `CLI_PATTERN`le taranır — `--solve-cloudflare`
(b), `--proxy`/`--proxies` (a) ve `scrapling extract|shell|mcp` (`python -m scrapling.cli …`
dahil) (d) kırmızı; A ayrıca `["scrapling", "extract", …]` argv listesini arar. `scrapling install`
(tarayıcı kurulumu) serbest.

A ekseninin R77b kuralları (AST, `src/` ve `scripts/`):
(a) proxy: `ProxyRotator` import/ad/öznitelik/`getattr` kullanımı, herhangi bir çağrıda
    `PROXY_KEYWORDS` anahtar argümanı ve bu adları TAM taşıyan dize (`opts["proxy"] = p`,
    `**{"proxy": p}`) — her dosyada, adaptör dahil;
(b) doğrulama çözme: `CHALLENGE_OPTIONS` (kurulu scrapling 0.4.15'in fetcher imzalarından
    ölçüldü: yalnız `solve_cloudflare`) anahtar argüman, parametre, ad, öznitelik ya da TAM dize
    olarak hiçbir değerle geçmez — `False` da;
(c) adı verilmiş bot: `useragent=`/`user_agent=` argümanları, `"User-Agent"` başlık anahtarlı
    sözlük ve atama (büyük/küçük harf duyarsız), adı UA olan değişken/öznitelik ataması
    (`USER_AGENT = …`, `self.useragent: str = …`, `DEFAULT_UA = …`) ve `config/sources.yaml`daki
    `user_agent` alanı `NAMED_BOTS` adlarından birini taşıyamaz. `config/robots/` anlık
    görüntüleri bot adı taşır: kapsam dışı;
(d) tek geçit: Scrapling fetcher tarafı (`GATED_MODULES`, `GATED_NAMES`) yalnız `ADAPTER`de
    serbest; başka her dosyada kırmızı. "Yalnız `sources.yaml` kaynağı", robots, crawl-delay,
    `Retry-After` ve 403/429 kuralları adaptörün davranış testlerinde tek yerde zorlanır. Adaptör
    dosyası yokken kural yeşil kalır — tarayacak dosya yoktur.

`FORBIDDEN` tablosu spec'teki "ve benzerleri"nin TAMAMI DEĞİLDİR; otorite spec'tir — tabloda
olmayan bir araç izinli değil, yalnız bu testin görmediği bir araçtır.

Bilinen sınırlar:
- Dize kuralı yalnız yasak adı TAM taşıyan sabiti yakalar: hesaplanmış dizeler
  (`"cloud" + "scraper"`), ek taşıyan dizeler (`"cloudscraper==1"`, `"pip install cloudscraper"`) ve
  `exec`/`eval` görünmez. Aynı sınıf: Python'da ekstra taşıyan kurulum dizesi
  (`subprocess.run(["pip", "install", "scrapling[ai]"])`) — B ve C onu görür, A görmez
  (DEFERRED 11a).
- (c) bot adı yalnız UA bağlamındaki SABİT dizelerde aranır: UA adı taşımayan bir değişkenden,
  `setdefault`la ya da `[("User-Agent", ...)]` demet listesiyle gelen UA görünmez. Bot listesi
  kapalıdır: `AdsBot-Google`, `Storebot-Google`, `Mediapartners-Google` gibi listede olmayan
  adlar yeşil kalır (spec "adı verilmiş bir bot" der; liste brief'in on iki adıdır).
- (a) ortam değişkeniyle proxy (`os.environ["HTTPS_PROXY"] = ...`, httpx `trust_env`) ölçülmez.
- (d) adaptörün bir fetcher'ı takma adla yeniden ihracı (`scrape.py`de
  `from scrapling.fetchers import StealthyFetcher as Browser`, başka modülde
  `from football_edge.scrape import Browser`) görünmez: ham fetcher geçidin dışında kullanılır.
  Adaptörün testleri, açık adlarının hiçbirinin Scrapling fetcher sınıfı olmadığını ölçmeli.
- (d) göreli dinamik import (`importlib.import_module(".fetchers", "scrapling")`) görünmez:
  `package` argümanı modül yoluna eklenmiyor.
- `config/sources.yaml`de yalnız `user_agent` alanı taranır: bir kaynağa eklenen `headers`
  (`User-Agent: Googlebot`) ya da `fetch_options` (`solve_cloudflare`, `proxy`) görünmez.
  `source_user_agents` kaynakları `id` ile sözlüğe koyar: yinelenen ya da eksik `id` önceki
  satırı gizler. İkisini de çalışma zamanında `sources.py` reddeder (bilinmeyen alan, yinelenen
  `id`); bu test o savunmaya dayanır.
- `FREED` araçlarının (ör. `curl_cffi`) adaptör dışında doğrudan kullanımı tek geçidi aşar; (d)
  yalnız Scrapling'i kapsar.
- Kuralın davranış tarafı (403/429'da kimlik ya da yol değiştirip yeniden denemek,
  `Retry-After`) burada değil adaptörün testlerinde ölçülür.
"""

from __future__ import annotations

import ast
import re
import tomllib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
LOCK = REPO / "uv.lock"
PYPROJECT = REPO / "pyproject.toml"
SOURCES = REPO / "config" / "sources.yaml"
RULE = "(spec §3.2.1, R77b)"
# (d) tek geçit: Scrapling fetcher tarafının serbest olduğu TEK dosya (Task 3 yazar).
ADAPTER = "src/football_edge/scrape.py"


def normalise(name: str) -> str:
    """PEP 503: küçük harf, `-`/`_`/`.` dizileri tek `-`."""
    return re.sub(r"[-_.]+", "-", name).lower()


# (dağıtım adı, import kökü, neden) — dağıtım, modül ve ad listeleri YALNIZ buradan türer.
# R77b'nin değişmeyen sınırları: doğrulama çözme, bot kontrolü atlatma, IP/kimlik döndürme.
FORBIDDEN: tuple[tuple[str, str, str], ...] = (
    ("cloudscraper", "cloudscraper", "Cloudflare bot kontrolünü atlatır"),
    ("cfscrape", "cfscrape", "Cloudflare bot kontrolünü atlatır"),
    ("fake-useragent", "fake_useragent", "User-Agent taklidi ve döndürme (R2)"),
    ("botasaurus", "botasaurus", "bot tespitini aşmak için kurulmuş çatı"),
    ("2captcha-python", "twocaptcha", "CAPTCHA çözme hizmeti istemcisi"),
    ("anticaptchaofficial", "anticaptchaofficial", "CAPTCHA çözme hizmeti istemcisi"),
    ("capsolver", "capsolver", "CAPTCHA çözme hizmeti istemcisi"),
    ("requests-ip-rotator", "requests_ip_rotator", "bulut ağ geçitleri üzerinden IP döndürme"),
)
# R77b ile serbest kalan parmak izi / tarayıcı taklidi araçları: (dağıtım adı, import kökü).
# Yalnız yeşil kanıt için tutulur; hiçbir eksen bunlara bakmaz.
FREED: tuple[tuple[str, str], ...] = (
    ("camoufox", "camoufox"),
    ("undetected-chromedriver", "undetected_chromedriver"),
    ("nodriver", "nodriver"),
    ("zendriver", "zendriver"),
    ("patchright", "patchright"),
    ("undetected-playwright", "undetected_playwright"),
    ("playwright-stealth", "playwright_stealth"),
    ("selenium-stealth", "selenium_stealth"),
    ("browserforge", "browserforge"),
    ("apify-fingerprint-datapoints", "apify_fingerprint_datapoints"),
    ("curl-cffi", "curl_cffi"),
    ("tls-client", "tls_client"),
)
# Tablo satırı hangi yazımla girilmiş olursa olsun kilitteki (normalize) adla eşleşsin.
FORBIDDEN_DISTRIBUTIONS = {normalise(dist): reason for dist, _, reason in FORBIDDEN}
FORBIDDEN_MODULES = {module: reason for _, module, reason in FORBIDDEN}
# C ekseni ve A'nın dize kuralı: dağıtım adı ve import kökü, ikisi de normalize.
NAME_REASONS = {normalise(name): why for dist, module, why in FORBIDDEN for name in (dist, module)}

GATE_REASON = (
    f"Scrapling fetcher tarafı yalnız {ADAPTER} içinde serbest "
    "(tek geçit: robots, crawl-delay, Retry-After, 403/429 orada zorlanır)"
)
STAR_REASON = "`*` getirdiği adları gizler; ProxyRotator ve fetcher'lar bu yoldan girebilir"
# Kurulu scrapling 0.4.15'te ölçüldü: bu yolların hepsi fetcher'lara ulaşır (DEFERRED 11c).
GATED_MODULES = frozenset(
    {
        "scrapling.fetchers",
        "scrapling.engines",
        "scrapling.spiders",
        "scrapling.core.ai",
        "scrapling.core.shell",
        "scrapling.cli",
    }
)
# `scrapling.fetchers.__all__`in ProxyRotator dışındaki dokuzu; ProxyRotator (a)'da, her yerde.
GATED_NAMES = frozenset(
    {
        "Fetcher",
        "AsyncFetcher",
        "FetcherSession",
        "DynamicFetcher",
        "DynamicSession",
        "AsyncDynamicSession",
        "StealthyFetcher",
        "StealthySession",
        "AsyncStealthySession",
    }
)
# (a) Proxy: 0.4.15 imzalarında (`GetRequestParams`, `PlaywrightSession`, `StealthSession`, …)
# proxy'ye ait dört anahtar; httpx/requests'in `proxy`/`proxies`ı da aynı adla.
PROXY_REASON = "proxy/IP döndürme yasak (R77b sınır 4)"
PROXY_NAME = "ProxyRotator"
PROXY_KEYWORDS = frozenset({"proxy", "proxies", "proxy_auth", "proxy_rotator"})
# (b) Doğrulama çözme: 0.4.15'in bütün fetcher imzalarında bu amaçlı tek seçenek.
CHALLENGE_REASON = "bot doğrulaması/CAPTCHA çözülmez ya da atlatılmaz (R77b sınır 2)"
CHALLENGE_OPTIONS = frozenset({"solve_cloudflare"})
# (c) Adı verilmiş botlar ayrıcalıklı erişim alır: taklit edilmez (R2).
BOT_REASON = "adı verilmiş bot taklit edilmez (R2, R77b sınır 3)"
NAMED_BOTS = (
    "Googlebot",
    "bingbot",
    "ClaudeBot",
    "GPTBot",
    "CCBot",
    "anthropic-ai",
    "PerplexityBot",
    "Google-Extended",
    "Applebot",
    "YandexBot",
    "DuckDuckBot",
    "Baiduspider",
)
UA_KEYWORDS = frozenset({"useragent", "user_agent"})
UA_HEADER = "user-agent"
# Scrapling CLI'si (`fetchers` ekstrasıyla gelir): 0.4.15 `cli.py` `--proxy` ve
# `--solve-cloudflare` bayraklarını, `extract`/`shell`/`mcp` alt komutlarını taşır; `install`
# (tarayıcı kurulumu) serbest.
CLI_REASON = f"Scrapling komut satırı aracı fetcher'ları {ADAPTER} dışında koşturur (tek geçit)"
CLI_PATTERN = re.compile(
    r"(?P<challenge>--solve[-_]cloudflare\b)"
    r"|(?P<proxy>--prox(?:y|ies)\b)"
    r"|(?P<cli>\bscrapling(?:-mcp|\.cli)?\s+(?:extract|shell|mcp)\b)",
    re.IGNORECASE,
)
CLI_HEADS = frozenset({"scrapling", "scrapling-mcp", "scrapling.cli"})
CLI_SUBCOMMANDS = frozenset({"extract", "shell", "mcp"})

# Scrapling'in yalnız `fetchers` ekstrası serbest (R77b); `ai`/`shell`/`all` MCP sunucusu ve
# etkileşimli kabuk getirir. Taban paket yalnız ayrıştırıcıdır (lxml, cssselect, orjson, …).
ALLOWED_SCRAPLING_EXTRAS = frozenset({"fetchers"})
SCRAPLING_EXTRAS_REASON = "Scrapling'in yalnız `fetchers` ekstrası serbest (R77b)"
STRING_REASONS = NAME_REASONS
GATED_STRINGS = {normalise(module): GATE_REASON for module in GATED_MODULES}
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
    """`source` metnindeki yasak import, erişim, argüman ve dizelerin HEPSİ, satır sırasıyla.

    `path` tek geçidi belirler: Scrapling fetcher tarafı yalnız `ADAPTER`de serbesttir (d)."""
    tree = ast.parse(source, filename=path)
    findings = sorted(_findings(tree, gate_open=path == ADAPTER))
    return [f"{path}:{line}: {found} — {reason} {RULE}" for line, found, reason in findings]


def _findings(tree: ast.AST, gate_open: bool) -> Iterator[Finding]:
    quiet = _quiet_strings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from _import_findings(node, gate_open)
        elif isinstance(node, ast.ImportFrom):
            yield from _import_from_findings(node, gate_open)
        elif isinstance(node, ast.Call):
            yield from _call_findings(node, gate_open)
        elif isinstance(node, ast.keyword):
            yield from _keyword_findings(node)
        elif isinstance(node, ast.Constant) and id(node) not in quiet:
            yield from _string_findings(node, gate_open)
        elif isinstance(node, ast.List | ast.Tuple):
            yield from _cli_argv_findings(node)
        else:
            yield from _identifier_findings(node, gate_open)
        yield from _user_agent_findings(node)


def _identifier_reason(name: str, gate_open: bool) -> str | None:
    """Ad yasak mı: ProxyRotator (a), doğrulama seçeneği (b), adaptör dışında fetcher adı (d)."""
    if name == PROXY_NAME:
        return PROXY_REASON
    if name in CHALLENGE_OPTIONS:
        return CHALLENGE_REASON
    return GATE_REASON if not gate_open and name in GATED_NAMES else None


def _module_reason(module: str, gate_open: bool) -> str | None:
    """`a.b.c` için `a`, `a.b`, `a.b.c` sorulur: yasak bir yolun alt modülleri de yasak."""
    parts = module.split(".")
    for end in range(1, len(parts) + 1):
        prefix = ".".join(parts[:end])
        if prefix in FORBIDDEN_MODULES:
            return FORBIDDEN_MODULES[prefix]
        if not gate_open and prefix in GATED_MODULES:
            return GATE_REASON
    return None


def _import_findings(node: ast.Import, gate_open: bool) -> Iterator[Finding]:
    for alias in node.names:
        reason = _module_reason(alias.name, gate_open)
        if reason:
            yield node.lineno, f"import {alias.name}", reason


def _import_from_findings(node: ast.ImportFrom, gate_open: bool) -> Iterator[Finding]:
    """Göreli importta yalnız ad sorulur (`from .scrape import StealthyFetcher` geçidi aşmasın);
    modül yolu yalnız mutlak importta."""
    module = node.module or ""
    source = "." * node.level + module
    for alias in node.names:
        reason = _from_import_reason(module if node.level == 0 else None, alias.name, gate_open)
        if reason:
            yield node.lineno, f"from {source} import {alias.name}", reason


def _from_import_reason(module: str | None, name: str, gate_open: bool) -> str | None:
    """En özel neden kazanır: ad, sonra Scrapling'den `*`, sonra modül yolu, sonra alt modül adı."""
    named = _identifier_reason(name, gate_open)
    if named or module is None:
        return named
    if name == "*" and module.split(".")[0] == "scrapling":
        return STAR_REASON
    return _module_reason(module, gate_open) or _module_reason(f"{module}.{name}", gate_open)


def _call_findings(node: ast.Call, gate_open: bool) -> Iterator[Finding]:
    callee = _callee(node.func)
    if callee in DYNAMIC_IMPORTS:
        module = _string_arg(node, 0) or ""
        reason = _module_reason(module, gate_open)
        if reason:
            yield node.lineno, f"{callee}({module!r})", reason
    elif callee == "getattr":
        name = _string_arg(node, 1)
        # Doğrulama seçeneği burada sorulmaz: dize kuralı onu zaten bir kez raporlar.
        reason = None if name in CHALLENGE_OPTIONS else _identifier_reason(name or "", gate_open)
        if reason:
            yield node.lineno, f"getattr(..., {name!r})", reason


def _keyword_findings(node: ast.keyword) -> Iterator[Finding]:
    """(a) proxy anahtarları ve (b) doğrulama seçeneği, hangi değerle olursa olsun."""
    if node.arg in PROXY_KEYWORDS:
        yield node.lineno, f"{node.arg}= argümanı", PROXY_REASON
    elif node.arg in CHALLENGE_OPTIONS:
        yield node.lineno, f"{node.arg}= argümanı", CHALLENGE_REASON


def _identifier_findings(node: ast.AST, gate_open: bool) -> Iterator[Finding]:
    """Ad (`ProxyRotator(...)`), öznitelik (`x.StealthyFetcher`) ve parametre (`def f(solve_...)`).

    Fetcher adları yalnız öznitelikte aranır: çıplak ad zaten import satırında raporlandı."""
    if isinstance(node, ast.Attribute):
        name, found, gate = node.attr, f".{node.attr} erişimi", gate_open
    elif isinstance(node, ast.Name):
        name, found, gate = node.id, f"{node.id} adı", True
    elif isinstance(node, ast.arg):
        name, found, gate = node.arg, f"{node.arg} parametresi", True
    else:
        return
    reason = _identifier_reason(name, gate_open=gate)
    if reason:
        yield node.lineno, found, reason


def _string_findings(node: ast.Constant, gate_open: bool) -> Iterator[Finding]:
    """Adı TAM taşıyan dize: `[..., "pip", "install", "cloudscraper"]`, `{"solve_cloudflare": 0}`,
    `opts["proxy"]`; ve Scrapling CLI'sini çağıran dize (`"--solve-cloudflare"`, `"--proxy"`,
    `os.system("scrapling extract …")`). Scrapling fetcher yolu dizesi (`"scrapling.fetchers"`)
    yalnız adaptör dışında."""
    if not isinstance(node.value, str):
        return
    key = normalise(node.value)
    reason = STRING_REASONS.get(key) or (None if gate_open else GATED_STRINGS.get(key))
    if reason is None and node.value in CHALLENGE_OPTIONS:
        reason = CHALLENGE_REASON
    if reason is None and node.value in PROXY_KEYWORDS:
        reason = PROXY_REASON
    if reason is None:
        reason = cli_reason(node.value)
    if reason:
        yield node.lineno, f"{node.value!r} dizesi", reason


def cli_reason(text: str) -> str | None:
    """`text`teki ilk Scrapling CLI eşleşmesinin nedeni: bayrak kendi kuralıyla, alt komut (d)."""
    match = CLI_PATTERN.search(text)
    if match is None:
        return None
    if match["challenge"]:
        return CHALLENGE_REASON
    return PROXY_REASON if match["proxy"] else CLI_REASON


def _cli_argv_findings(node: ast.List | ast.Tuple) -> Iterator[Finding]:
    """`["scrapling", "extract", …]`, `[sys.executable, "-m", "scrapling.cli", "shell"]`."""
    words = [element.value if isinstance(element, ast.Constant) else None for element in node.elts]
    pairs = zip(words, words[1:], strict=False)
    if any(head in CLI_HEADS and command in CLI_SUBCOMMANDS for head, command in pairs):
        yield node.lineno, "Scrapling CLI argv listesi", CLI_REASON


def named_bot(text: str) -> str | None:
    """`text` adı verilmiş bir botu taşıyorsa onun adı (büyük/küçük harf duyarsız)."""
    lowered = text.lower()
    return next((bot for bot in NAMED_BOTS if bot.lower() in lowered), None)


def _user_agent_findings(node: ast.AST) -> Iterator[Finding]:
    """(c) UA bağlamındaki her SABİT dize: argüman, başlık sözlüğü, başlık ataması."""
    for value in _user_agent_values(node):
        for sub in ast.walk(value):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                bot = named_bot(sub.value)
                if bot:
                    yield sub.lineno, f"User-Agent'ta {bot}", BOT_REASON


def _user_agent_values(node: ast.AST) -> Iterator[ast.expr]:
    if isinstance(node, ast.keyword) and node.arg in UA_KEYWORDS:
        yield node.value
    elif isinstance(node, ast.Dict):
        pairs = zip(node.keys, node.values, strict=True)
        yield from (value for key, value in pairs if _is_ua_header(key))
    elif isinstance(node, ast.Assign | ast.AnnAssign) and node.value is not None:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(map(_is_ua_target, targets)):
            yield node.value


def _is_ua_target(target: ast.expr) -> bool:
    """`h["User-Agent"] = …`, `USER_AGENT = …`, `self.useragent = …`, `DEFAULT_UA = …`."""
    if isinstance(target, ast.Subscript):
        return _is_ua_header(target.slice)
    if isinstance(target, ast.Name):
        name = target.id
    elif isinstance(target, ast.Attribute):
        name = target.attr
    else:
        return False
    lowered = name.lower()
    return any(word in lowered for word in UA_KEYWORDS) or "ua" in lowered.split("_")


def _is_ua_header(node: ast.expr | None) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.lower() == UA_HEADER
    )


def _quiet_strings(tree: ast.AST) -> set[int]:
    """Dize kuralının atladığı sabitler: docstring (anma sayılır) ve dinamik import kuralının
    zaten raporladığı ilk argüman (aynı ihlal iki kez yazılmasın)."""
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


# ── A'. Kaynak kayıt defteri: `user_agent` alanı (c) ───────────────────────────


def source_user_agents(text: str) -> dict[str, str]:
    """Her kaynağın `user_agent`ı; `note` alanı ve robots anlık görüntüleri dışarıda."""
    sources = yaml.safe_load(text).get("sources", [])
    return {str(source.get("id")): str(source.get("user_agent", "")) for source in sources}


def sources_violations(text: str, path: str) -> list[str]:
    return [
        f"{path}: {source}: user_agent {agent!r} — {named_bot(agent)} — {BOT_REASON} {RULE}"
        for source, agent in source_user_agents(text).items()
        if named_bot(agent)
    ]


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
    rest = head[len(raw_name) :].lstrip()
    if name == "scrapling" and rest.startswith("["):
        return SCRAPLING_EXTRAS_REASON if _blocked_extras(rest[1:].split("]")[0]) else None
    return FORBIDDEN_DISTRIBUTIONS.get(name)


def _blocked_extras(extras: str) -> set[str]:
    """`fetchers, ai` → `{"ai"}`: `ALLOWED_SCRAPLING_EXTRAS` dışında kalan ekstralar."""
    named = {normalise(extra.strip()) for extra in extras.split(",") if extra.strip()}
    return named - ALLOWED_SCRAPLING_EXTRAS


# ── C. Çalışma zamanında kurulum ve Scrapling CLI (iş akışları, betikler, requirements) ──


def _name_pattern(name: str) -> str:
    """`requests-ip-rotator` → `requests[-_.]+ip[-_.]+rotator`: pip `-`, `_`, `.`yı aynı sayar."""
    return "[-_.]+".join(map(re.escape, name.split("-")))


_INSTALL_PATTERN = re.compile(
    r"\b(?P<name>"
    + "|".join(map(_name_pattern, NAME_REASONS))
    + r")\b|(?P<extras>scrapling\s*\[(?P<listed>[^\]]*)\]?)",
    re.IGNORECASE,
)


def install_violations(text: str, path: str) -> list[str]:
    violations = []
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue
        matches = _INSTALL_PATTERN.finditer(line)
        reason = next(filter(None, map(_install_reason, matches)), None) or cli_reason(line)
        if reason:
            violations.append(f"{path}:{number}: {line.strip()} — {reason} {RULE}")
    return violations


def _install_reason(match: re.Match[str]) -> str | None:
    if match["extras"] is None:
        return NAME_REASONS[normalise(match["name"])]
    return SCRAPLING_EXTRAS_REASON if _blocked_extras(match["listed"]) else None


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

FORBIDDEN_TOOL_PYTHON = [
    "import cloudscraper",
    "from cfscrape import create_scraper",
    "import botasaurus.browser",
    "from fake_useragent import UserAgent",
    "from twocaptcha import TwoCaptcha",
    "import anticaptchaofficial",
    "import capsolver",
    "from requests_ip_rotator import ApiGateway",
    'import_module("cloudscraper")',
    '__import__("fake_useragent")',
    # Dize kuralı: import deyimi olmadan kurulum ve yükleme.
    'subprocess.run([sys.executable, "-m", "pip", "install", "cloudscraper"])',
    'importlib.import_module(name="botasaurus")',
    # `*` her dosyada yasak: `scrapling.fetchers`inki ProxyRotator'ı da getirir.
    "from scrapling import *",
    "from scrapling.fetchers import *",
]
# (a) proxy — her dosyada, adaptör dahil.
PROXY_PYTHON = [
    "from scrapling.fetchers import ProxyRotator",
    "from scrapling.engines.toolbelt import ProxyRotator",
    "rotator = toolbelt.ProxyRotator(pool)",
    "rotator = ProxyRotator(pool)",
    'getattr(scrapling, "ProxyRotator")',
    'httpx.get(url, proxy="http://127.0.0.1:8080")',
    "client = httpx.Client(proxies=pool)",
    'page = session.fetch(url, proxy={"server": adres})',
    "page = session.get(url, proxy_auth=kimlik)",
    "page = session.get(url, proxy_rotator=rotator)",
    # Sonradan kurulan seçenek sözlüğü: anahtar TAM dize olarak (inceleme Important-1, m9).
    'opts["proxy"] = adres',
    'page = session.fetch(url, **{"proxies": havuz})',
]
# (b) doğrulama çözme — hangi değerle olursa olsun.
CHALLENGE_PYTHON = [
    "page = StealthyFetcher.fetch(url, solve_cloudflare=True)",
    "page = session.fetch(url, solve_cloudflare=False)",
    'secenekler = {"solve_cloudflare": False}',
    "def al(url, solve_cloudflare=False):\n    return url\n",
    "ayar.solve_cloudflare = False",
    "solve_cloudflare = True",
    'getattr(secenekler, "solve_cloudflare")',
]
# (c) adı verilmiş bot User-Agent'ta.
BOT_PYTHON = [
    'page = DynamicFetcher.fetch(url, useragent="Mozilla/5.0 (compatible; Googlebot/2.1)")',
    'kaynak = Source(user_agent="ClaudeBot/1.0")',
    'basliklar = {"User-Agent": "GPTBot"}',
    'basliklar = {"user-agent": "ccbot/2.0"}',
    'basliklar["USER-AGENT"] = f"x {surum} PerplexityBot"',
    'client = httpx.Client(headers={"User-Agent": "Mozilla/5.0 (compatible; bingbot/2.0)"})',
    'izin = parser.can_fetch(url=u, user_agent="Google-Extended")',
    # Adı UA olan sabit / öznitelik (inceleme Important-2, m6 ve m34).
    'USER_AGENT = "Mozilla/5.0 (compatible; Googlebot/2.1)"',
    'USER_AGENT: str = "Googlebot/2.1"',
    'self.useragent = "DuckDuckBot/1.1"',
    'DEFAULT_UA = "Baiduspider"',
]
# Scrapling CLI'si — her dosyada, adaptör dahil (inceleme Critical-1, m37).
CLI_PYTHON = [
    'subprocess.run(["scrapling", "extract", "get", url, "o.md"])',
    'argv = ("scrapling", "mcp")',
    'os.system("scrapling extract get https://ornek.invalid o.md")',
    'komut = f"scrapling shell {url}"',
    'secenek = "--solve-cloudflare"',
    'argv = ["--proxy", adres]',
]
# (d) tek geçit — adaptör DIŞINDA kırmızı, adaptörde yeşil.
GATED_PYTHON = [
    "import scrapling.fetchers",
    "import scrapling.engines.static",
    "from scrapling import fetchers",
    "from scrapling import Fetcher",
    "from scrapling import StealthyFetcher",
    "from scrapling.fetchers import DynamicFetcher",
    "from scrapling.fetchers import AsyncStealthySession as Session",
    "from scrapling.spiders import Spider",
    "from scrapling.core import shell",
    "import scrapling.core.ai",
    "import scrapling.cli",
    "from .scrape import StealthyFetcher",
    'importlib.import_module("scrapling.fetchers")',
    'yol = "scrapling.fetchers"',
    "fetcher = scrapling.StealthyFetcher()",
    'getattr(scrapling, "DynamicFetcher")',
]
EVERYWHERE_FORBIDDEN = (
    FORBIDDEN_TOOL_PYTHON + PROXY_PYTHON + CHALLENGE_PYTHON + BOT_PYTHON + CLI_PYTHON
)
FORBIDDEN_PYTHON = EVERYWHERE_FORBIDDEN + GATED_PYTHON
ALLOWED_PYTHON = [
    "import httpx",
    "import scrapling",
    "from scrapling.parser import Selector",
    "from scrapling import Selector",
    "from scrapling.core.custom_types import TextHandler",
    "import playwright.sync_api",
    "from protego import Protego",
    # R77b: parmak izi / tarayıcı taklidi serbest.
    "import camoufox",
    "from curl_cffi import requests",
    "import patchright.sync_api",
    "from browserforge.headers import HeaderGenerator",
    "import undetected_chromedriver as uc",
    "from playwright_stealth import stealth_sync",
    "import tls_client",
    'subprocess.run([sys.executable, "-m", "pip", "install", "camoufox"])',
    # Anma ve dürüst kullanım: kuralın adı ya da bot adı UA bağlamı dışında.
    "stealthy = True",
    '"""solve_cloudflare bu projede kapalı; Googlebot taklit edilmez."""',
    'log.info("solve_cloudflare kapalı")',
    'log.info("Googlebot bu projede taklit edilmez")',
    "proxy_adresi = None",
    'basliklar = {"User-Agent": source.user_agent}',
    'basliklar = {"User-Agent": "football-edge/0.1"}',
    'kaynak = Source(user_agent="football-edge/0.1 (+https://github.com/popiliadam/football-edge)")',
    "izin = parser.can_fetch(url=u, user_agent=source.user_agent)",
    'page = session.get(url, impersonate="chrome", stealthy_headers=True)',
    "page = session.fetch(url, google_search=True, real_chrome=True)",
    "from . import cloudscraper",
    "from .cloudscraper import yardimci",
    # `scrapling install` serbest (Task 3 tarayıcıyı kurar); UA adlı dürüst sabit serbest.
    'subprocess.run(["scrapling", "install"])',
    'log.info("proxy kullanılmaz")',
    'USER_AGENT = "football-edge/0.1"',
    'ua_surumu = "football-edge/0.1"',
]


@pytest.mark.parametrize("snippet", FORBIDDEN_PYTHON)
def test_python_scan_catches_every_forbidden_form_once(snippet: str) -> None:
    violations = python_violations(snippet, "ornek.py")

    assert len(violations) == 1, f"tek ihlal bekleniyordu: {snippet!r} → {violations}"


@pytest.mark.parametrize("snippet", ALLOWED_PYTHON)
def test_python_scan_allows_freed_tools_honest_use_and_mere_mentions(snippet: str) -> None:
    assert python_violations(snippet, "ornek.py") == []


@pytest.mark.parametrize("snippet", GATED_PYTHON)
def test_adapter_is_the_single_gate_for_scrapling_fetchers(snippet: str) -> None:
    """(d): adaptör dışında kırmızı olan her fetcher biçimi adaptörde yeşil."""
    assert python_violations(snippet, ADAPTER) == []


@pytest.mark.parametrize("snippet", EVERYWHERE_FORBIDDEN)
def test_adapter_still_obeys_every_other_rule(snippet: str) -> None:
    """Tek geçit fetcher'ı açar; proxy, doğrulama, bot ve yasak araç orada da kırmızı."""
    assert len(python_violations(snippet, ADAPTER)) == 1, snippet


def test_python_scan_reports_every_violation_with_path_and_line() -> None:
    """İlk ihlalde durmaz; her biri `<yol>:<satır>: <bulgu> — <neden> (spec §3.2.1, R77b)`."""
    source = (
        "import httpx\nimport cloudscraper\nfrom scrapling import StealthyFetcher\n"
        "page = StealthyFetcher.fetch(url, solve_cloudflare=False)\n"
    )

    assert python_violations(source, "ornek.py") == [
        f"ornek.py:2: import cloudscraper — {FORBIDDEN_MODULES['cloudscraper']} {RULE}",
        f"ornek.py:3: from scrapling import StealthyFetcher — {GATE_REASON} {RULE}",
        f"ornek.py:4: solve_cloudflare= argümanı — {CHALLENGE_REASON} {RULE}",
    ]


@pytest.mark.parametrize(
    ("snippet", "found", "reason"),
    [
        ("from scrapling import StealthyFetcher", None, GATE_REASON),
        ("from scrapling.fetchers import ProxyRotator", None, PROXY_REASON),
        ("from scrapling import *", None, STAR_REASON),
        ("import scrapling.engines", None, GATE_REASON),
        ("session.get(url, proxies=havuz)", "proxies= argümanı", PROXY_REASON),
        ("ayar.solve_cloudflare = False", ".solve_cloudflare erişimi", CHALLENGE_REASON),
        ('Source(user_agent="YandexBot/3.0")', "User-Agent'ta YandexBot", BOT_REASON),
    ],
)
def test_python_scan_gives_each_rule_its_own_reason(
    snippet: str, found: str | None, reason: str
) -> None:
    assert python_violations(snippet, "ornek.py") == [
        f"ornek.py:1: {found or snippet} — {reason} {RULE}"
    ]


@pytest.mark.parametrize("bot", NAMED_BOTS)
@pytest.mark.parametrize("case", [str.lower, str.upper])
def test_every_named_bot_is_caught_in_any_case(bot: str, case: Callable[[str], str]) -> None:
    snippet = f'basliklar = {{"User-Agent": "Mozilla/5.0 (compatible; {case(bot)}/1.0)"}}'

    assert len(python_violations(snippet, "ornek.py")) == 1, snippet


def test_freed_and_forbidden_tables_are_disjoint() -> None:
    """Bir araç hem serbest hem yasak olamaz: çelişen tablolar geçerli olanı gizler."""
    freed = {normalise(name) for dist, module in FREED for name in (dist, module)}

    assert not freed & set(NAME_REASONS), sorted(freed & set(NAME_REASONS))


# ── (c) sources.yaml ───────────────────────────────────────────────────────────

SOURCES_TEMPLATE = "sources:\n  - id: ornek\n    user_agent: AGENT\n    note: ClaudeBot anması\n"


@pytest.mark.parametrize("bot", NAMED_BOTS)
def test_sources_scan_catches_a_named_bot_in_user_agent(bot: str) -> None:
    text = SOURCES_TEMPLATE.replace("AGENT", f"Mozilla/5.0 (compatible; {bot.upper()})")

    assert len(sources_violations(text, "sources.yaml")) == 1, bot


@pytest.mark.parametrize("agent", ["football-edge/0.1", "Mozilla/5.0 (Macintosh) Chrome/131"])
def test_sources_scan_allows_honest_or_browser_agents_and_ignores_notes(agent: str) -> None:
    assert sources_violations(SOURCES_TEMPLATE.replace("AGENT", agent), "sources.yaml") == []


# ── B ve C: sınama ─────────────────────────────────────────────────────────────

LOCK_TEMPLATE = 'version = 1\n\n[[package]]\nname = "httpx"\n\n[[package]]\nname = "NAME"\n'


@pytest.mark.parametrize("spelling", ["requests-ip-rotator", "Requests_IP.Rotator"])
def test_lock_scan_catches_a_forbidden_package_in_any_spelling(spelling: str) -> None:
    violations = lock_violations(LOCK_TEMPLATE.replace("NAME", spelling))

    assert violations == [
        f"requests-ip-rotator — {FORBIDDEN_DISTRIBUTIONS['requests-ip-rotator']} {RULE}"
    ]


@pytest.mark.parametrize("distribution", [distribution for distribution, _, _ in FORBIDDEN])
def test_lock_scan_catches_every_table_row_as_uv_writes_it(distribution: str) -> None:
    """uv kilide normalize ad yazar; satır tabloya hangi yazımla girilmiş olursa olsun eşleşmeli."""
    written = normalise(distribution)

    assert len(lock_violations(LOCK_TEMPLATE.replace("NAME", written))) == 1, written


@pytest.mark.parametrize("distribution", [distribution for distribution, _ in FREED])
def test_lock_scan_allows_every_freed_distribution(distribution: str) -> None:
    assert lock_violations(LOCK_TEMPLATE.replace("NAME", normalise(distribution))) == []


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
    "scrapling[ai]",
    "scrapling[fetchers, shell]>=0.4",
    "cloudscraper>=1",
    "botasaurus@ https://örnek.invalid/x.whl",
    "capsolver(>=1)",
]
PYPROJECT_ALLOWED = [
    "scrapling>=0.4",
    "scrapling[fetchers]>=0.4.15",
    "scrapling [fetchers]",
    "curl-cffi>=0.7",
    "camoufox",
]


@pytest.mark.parametrize("section", list(PYPROJECT_SECTIONS))
@pytest.mark.parametrize("requirement", PYPROJECT_FORBIDDEN)
def test_pyproject_scan_catches_forbidden_requirements(section: str, requirement: str) -> None:
    text = PYPROJECT_SECTIONS[section].replace("REQ", f'"{requirement}"')

    assert pyproject_violations(text), f"{section} içindeki {requirement!r} yakalanmadı"


@pytest.mark.parametrize("section", list(PYPROJECT_SECTIONS))
@pytest.mark.parametrize("requirement", PYPROJECT_ALLOWED)
def test_pyproject_scan_allows_scrapling_fetchers_and_freed_tools(
    section: str, requirement: str
) -> None:
    text = PYPROJECT_SECTIONS[section].replace("REQ", f'"{requirement}"')

    assert pyproject_violations(text) == []


FORBIDDEN_INSTALLS = [
    "pip install cloudscraper",
    'uv pip install "scrapling[ai]"',
    'uv pip install "scrapling [fetchers,shell]"',
    # İmport kökü yazımı ve pip'in `-`/`_`/`.` eşdeğerliği.
    "pip install fake_useragent --upgrade",
    "pip install requests.ip.rotator",
    # Normalizasyondan sonra da dağıtımından ayrı kalan tek import kökü (2captcha-python).
    'python -c "from twocaptcha import TwoCaptcha"',
    "pip install 2captcha-python",
    # Serbest ekstra yasak bir aracı aynı satırda gizleyemez.
    'uv pip install "scrapling[fetchers]" capsolver',
    # Scrapling CLI'si (inceleme Critical-1, m36 ve m38).
    'scrapling extract stealthy-fetch "$URL" o.md --solve-cloudflare --proxy "$P"',
    "      - run: python -m scrapling.cli extract get $URL o.md --proxy $P",
    "uv run scrapling extract get $URL o.md",
    "scrapling shell",
    "curl --proxy http://127.0.0.1:1 $URL",
    "xvfb-run python kazi.py --solve_cloudflare",
]
ALLOWED_INSTALLS = [
    "# cloudscraper yasak",
    "    # pip install cloudscraper",
    "uv pip install scrapling playwright",
    'uv pip install "scrapling[fetchers]"',
    "pip install camoufox curl_cffi patchright",
    "uv run scrapling install",
    "scrapling install --force",
    # Kelime sınırı: yasak ad daha uzun bir adın parçasıysa o araç değildir.
    "uv pip install cloudscraperish",
    "uv pip install mycapsolver",
]


@pytest.mark.parametrize("line", FORBIDDEN_INSTALLS)
def test_install_scan_catches_forbidden_installs(line: str) -> None:
    violations = install_violations(f"set -e\n{line}\n", "ornek.sh")

    assert [violation.split(": ", 1)[0] for violation in violations] == ["ornek.sh:2"]


@pytest.mark.parametrize("line", ALLOWED_INSTALLS)
def test_install_scan_skips_comments_freed_tools_and_the_fetchers_extra(line: str) -> None:
    assert install_violations(f"set -e\n{line}\n", "ornek.sh") == []


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ("pip install Fake-UserAgent", FORBIDDEN_DISTRIBUTIONS["fake-useragent"]),
        ('uv pip install "scrapling [all]"', SCRAPLING_EXTRAS_REASON),
        ("scrapling extract get $URL o.md", CLI_REASON),
        ("curl --proxies http://p:1 $URL", PROXY_REASON),
        ("kazi --solve-cloudflare", CHALLENGE_REASON),
    ],
)
def test_install_scan_gives_the_matched_tool_its_own_reason(line: str, reason: str) -> None:
    assert install_violations(f"{line}\n", "ornek.sh") == [f"ornek.sh:1: {line} — {reason} {RULE}"]


@pytest.mark.parametrize(
    "name", sorted({name for dist, root, _ in FORBIDDEN for name in (dist, root)})
)
def test_install_scan_catches_every_table_name_in_both_spellings(name: str) -> None:
    assert install_violations(f"pip install {name}\n", "ornek.sh"), f"{name!r} yakalanmadı"


@pytest.mark.parametrize("name", sorted({name for dist, root in FREED for name in (dist, root)}))
def test_install_scan_allows_every_freed_name_in_both_spellings(name: str) -> None:
    assert install_violations(f"pip install {name}\n", "ornek.sh") == []


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_python_tree_scan_reads_every_file_it_reaches(tmp_path: Path) -> None:
    """Dosyaya "ulaşmak" yetmez: okunduğu ve bulgunun köke göreli yol ve satırla geldiği ölçülür."""
    _write(tmp_path, "src/paket/temiz.py", "import httpx\n")
    _write(tmp_path, "src/paket/alt/kirli.py", "import httpx\nimport cloudscraper\n")

    reason = FORBIDDEN_MODULES["cloudscraper"]

    assert _scan(tmp_path, _python_files, python_violations) == [
        f"src/paket/alt/kirli.py:2: import cloudscraper — {reason} {RULE}"
    ]


def test_python_tree_scan_opens_the_gate_only_at_the_adapter_path(tmp_path: Path) -> None:
    """(d) ağaç düzeyinde: aynı satır adaptörde yeşil, kardeş modülde kırmızı."""
    line = "from scrapling.fetchers import StealthyFetcher\n"
    _write(tmp_path, ADAPTER, line)
    _write(tmp_path, "src/football_edge/collectors/pfdk.py", line)

    assert _scan(tmp_path, _python_files, python_violations) == [
        f"src/football_edge/collectors/pfdk.py:1: {line.strip()} — {GATE_REASON} {RULE}"
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


def test_adapter_path_sits_where_the_scan_walks() -> None:
    """`ADAPTER` kayarsa (yazım hatası, taşınan paket) geçit hiçbir dosyada açılmaz ya da yanlış
    dosyada açılır. Dosyanın kendisi Task 3'e kadar yok; dizini ve tarama kökü ölçülür."""
    adapter = REPO / ADAPTER

    assert adapter.parent.is_dir(), f"adaptör dizini yok: {adapter.parent}"
    assert ADAPTER.split("/")[0] in PYTHON_ROOTS and adapter.suffix == ".py"
    assert not adapter.exists() or ADAPTER in {_rel(path, REPO) for path in _python_files(REPO)}


def test_install_scan_reaches_the_known_files() -> None:
    scanned = {_rel(path, REPO) for path in _install_files(REPO)}
    expected = {".github/workflows/ci.yml", "scripts/check_secrets.sh", "verify.sh"}

    assert expected <= scanned, f"C ekseni bunları taramıyor: {sorted(expected - scanned)}"


def test_lock_parser_reads_the_real_lock() -> None:
    """Ayrıştırma bozulup boş küme dönerse kilit testi boşa yeşil kalırdı."""
    names = lock_package_names(LOCK.read_text(encoding="utf-8"))
    expected = {"httpx", "protego", "psycopg"}

    assert expected <= names, f"uv.lock'tan okunamayan paketler: {sorted(expected - names)}"


def test_sources_parser_reads_every_real_user_agent() -> None:
    """Alan adı ya da yapı kayarsa boş sözlük döner ve (c) boşa yeşil kalırdı."""
    agents = source_user_agents(SOURCES.read_text(encoding="utf-8"))
    expected = {"footystats", "tff", "ajansspor", "googlenews"}

    assert expected <= set(agents), f"okunamayan kaynaklar: {sorted(expected - set(agents))}"
    assert all(agents.values()), f"user_agent alanı boş okunan kaynak: {agents}"


# ── Depo: üç eksen ve kayıt defteri ────────────────────────────────────────────


def test_python_sources_use_no_forbidden_tool() -> None:
    violations = _scan(REPO, _python_files, python_violations)

    assert not violations, "erişim yöntemi kuralı ihlali kodda:\n" + "\n".join(violations)


def test_sources_registry_names_no_bot_in_user_agent() -> None:
    violations = sources_violations(SOURCES.read_text(encoding="utf-8"), "config/sources.yaml")

    assert not violations, "sources.yaml adı verilmiş bot taşıyor:\n" + "\n".join(violations)


def test_lock_holds_no_forbidden_distribution() -> None:
    violations = lock_violations(LOCK.read_text(encoding="utf-8"))

    assert not violations, "uv.lock yasak dağıtım taşıyor:\n" + "\n".join(violations)


def test_pyproject_declares_no_forbidden_requirement() -> None:
    violations = pyproject_violations(PYPROJECT.read_text(encoding="utf-8"))

    assert not violations, "pyproject.toml yasak gereksinim bildiriyor:\n" + "\n".join(violations)


def test_workflows_and_scripts_install_no_forbidden_tool() -> None:
    violations = _scan(REPO, _install_files, install_violations)

    assert not violations, "çalışma zamanında yasak kurulum:\n" + "\n".join(violations)
