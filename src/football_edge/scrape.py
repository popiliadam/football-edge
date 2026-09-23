"""Scrapling toplayıcı adaptörü — Scrapling fetcher'larının TEK geçidi (spec §3.2.1, R77b).

R77b Scrapling'i tam açtı (`Fetcher`, `DynamicFetcher`, `StealthyFetcher`, `impersonate`,
`stealthy_headers`, Google yönlendiren `referer`). Değişmeyen sınırların davranış tarafı burada
zorlanır; `tests/test_access_method_rule.py` Scrapling fetcher importunu YALNIZ bu dosyada serbest
bırakır, yani başka bir modül bu kuralları atlayarak Scrapling'e ulaşamaz.

Sözleşme (her biri `tests/test_scrape.py`de mutasyonla kırmızı kanıtlı):

1. Kaynak yalnız `config/sources.yaml`dan gelir (`load_sources` çıktısıyla ALAN ALAN eşit olmalı —
   elle kurulmuş ya da değiştirilmiş bir `Source` reddedilir) ve `access_basis: robots` taşır.
2. Hedef URL'nin şeması+host'u+portu `base_url`inkiyle aynı, yolu (sorgu dahil) `declared_paths`te
   birebir olmalı (R7) — değilse HİÇBİR istek atılmaz (robots.txt bile).
3. robots.txt her turda CANLI okunur (`snapshot_from_status`: 200 politika, 404/410 "politika yok",
   başka her şey ölçülemedi → istek atılmaz). Her istekten önce iki eksen sorulur: kaynağın
   `user_agent` belirteci VE gerçekten gönderilen User-Agent (tarayıcı kimliği → çoğunlukla `*`
   grubu). Biri kapalıysa istek atılmaz.
4. Aynı kaynağa ardışık iki istek arasında `max(crawl_delay_seconds, robots Crawl-delay)` beklenir;
   bir yanıt `Retry-After` taşırsa sonraki istek en erken o an atılır. Saat enjekte edilir.
5. 403/429 kaynağı bu TUR (`ScrapeRound`) için durdurur: aynı turda o kaynağa — başka oturum,
   başka fetcher ya da başka yolla da — ikinci istek atılmaz. Kimlik, başlık, yol ya da fetcher
   değiştirerek yeniden deneme yok; Scrapling'in kendi yeniden denemesi de kapalı (`retries=1`).
6. Yönlendirme otomatik izlenmez: her sıçrama aynı orijin ve robots denetiminden (2. ve 3. madde)
   geçer; başka bir orijine sıçrama `SourceBlocked`.

Taşıyıcı (`Transport`) sözleşmesi: attığı HER istekten önce `guard(url, user_agent)`ı çağırır ve
yönlendirmeyi kendisi izlemez. `FetcherTransport` (varsayılan, curl_cffi) bunu birebir yapar.
Tarayıcı taşıyıcıları (`dynamic`, `stealthy`) sayfanın her isteğini bir rota işleyicisinde bekçiden
geçirir; sınırları modül sonunda ve raporda yazılıdır.

Scrapling fetcher sınıfları bu modülün açık adı DEĞİLDİR (`_scrapling` önekli modül takma adıyla
erişilir): bir sınıfın buradan yeniden ihraç edilip geçidin dışında kullanılması test edilir.
"""

from __future__ import annotations

import dataclasses
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Final, Literal, Protocol
from urllib.parse import urljoin, urlsplit

from protego import Protego
from scrapling import fetchers as _scrapling

from football_edge.collector import ContractViolation
from football_edge.sources import (
    ACCESS_BASIS_ROBOTS,
    Source,
    SourceBlocked,
    load_sources,
    snapshot_from_status,
)

# `collect.SOURCES_PATH` ile aynı (test eşitliği zorlar); `collect`i içe aktarmak bu modüle
# veritabanı ve Jev bağımlılıklarını taşırdı. Parametre DEĞİLDİR: kaynak kaydı değiştirilemez.
REGISTRY_PATH = Path("config/sources.yaml")

