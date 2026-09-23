"""Scrapling adaptörünün (`football_edge.scrape`) davranış testleri — ağsız, tarayıcısız.

Taşıyıcı ve saat enjekte edilir. Sahte taşıyıcı sözleşmeye sadıktır: her istekten önce bekçiyi
(`guard`) çağırır, istenmeyen URL'ye 404 döner ve her gönderilen isteği kaydeder — testler
"istek ATILMADI"yı bu kayıttan okur, yalnız istisnadan değil.

Kaynaklar gerçek `config/sources.yaml`dan gelir (adaptör başkasını kabul etmez). `tff` seçildi:
`access_basis: robots`, tek beyanlı yol, `crawl_delay_seconds: 2.0`, belirteç `football-edge/0.1`.

Bilinen sınırlar (ölçülmeyen):
- Tarayıcı taşıyıcısının bekçisi sahte bir sayfa ve rota ile sınanır; gerçek Playwright'ın
  yönlendirme sıçramalarını rotaya uğratıp uğratmadığı burada ölçülmez (tarayıcı ikilisi yok).
- Gerçek curl_cffi'nin `follow_redirects=False`a uyduğu burada değil, fixture kaydında görüldü.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from types import SimpleNamespace
from typing import Any

import pytest
import scrapling.fetchers

from football_edge import scrape
from football_edge.collect import SOURCES_PATH
from football_edge.collector import ContractViolation
from football_edge.scrape import (
    BROWSER_USER_AGENT,
    BrowserTransport,
    Fetched,
    FetcherTransport,
    ScrapeRound,
    SourceHalted,
)
from football_edge.sources import Source, SourceBlocked, load_sources

BASE = "https://www.tff.org"
PAGE = f"{BASE}/Default.aspx?pageID=600"
ROBOTS = f"{BASE}/robots.txt"
START = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def registry_source(source_id: str) -> Source:
    return next(entry for entry in load_sources(SOURCES_PATH) if entry.id == source_id)


TFF = registry_source("tff")


def response(
    url: str, status: int = 200, body: str = "", headers: Mapping[str, str] | None = None
) -> Fetched:
    return Fetched(url=url, status=status, headers=dict(headers or {}), body=body.encode())


@dataclass
class FakeTransport:
    routes: dict[str, list[Fetched]]
    user_agent: str = BROWSER_USER_AGENT
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, guard: scrape.Guard) -> Fetched:
        guard(url, self.user_agent)
        self.calls.append(url)
        queue = self.routes.get(url)
        if not queue:
            return response(url, 404)
        return queue.pop(0) if len(queue) > 1 else queue[0]


@dataclass
class FakeClock:
    t: float = 1000.0
    sleeps: list[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds

    def now(self) -> datetime:
        return START + timedelta(seconds=self.t - 1000.0)


def transport_with(robots: Fetched, *pages: tuple[str, list[Fetched]]) -> FakeTransport:
    return FakeTransport(routes={ROBOTS: [robots], **dict(pages)})


def session_for(transport: FakeTransport, clock: FakeClock | None = None) -> scrape.ScrapeSession:
    return ScrapeRound(clock=clock or FakeClock(), robots_transport=transport).session(
        TFF, transport
    )


NO_ROBOTS = response(ROBOTS, 404)


# ── 1. Yalnız sources.yaml kaynağı ──────────────────────────────────────────────


def test_a_source_that_is_not_in_the_registry_is_refused() -> None:
    fabricated = Source(
        id="elle",
        base_url=BASE,
        user_agent="football-edge/0.1",
        crawl_delay_seconds=2.0,
        robots_verified_at=TFF.robots_verified_at,
        declared_paths=("/Default.aspx?pageID=600",),
        enabled=True,
        note="",
        access_basis="robots",
        terms_url="",
    )
    with pytest.raises(SourceBlocked, match="birebir aynı değil"):
        ScrapeRound(clock=FakeClock()).session(fabricated, transport_with(NO_ROBOTS))


def test_a_registry_source_with_an_edited_field_is_refused() -> None:
    edited = dataclasses.replace(TFF, crawl_delay_seconds=0.0)
    with pytest.raises(SourceBlocked, match="birebir aynı değil"):
        ScrapeRound(clock=FakeClock()).session(edited, transport_with(NO_ROBOTS))


def test_an_api_terms_source_is_not_scraped() -> None:
    with pytest.raises(SourceBlocked, match="robots değil"):
        ScrapeRound(clock=FakeClock()).session(
            registry_source("openmeteo"), transport_with(NO_ROBOTS)
        )


def test_registry_path_is_the_collectors_registry() -> None:
    assert scrape.REGISTRY_PATH == SOURCES_PATH


# ── 2. Host ve yol (R7) — istek ATILMADAN ─────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/Default.aspx?pageID=600",
        "https://www.tff.org.evil.com/Default.aspx?pageID=600",
        "http://www.tff.org/Default.aspx?pageID=600",
        "https://www.tff.org:8443/Default.aspx?pageID=600",
    ],
)
def test_another_origin_is_refused_before_any_request(url: str) -> None:
    transport = transport_with(NO_ROBOTS, (url, [response(url)]))
    with pytest.raises(SourceBlocked, match="orijininde değil"):
        session_for(transport).get(url)
    assert transport.calls == []


@pytest.mark.parametrize(
    "path",
    ["/Default.aspx?pageID=433", "/Default.aspx", "/Default.aspx?pageID=600&x=1"],
)
def test_an_undeclared_path_is_refused_before_any_request(path: str) -> None:
    transport = transport_with(NO_ROBOTS, (f"{BASE}{path}", [response(f"{BASE}{path}")]))
    with pytest.raises(SourceBlocked, match="declared_paths"):
        session_for(transport).get(f"{BASE}{path}")
    assert transport.calls == []


# ── 3. robots — iki eksen, canlı ──────────────────────────────────────────────


def test_robots_closed_for_the_source_token_blocks_the_request() -> None:
    robots = response(ROBOTS, body="User-agent: football-edge\nDisallow: /\n\nUser-agent: *\n")
    transport = transport_with(robots, (PAGE, [response(PAGE)]))
    with pytest.raises(SourceBlocked, match="football-edge/0.1"):
        session_for(transport).get(PAGE)
    assert transport.calls == [ROBOTS]


def test_robots_closed_for_the_browser_identity_blocks_the_request() -> None:
    robots = response(
        ROBOTS, body="User-agent: football-edge\nAllow: /\n\nUser-agent: *\nDisallow: /\n"
    )
    transport = transport_with(robots, (PAGE, [response(PAGE)]))
    with pytest.raises(SourceBlocked, match="Mozilla"):
        session_for(transport).get(PAGE)
    assert transport.calls == [ROBOTS]


@pytest.mark.parametrize("status", [500, 503, 302])
def test_robots_that_cannot_be_measured_block_the_request(status: int) -> None:
    transport = transport_with(response(ROBOTS, status), (PAGE, [response(PAGE)]))
    with pytest.raises(SourceBlocked, match="ölçülemedi"):
        session_for(transport).get(PAGE)
    assert transport.calls == [ROBOTS]


def test_missing_robots_means_no_policy_and_the_page_is_fetched() -> None:
    transport = transport_with(NO_ROBOTS, (PAGE, [response(PAGE, body="ok")]))
    fetched = session_for(transport).get(PAGE)
    assert fetched.body == b"ok"
    assert transport.calls == [ROBOTS, PAGE]


# ── 4. crawl-delay ve Retry-After ─────────────────────────────────────────────


def test_robots_crawl_delay_larger_than_the_sources_is_waited_between_requests() -> None:
    robots = response(ROBOTS, body="User-agent: *\nCrawl-delay: 7\n")
    clock = FakeClock()
    transport = transport_with(robots, (PAGE, [response(PAGE)]))
    session = session_for(transport, clock)
    session.get(PAGE)
    session.get(PAGE)
    assert clock.sleeps == [7.0, 7.0]
    assert transport.calls == [ROBOTS, PAGE, PAGE]


def test_the_sources_crawl_delay_applies_when_robots_sets_none() -> None:
    clock = FakeClock()
    session = session_for(transport_with(NO_ROBOTS, (PAGE, [response(PAGE)])), clock)
    session.get(PAGE)
    session.get(PAGE)
    assert clock.sleeps == [TFF.crawl_delay_seconds] * 2


@pytest.mark.parametrize(
    "retry_after",
    ["30", format_datetime(START + timedelta(seconds=30), usegmt=True)],
    ids=["saniye", "http-tarihi"],
)
def test_retry_after_delays_the_next_request(retry_after: str) -> None:
    clock = FakeClock()
    busy = response(PAGE, 503, headers={"Retry-After": retry_after})
    transport = transport_with(NO_ROBOTS, (PAGE, [busy, response(PAGE)]))
    session = session_for(transport, clock)
    with pytest.raises(ContractViolation, match="503"):
        session.get(PAGE)
    session.get(PAGE)
    assert clock.sleeps[-1] >= 28.0
    assert transport.calls == [ROBOTS, PAGE, PAGE]


# ── 5. 403/429 turu durdurur ──────────────────────────────────────────────────


@pytest.mark.parametrize("status", [403, 429])
def test_a_refusal_halts_the_source_for_the_round(status: int) -> None:
    clock = FakeClock()
    transport = transport_with(NO_ROBOTS, (PAGE, [response(PAGE, status), response(PAGE)]))
    scrape_round = ScrapeRound(clock=clock, robots_transport=transport)
    with pytest.raises(SourceHalted, match=str(status)):
        scrape_round.session(TFF, transport).get(PAGE)
    with pytest.raises(SourceHalted):
        scrape_round.session(TFF, transport).get(PAGE)
    other = transport_with(NO_ROBOTS, (PAGE, [response(PAGE)]))
    other.user_agent = "başka-kimlik/1"
    with pytest.raises(SourceHalted):
        scrape_round.session(TFF, other).get(PAGE)
    assert transport.calls == [ROBOTS, PAGE]
    assert other.calls == []


def test_a_refused_robots_fetch_also_halts_the_source() -> None:
    transport = transport_with(response(ROBOTS, 403), (PAGE, [response(PAGE)]))
    session = session_for(transport)
    with pytest.raises(SourceHalted):
        session.get(PAGE)
    with pytest.raises(SourceHalted):
        session.get(PAGE)
    assert transport.calls == [ROBOTS]


# ── 6. Yönlendirme: her sıçrama bekçiden ──────────────────────────────────────


@pytest.mark.parametrize(
    "location",
    ["https://evil.example/x", "https://www.tff.org.evil.com/x", "//evil.example/x"],
)
def test_a_redirect_to_another_origin_is_not_followed(location: str) -> None:
    hop = response(PAGE, 302, headers={"Location": location})
    transport = transport_with(NO_ROBOTS, (PAGE, [hop]))
    with pytest.raises(SourceBlocked, match="orijin dışı"):
        session_for(transport).get(PAGE)
    assert transport.calls == [ROBOTS, PAGE]


def test_a_same_origin_redirect_into_a_robots_closed_path_is_not_followed() -> None:
    robots = response(ROBOTS, body="User-agent: *\nDisallow: /kapali\n")
    hop = response(PAGE, 301, headers={"Location": "/kapali/sayfa"})
    transport = transport_with(robots, (PAGE, [hop]))
    with pytest.raises(SourceBlocked, match="/kapali/sayfa"):
        session_for(transport).get(PAGE)
    assert transport.calls == [ROBOTS, PAGE]


def test_an_allowed_same_origin_redirect_is_followed_after_the_crawl_delay() -> None:
    target = f"{BASE}/Default.aspx?pageID=601"
    clock = FakeClock()
    hop = response(PAGE, 302, headers={"Location": "/Default.aspx?pageID=601"})
    transport = transport_with(NO_ROBOTS, (PAGE, [hop]), (target, [response(target, body="son")]))
    fetched = session_for(transport, clock).get(PAGE)
    assert fetched.body == b"son"
    assert transport.calls == [ROBOTS, PAGE, target]
    assert clock.sleeps == [TFF.crawl_delay_seconds] * 2


def test_an_endless_redirect_chain_stops() -> None:
    hop = response(PAGE, 302, headers={"Location": PAGE})
    transport = transport_with(NO_ROBOTS, (PAGE, [hop]))
    with pytest.raises(ContractViolation, match="yönlendirme"):
        session_for(transport).get(PAGE)
    assert transport.calls.count(PAGE) == scrape.MAX_REDIRECTS + 1


# ── Taşıyıcılar: Scrapling'e giden argümanlar ─────────────────────────────────


@dataclass
class RecordingClient:
    kwargs: dict[str, Any] = field(default_factory=dict)

    def get(self, url: str, **kwargs: Any) -> Any:
        self.kwargs = {"url": url, **kwargs}
        return SimpleNamespace(url=url, status=200, headers={"X-A": "b"}, body=b"x")


def allow_all(url: str, user_agent: str) -> None:
    del url, user_agent


def test_the_default_transport_sends_one_request_without_following_redirects() -> None:
    client = RecordingClient()
    fetched = FetcherTransport(client).get(PAGE, allow_all)
    sent = client.kwargs
    assert sent["follow_redirects"] is False
    assert sent["retries"] == 1
    assert sent["impersonate"] == "chrome"
    assert sent["stealthy_headers"] is True
    assert sent["headers"] == {"User-Agent": BROWSER_USER_AGENT}
    assert not [key for key in sent if "prox" in key or "solve" in key]
    assert fetched.header("x-a") == "b"


def test_the_default_transport_asks_the_guard_before_sending() -> None:
    client = RecordingClient()
    seen: list[tuple[str, str]] = []

    def refuse(url: str, user_agent: str) -> None:
        seen.append((url, user_agent))
        raise SourceBlocked("hayır")

    with pytest.raises(SourceBlocked):
        FetcherTransport(client).get(PAGE, refuse)
    assert client.kwargs == {}
    assert seen == [(PAGE, BROWSER_USER_AGENT)]


def test_the_default_fetcher_is_scraplings_static_fetcher() -> None:
    round_ = ScrapeRound(clock=FakeClock())
    assert isinstance(round_.session(TFF)._transport, FetcherTransport)
    assert isinstance(round_.session(TFF, fetcher="dynamic")._transport, BrowserTransport)
    assert FetcherTransport()._client is scrapling.fetchers.Fetcher
    assert BrowserTransport("stealthy")._client is scrapling.fetchers.StealthyFetcher


@dataclass
class FakeRoute:
    url: str
    user_agent: str
    outcome: str = ""

    @property
    def request(self) -> Any:
        return SimpleNamespace(url=self.url, headers={"user-agent": self.user_agent})

    def abort(self) -> None:
        self.outcome = "abort"

    def fallback(self) -> None:
        self.outcome = "fallback"


@dataclass
class FakeBrowserClient:
    requests: list[FakeRoute]
    run_setup: bool = True
    kwargs: dict[str, Any] = field(default_factory=dict)

    def fetch(self, url: str, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        handlers: list[Any] = []
        page = SimpleNamespace(route=lambda pattern, handler: handlers.append(handler))
        if self.run_setup:
            kwargs["page_setup"](page)
        for route in self.requests:
            for handler in handlers:
                handler(route)
        return SimpleNamespace(url=url, status=200, headers={}, body="<html></html>")


def origin_guard(url: str, user_agent: str) -> None:
    del user_agent
    if not url.startswith(f"{BASE}/"):
        raise SourceBlocked(f"orijin dışı {url}")


def test_the_browser_guard_aborts_a_request_to_another_origin() -> None:
    inside = FakeRoute(PAGE, BROWSER_USER_AGENT)
    outside = FakeRoute("https://cdn.example/a.js", BROWSER_USER_AGENT)
    client = FakeBrowserClient([inside, outside])
    with pytest.raises(SourceBlocked, match="cdn.example"):
        BrowserTransport("dynamic", client).get(PAGE, origin_guard)
    assert (inside.outcome, outside.outcome) == ("fallback", "abort")
    assert client.kwargs["retries"] == 1
    assert client.kwargs["useragent"] == BROWSER_USER_AGENT
    assert not [key for key in client.kwargs if "prox" in key or "solve" in key]


def test_the_browser_guard_sees_the_user_agent_actually_sent() -> None:
    seen: list[str] = []

    def record(url: str, user_agent: str) -> None:
        del url
        seen.append(user_agent)

    client = FakeBrowserClient([FakeRoute(PAGE, "HeadlessChrome/150")])
    BrowserTransport("stealthy", client).get(PAGE, record)
    assert seen == [BROWSER_USER_AGENT, "HeadlessChrome/150"]


def test_a_browser_page_whose_guard_was_never_installed_is_discarded() -> None:
    client = FakeBrowserClient([], run_setup=False)
    with pytest.raises(SourceBlocked, match="kurulamadı"):
        BrowserTransport("dynamic", client).get(PAGE, origin_guard)


# ── Tek geçit: fetcher sınıfları adaptörden yeniden ihraç edilmez ─────────────


def test_no_public_name_of_the_adapter_is_a_scrapling_fetcher() -> None:
    fetcher_objects = {id(getattr(scrapling.fetchers, name)) for name in scrapling.fetchers.__all__}
    leaked = [
        name
        for name, value in vars(scrape).items()
        if not name.startswith("_") and id(value) in fetcher_objects
    ]
    assert leaked == []
