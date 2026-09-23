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
Tarayıcı taşıyıcıları (`dynamic`, `stealthy`) KAPALI: `build_transport` onları
`BrowserTransportDisabled` ile reddeder (Playwright rotası yönlendirme sıçramalarını göstermiyor;
gerçek tarayıcıyla ölçülmeden açılmaz — DEFERRED 11g).

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
# `Retry-After` bundan uzunsa beklenmez, kaynak bu turda durur (sonsuz uykuya karşı; Minor 3).
RETRY_AFTER_CAP_SECONDS = 3600.0
BROWSER_DISABLED_REASON = (
    "tarayıcı taşıyıcıları (dynamic/stealthy) kapalı: Playwright `page.route` yönlendirme "
    "sıçramalarını ve service worker isteklerini rota işleyicisine göstermiyor (belgelenmiş "
    "davranış), yani sıçramalar bekçiden ve crawl-delay'den geçmeden izlenir; "
    "gerçek tarayıcıyla ölçülmeden açılmaz — DEFERRED'e bak (§11, 11g)"
)

FetcherKind = Literal["fetcher", "dynamic", "stealthy"]
Guard = Callable[[str, str], None]


class SourceHalted(SourceBlocked):
    """Kaynak 403/429 döndü; bu turda ona istek atılmaz (yakalanıp yeniden denenmez)."""


class BrowserTransportDisabled(SourceBlocked):
    """`dynamic`/`stealthy` istendi: gerçek tarayıcıyla ölçülene kadar reddedilir."""


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
    """`DynamicFetcher` / `StealthyFetcher` — KAPALI (`BROWSER_DISABLED_REASON`, DEFERRED 11g).

    Kurulamaz: her kurulum `BrowserTransportDisabled` fırlatır. Açıldığında kullanılacak bekçi
    `_browser_fetch`tedir ve sahte sayfayla sınanır; gerçek Playwright'ın her sıçramayı o bekçiden
    geçirdiği ölçülmeden bu sınıf açılmaz."""

    def __init__(self, kind: Literal["dynamic", "stealthy"]) -> None:
        raise BrowserTransportDisabled(f"{kind}: {BROWSER_DISABLED_REASON}")


def _browser_fetch(client: Any, url: str, guard: Guard, user_agent: str) -> Fetched:
    """Tarayıcı bekçisi (henüz çağıranı yok): `page_setup` → `page.route("**/*")`; orijin dışı ya da
    robots'a aykırı her istek `abort`, izinli olan Scrapling'in işleyicisine `fallback`. İşleyici
    kurulamadıysa (Scrapling `page_setup` hatasını yutar) ya da bir istek engellendiyse yanıt
    KULLANILMAZ. Arka plan kaynakları (`disable_resources`) hiç istenmez."""
    guard(url, user_agent)
    blocked: list[str] = []
    installed: list[bool] = []

    def on_route(route: Any) -> None:
        request = route.request
        try:
            guard(str(request.url), request.headers.get("user-agent", user_agent))
        except SourceBlocked as error:
            blocked.append(str(error))
            route.abort()
            return
        route.fallback()

    def page_setup(page: Any) -> None:
        page.route("**/*", on_route)
        installed.append(True)

    response = client.fetch(
        url,
        page_setup=page_setup,
        useragent=user_agent,
        disable_resources=True,
        retries=1,
        timeout=TIMEOUT_SECONDS * 1000,
    )
    if not installed:
        raise SourceBlocked(f"{url}: tarayıcı rota bekçisi kurulamadı — yanıt kullanılmadı")
    if blocked:
        raise SourceBlocked(f"tarayıcı bekçisi istek engelledi — yanıt kullanılmadı: {blocked[0]}")
    return _fetched(response)


def build_transport(fetcher: FetcherKind) -> Transport:
    if fetcher == "fetcher":
        return FetcherTransport()
    raise BrowserTransportDisabled(f"{fetcher}: {BROWSER_DISABLED_REASON}")