# Scrapling'in `impersonate` varsayılanı ("chrome", curl_cffi'nin en yeni Chrome hedefi). Tek dize
# olarak sabitlenir: liste verilirse Scrapling her istekte rastgele seçer — kimlik döndürme olurdu.
IMPERSONATE: Final = "chrome"
# `impersonate="chrome"` ile curl_cffi 0.16.3'ün gönderdiği User-Agent (2026-09-23 loopback'te
# ölçüldü). Açıkça gönderilir: robots'un ikinci ekseni tam bu dizeyle sorulur, tahminle değil.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)
TIMEOUT_SECONDS = 30
MAX_REDIRECTS = 5
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
# Kaynak bizi geri çeviriyor: tur durur (spec §3.2.1 "Yasak", R77b sınır 4).
HALT_STATUSES = frozenset({403, 429})
ROBOTS_PATH = "/robots.txt"

FetcherKind = Literal["fetcher", "dynamic", "stealthy"]
Guard = Callable[[str, str], None]


class SourceHalted(SourceBlocked):
    """Kaynak 403/429 döndü; bu turda ona istek atılmaz (yakalanıp yeniden denenmez)."""


@dataclass(frozen=True)
class Fetched:
    """Taşıyıcıdan dönen ham yanıt. Başlık araması büyük/küçük harfe duyarsızdır; gövde ham bayttır
    (TFF'de charset yalnız HTTP başlığında: çözümü ayrıştırıcı açıkça yapar)."""

    url: str
    status: int
    headers: Mapping[str, str]
    body: bytes

    def header(self, name: str) -> str:
        wanted = name.lower()
        return next((value for key, value in self.headers.items() if key.lower() == wanted), "")

    def text(self, encoding: str) -> str:
        return self.body.decode(encoding, errors="strict")


class Transport(Protocol):
    """Attığı HER istekten önce `guard(url, gönderilen_user_agent)` çağırır; yönlendirme izlemez."""

    @property
    def user_agent(self) -> str: ...

    def get(self, url: str, guard: Guard) -> Fetched: ...


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...

    def now(self) -> datetime: ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def now(self) -> datetime:
        return datetime.now(UTC)


def _fetched(response: Any) -> Fetched:
    body = response.body
    return Fetched(
        url=str(response.url),
        status=int(response.status),
        headers={str(key).lower(): str(value) for key, value in dict(response.headers).items()},
        body=body if isinstance(body, bytes) else str(body).encode("utf-8"),
    )


class FetcherTransport:
    """Varsayılan taşıyıcı: Scrapling `Fetcher` (curl_cffi), R77b varsayılanları açık.

    `client` yalnız testte değişir (sahte, ağsız); üretimde Scrapling'in `Fetcher`ıdır."""

    def __init__(self, client: Any = None) -> None:
        self._client = _scrapling.Fetcher if client is None else client

    @property
    def user_agent(self) -> str:
        return BROWSER_USER_AGENT

    def get(self, url: str, guard: Guard) -> Fetched:
        guard(url, self.user_agent)
        response = self._client.get(
            url,
            impersonate=IMPERSONATE,
            stealthy_headers=True,
            headers={"User-Agent": self.user_agent},
            follow_redirects=False,
            retries=1,
            timeout=TIMEOUT_SECONDS,
        )
        return _fetched(response)


class BrowserTransport:
    """`DynamicFetcher` ya da `StealthyFetcher`: tarayıcı sayfanın isteklerini kendisi atar.

    Bekçi bir rota işleyicisidir (`page_setup` → `page.route("**/*")`): orijin dışı ya da robots'a
    aykırı her istek `abort` edilir, izinli olan Scrapling'in kendi işleyicisine devredilir
    (`fallback`). İşleyici kurulamadıysa (Scrapling `page_setup` hatasını yutar) ya da bir istek
    engellendiyse yanıt KULLANILMAZ. Arka plan kaynakları (`disable_resources`) hiç istenmez."""

    def __init__(self, kind: Literal["dynamic", "stealthy"], client: Any = None) -> None:
        default = _scrapling.DynamicFetcher if kind == "dynamic" else _scrapling.StealthyFetcher
        self._client = default if client is None else client

    @property
    def user_agent(self) -> str:
        return BROWSER_USER_AGENT

    def get(self, url: str, guard: Guard) -> Fetched:
        guard(url, self.user_agent)
        blocked: list[str] = []
        installed: list[bool] = []

        def on_route(route: Any) -> None:
            request = route.request
            try:
                guard(str(request.url), request.headers.get("user-agent", self.user_agent))
            except SourceBlocked as error:
                blocked.append(str(error))
                route.abort()
                return
            route.fallback()

        def page_setup(page: Any) -> None:
            page.route("**/*", on_route)
            installed.append(True)

        response = self._client.fetch(
            url,
            page_setup=page_setup,
            useragent=self.user_agent,
            disable_resources=True,
            retries=1,
            timeout=TIMEOUT_SECONDS * 1000,
        )
        if not installed:
            raise SourceBlocked(f"{url}: tarayıcı rota bekçisi kurulamadı — yanıt kullanılmadı")
        if blocked:
            raise SourceBlocked(
                f"tarayıcı bekçisi istek engelledi — yanıt kullanılmadı: {blocked[0]}"
            )
        return _fetched(response)


def build_transport(fetcher: FetcherKind) -> Transport:
    if fetcher == "fetcher":
        return FetcherTransport()
    return BrowserTransport(fetcher)


def _origin(url: str) -> tuple[str, str, int | None]:
    parts = urlsplit(url)
    default_port = {"http": 80, "https": 443}.get(parts.scheme.lower())
    return (parts.scheme.lower(), (parts.hostname or "").lower(), parts.port or default_port)


def _path_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.path or '/'}?{parts.query}" if parts.query else (parts.path or "/")


def _declared_path(source: Source, url: str) -> str:
    if _origin(url) != _origin(source.base_url):
        raise SourceBlocked(f"{source.id}: {url} kaynağın orijininde değil — istek atılmadı")
    if urlsplit(url).fragment:
        raise SourceBlocked(f"{source.id}: {url} parça (#) taşıyor — istek atılmadı")
    path = _path_of(url)
    if path not in source.declared_paths:
        raise SourceBlocked(f"{source.id}: '{path}' declared_paths'te yok (R7) — istek atılmadı")
    return path


def _retry_after_seconds(value: str, now: datetime) -> float | None:
    """`Retry-After`: saniye ya da HTTP tarihi. Çözülemeyen değer yok sayılır (403/429 durur)."""
    text = value.strip()
    if not text:
        return None
    if text.isdigit():
        return float(text)
    try:
        moment = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    return max(0.0, (moment - now).total_seconds())


@dataclass(frozen=True)
class _SourceState:
    robots: Protego | None = None
    delay: float = 0.0
    last_request: float | None = None
    not_before: float = 0.0
    halted: str | None = None


class ScrapeRound:
    """Bir toplama turu: kaynak başına robots, bekleme ve durma durumu burada tutulur.

    Yeni tur = yeni nesne (ör. bir sonraki zamanlanmış koşu). Aynı tur içinde 403/429 alan
    kaynak, hangi oturum ya da fetcher'la istenirse istensin, yeniden istenmez."""

    def __init__(self, *, clock: Clock | None = None, robots_transport: Transport | None = None):
        self._clock: Clock = SystemClock() if clock is None else clock
        self._robots_transport = robots_transport
        self._registry = load_sources(REGISTRY_PATH)
        self._states: dict[str, _SourceState] = {}

    def session(
        self,
        source: Source,
        transport: Transport | None = None,
        *,
        fetcher: FetcherKind = "fetcher",
    ) -> ScrapeSession:
        if source not in self._registry:
            raise SourceBlocked(
                f"{source.id}: {REGISTRY_PATH} kaydıyla birebir aynı değil — istek atılmadı"
            )
        if source.access_basis != ACCESS_BASIS_ROBOTS:
            raise SourceBlocked(f"{source.id}: access_basis={source.access_basis}, robots değil")
        chosen = build_transport(fetcher) if transport is None else transport
        return ScrapeSession(self, source, chosen)

    def _state(self, source: Source) -> _SourceState:
        return self._states.get(source.id, _SourceState())

    def _update(self, source: Source, **changes: Any) -> None:
        self._states = {
            **self._states,
            source.id: dataclasses.replace(self._state(source), **changes),
        }

    def _ensure_open(self, source: Source) -> None:
        halted = self._state(source).halted
        if halted is not None:
            raise SourceHalted(halted)

    def _wait(self, source: Source) -> None:
        self._ensure_open(source)
        state = self._state(source)
        ready = state.not_before
        if state.last_request is not None:
            ready = max(ready, state.last_request + state.delay)
        remaining = ready - self._clock.monotonic()
        if remaining > 0:
            self._clock.sleep(remaining)

    def _send(self, source: Source, transport: Transport, url: str, guard: Guard) -> Fetched:
        self._wait(source)
        try:
            fetched = transport.get(url, guard)
        finally:
            self._update(source, last_request=self._clock.monotonic())
        retry_after = _retry_after_seconds(fetched.header("retry-after"), self._clock.now())
        if retry_after is not None:
            self._update(source, not_before=self._clock.monotonic() + retry_after)
        if fetched.status in HALT_STATUSES:
            reason = f"{source.id}: HTTP {fetched.status} ({url}) — kaynak bu turda durdu"
            self._update(source, halted=reason)
            raise SourceHalted(reason)
        return fetched

    def _robots(self, source: Source, user_agent: str) -> Protego:
        state = self._state(source)
        if state.robots is not None:
            return state.robots
        robots_url = f"{source.base_url}{ROBOTS_PATH}"

        def robots_guard(url: str, _user_agent: str) -> None:
            if url != robots_url:
                raise SourceBlocked(f"{source.id}: robots okuması {url}'e sıçramaz")

        transport = self._robots_transport or FetcherTransport()
        fetched = self._send(source, transport, robots_url, robots_guard)
        body = snapshot_from_status(fetched.status, fetched.body.decode("utf-8", "replace"))
        if body is None:
            raise SourceBlocked(
                f"{source.id}: robots.txt ölçülemedi (HTTP {fetched.status}) — istek atılmadı"
            )
        parser = Protego.parse(body)
        delays = (parser.crawl_delay(agent) for agent in (source.user_agent, user_agent))
        delay = max([source.crawl_delay_seconds, *(float(d) for d in delays if d is not None)])
        self._update(source, robots=parser, delay=delay)
        return parser

    def _guard(self, source: Source, parser: Protego) -> Guard:
        def guard(url: str, user_agent: str) -> None:
            if _origin(url) != _origin(source.base_url):
                raise SourceBlocked(f"{source.id}: {url} orijin dışı — istek atılmadı")
            for agent in (source.user_agent, user_agent):
                if not parser.can_fetch(url=url, user_agent=agent):
                    raise SourceBlocked(
                        f"{source.id}: robots.txt '{_path_of(url)}' yolunu '{agent}' için "
                        "kapatıyor — istek atılmadı"
                    )

        return guard