def _origin(url: str) -> tuple[str, str, int | None]:
    parts = urlsplit(url)
    default_port = {"http": 80, "https": 443}.get(parts.scheme.lower())
    return (parts.scheme.lower(), (parts.hostname or "").lower(), parts.port or default_port)


def _path_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.path or '/'}?{parts.query}" if parts.query else (parts.path or "/")


def _carries_credentials(url: str) -> bool:
    """`kullanıcı:parola@` ya da ters bölü: urlsplit ile tarayıcı (WHATWG) host'u farklı okur."""
    parts = urlsplit(url)
    return "@" in parts.netloc or "\\" in url or parts.username is not None


def _declared_path(source: Source, url: str) -> str:
    if _carries_credentials(url):
        raise SourceBlocked(f"{source.id}: URL kimlik bilgisi/ters bölü taşıyor — istek atılmadı")
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
    if text.isascii() and text.isdigit():
        return float(text)
    try:
        moment = parsedate_to_datetime(text)
        # `-0000` bölgesi naive döner (stdlib): UTC sayılır (inceleme Critical 1).
        aware = moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
        return max(0.0, (aware - now).total_seconds())
    except (TypeError, ValueError, OverflowError, IndexError):
        return None


def _crawl_delay(source: Source, parser: Protego, user_agent: str) -> float:
    """max(kaynağın `crawl_delay_seconds`i, robots `Crawl-delay`i iki eksen için)."""
    delays = (parser.crawl_delay(agent) for agent in (source.user_agent, user_agent))
    return max([source.crawl_delay_seconds, *(float(d) for d in delays if d is not None)])


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
        # Durma KARARI başlık okumadan ÖNCE kaydedilir: hiçbir Retry-After biçimi durmayı atlatamaz.
        if fetched.status in HALT_STATUSES:
            reason = f"{source.id}: HTTP {fetched.status} ({url}) — kaynak bu turda durdu"
            self._update(source, halted=reason)
            raise SourceHalted(reason)
        retry_after = _retry_after_seconds(fetched.header("retry-after"), self._clock.now())
        if retry_after is not None and retry_after > RETRY_AFTER_CAP_SECONDS:
            self._update(
                source,
                halted=f"{source.id}: Retry-After {retry_after:.0f} sn, tavan "
                f"{RETRY_AFTER_CAP_SECONDS:.0f} sn — beklenmez, kaynak bu turda durdu",
            )
        elif retry_after is not None:
            self._update(source, not_before=self._clock.monotonic() + retry_after)
        return fetched

    def _robots(self, source: Source, user_agent: str) -> Protego:
        state = self._state(source)
        if state.robots is not None:
            # Turun sonraki bir taşıyıcısı başka UA taşıyabilir: onun Crawl-delay'i de sorulur.
            delay = max(state.delay, _crawl_delay(source, state.robots, user_agent))
            self._update(source, delay=delay)
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
        self._update(source, robots=parser, delay=_crawl_delay(source, parser, user_agent))
        return parser

    def _guard(self, source: Source, parser: Protego) -> Guard:
        def guard(url: str, user_agent: str) -> None:
            if _carries_credentials(url):
                raise SourceBlocked(f"{source.id}: URL kimlik bilgisi taşıyor — istek atılmadı")
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
# - Tarayıcı taşıyıcıları kapalı (DEFERRED 11g). Playwright 1.63 `page.route` belgesi: işleyici
#   yönlendirmede yalnız İLK URL için çağrılır ve service worker'ın yakaladığı istekleri görmez.
#   Açılırsa sayfanın alt istekleri de crawl-delay'e ve 403/429 durmasına tabi değildir.
# - `Transport` dikişi: bekçiyi çağırmayan bir taşıyıcı kodla reddedilmez (yalnız testte verilir).
# - Yönlendirme hedefi yalnız orijin + robots'tan geçer; `declared_paths`e bakılmaz (brief).
# - robots.txt'in kendisi yönlendirirse "ölçülemedi" sayılır (RFC 9309 izlemeyi önerir; burada
#   temkinli taraf seçildi).