class ScrapeSession:
    """Bir kaynak + bir taşıyıcı. `get` tek giriş kapısıdır; `ScrapeRound.session` ile kurulur."""

    def __init__(self, scrape_round: ScrapeRound, source: Source, transport: Transport) -> None:
        self._round = scrape_round
        self._source = source
        self._transport = transport

    def get(self, url: str) -> Fetched:
        _declared_path(self._source, url)
        self._round._ensure_open(self._source)
        parser = self._round._robots(self._source, self._transport.user_agent)
        guard = self._round._guard(self._source, parser)
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            fetched = self._round._send(self._source, self._transport, current, guard)
            if _origin(fetched.url) != _origin(self._source.base_url):
                raise SourceBlocked(f"{self._source.id}: yanıt orijin dışından ({fetched.url})")
            if fetched.status not in REDIRECT_STATUSES:
                return _accepted(self._source, fetched)
            location = fetched.header("location")
            if not location:
                raise ContractViolation(f"{self._source.id}: {fetched.status} ama Location yok")
            current = urljoin(current, location)
        raise ContractViolation(f"{self._source.id}: {MAX_REDIRECTS} yönlendirmeden sonra sıçrıyor")


def _accepted(source: Source, fetched: Fetched) -> Fetched:
    if not 200 <= fetched.status < 300:
        raise ContractViolation(f"{source.id}: HTTP {fetched.status} ({fetched.url})")
    return fetched


# Bilinen sınırlar (kod dışı; raporda ve tests/test_scrape.py docstring'inde de):
# - Tarayıcı taşıyıcılarında bekçi Playwright rotasıdır. Yönlendirme sıçramalarının ve servis
#   çalışanı isteklerinin rotaya uğrayıp uğramadığı bu depoda ÖLÇÜLMEDİ (tarayıcı ikilisi kurulu
#   değil; testler sahte sayfayla). Sayfanın alt istekleri crawl-delay'e tabi değildir.
# - Yönlendirme hedefi yalnız orijin + robots'tan geçer; `declared_paths`e bakılmaz (brief).
# - robots.txt'in kendisi yönlendirirse "ölçülemedi" sayılır (RFC 9309 izlemeyi önerir; burada
#   temkinli taraf seçildi).
