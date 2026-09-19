from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from football_edge.collector import ContractViolation, fetch_text
from football_edge.collectors import news as news_module
from football_edge.collectors.news import (
    AjansporAdapter,
    GoogleNewsAdapter,
    NewsCollectResult,
    NewsItem,
    collect_news,
    enabled_adapters,
    news_observation,
)
from football_edge.sources import SourceBlocked, load_sources, robots_for
from tests.fake_obs_db import FakeObservationDb
from tests.fake_sources import fake_source, write_robots

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
# SENTETİK — gerçek Google News içeriği DEĞİL (review Important #3, 2026-09-19). Önceki
# `googlenews-tr.xml` canlı bir fetch'ti; o path'in robots.txt'i HER user-agent için
# `Disallow` ölçüldü (protego ile doğrulandı, aşağıdaki "robots ölçümü" bölümüne bkz.) —
# o fetch'in kendisi robots ihlaliydi ve commit'lemek yeniden-yayın olurdu (spec §3.2/4,
# feed'in kendi <copyright>'ı). Bu dosya elle üretildi: aynı RSS 2.0 şekli, sıfır gerçek
# içerik, sıfır gerçek URL (`example.test`, hiç çözümlenmez).
GOOGLE_FIXTURE = Path("tests/fixtures/news/rss-sample.xml")
# `/sitemap/news`ten (ölçüldü 2026-09-19) alınan GERÇEK 1000 <url> bloğunun ilk 40'ı.
AJANSSPOR_URLSET_FIXTURE = Path("tests/fixtures/news/ajansspor-sitemap-urlset.xml")
# `/sitemap`ten (ölçüldü 2026-09-19) alınan GERÇEK yanıt — bir sitemap INDEX'i, urlset değil.
# `declared_paths`teki `/sitemap.xml` (config/sources.yaml, salt okunur) canlıda 404 veriyor;
# robots.txt'in kendi `Sitemap:` satırları `/sitemap` ve `/sitemap/news`dir — bkz. task-8-report.md.
AJANSSPOR_INDEX_FIXTURE = Path("tests/fixtures/news/ajansspor-sitemap.xml")


# ---------------------------------------------------------------------------
# Google News (RSS) — feed'in kendisi 'enabled: false' ama adaptör yine de yazılır
# ve test edilir (Ruling B): kapalı bir anahtarın ARDINDAKİ kodun çalıştığını bilmeden
# "kapalı, güvenli" denemez.
# ---------------------------------------------------------------------------


# `contract` İŞARETLENMEDİ (review Important #3'ün doğal sonucu, kendi kararım): `contract`
# marker'ı "kaydedilmiş fixture üzerinde tazelik/şema sözleşmesi" — yani CANLI gerçekliğin
# hâlâ bu şekli ürettiğini doğrulayan testler içindir (footystats'ın 3'ü gibi). Google News
# artık HİÇ yeniden ölçülemiyor (robots.txt her user-agent'ı reddediyor) — bu test yalnız
# BİZİM UYDURDUĞUMUZ bir şekle karşı ayrıştırıcıyı sınıyor, "bugünün gerçek yükü hâlâ
# doğru mu" sorusuna cevap VEREMEZ. `contract` etiketi burada YANILTICI olurdu.
def test_google_adapter_parses_the_feed() -> None:
    items = GoogleNewsAdapter().parse(GOOGLE_FIXTURE.read_text(encoding="utf-8"), now=NOW)
    assert len(items) >= 20
    assert all(item.title and item.url for item in items)


def test_empty_feed_raises() -> None:
    """Kırılan bir ayrıştırıcı boş liste dönerse iddiasız bir turdan ayırt edilemez."""
    with pytest.raises(ContractViolation):
        GoogleNewsAdapter().parse("<rss><channel></channel></rss>", now=NOW)


def test_entity_expansion_attack_is_refused_not_expanded() -> None:
    """Besleme gövdesini biz yazmıyoruz. Stdlib ElementTree bunu genişletmeye ÇALIŞIR.

    `defusedxml` varlık tanımını reddeder ve ContractViolation'a dönüşür; sertleştirilmemiş
    bir ayrıştırıcı burada belleği tüketir ve toplayıcı turu hiç bitmez.
    """
    bomb = (
        "<?xml version='1.0'?><!DOCTYPE rss ["
        "<!ENTITY a 'aaaaaaaaaa'>"
        "<!ENTITY b '&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;'>"
        "<!ENTITY c '&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;'>"
        "]><rss><channel><item><title>&c;</title><link>x</link></item></channel></rss>"
    )
    with pytest.raises(ContractViolation):
        GoogleNewsAdapter().parse(bomb, now=NOW)


# ---------------------------------------------------------------------------
# Ajansspor (sitemap) — muhtemel 11 / mac / oyuncu / lig yolları robots'ça KAPALI (ölçüldü);
# yalnız /haber/ altındaki makale yolları açık. `declared_paths` bunu STATİK sorar,
# `guard_path` her makale URL'sini fetch anında AYRI AYRI sorar — aşağıdaki
# `test_article_url_is_checked_against_robots_at_fetch_time` ikincisini kanıtlar.
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_ajansspor_adapter_parses_real_article_urls_from_the_urlset() -> None:
    """40 gerçek <url> bloğu (ölçüldü 2026-09-19, canlı `/sitemap/news` yanıtından, ilk 40)."""
    body = AJANSSPOR_URLSET_FIXTURE.read_text(encoding="utf-8")
    items = AjansporAdapter().parse(body, now=NOW)
    assert len(items) >= 20
    assert all(item.title for item in items)
    assert all(item.url.startswith("https://ajansspor.com/haber/") for item in items)
    assert all(item.source_id == "ajansspor" for item in items)


def test_ajansspor_adapter_does_not_count_image_urls_as_news_items() -> None:
    """Gerçek besleme HER <url> için bir <image:image><image:loc> TAŞIR (ölçüldü: 1000/1000,
    makale <loc> ile TAM AYNI SAYIDA). Ad alanı önekleri farklı olsa da ikisi de aynı
    şekilde biter; yalnız etiket ADINA bakan kör bir tarama (`root.iter()` + "tag'i 'loc' mu")
    ikisini ayıramaz ve fotoğraf CDN URL'sini de "haber" sayıp toplamı ikiye katlar.
    Doğrudan-çocuk gezinmesi `<image:loc>`u (`<url>`in İKİ seviye altındaki bir torun) hiç
    ziyaret etmemeli — yalnız BİR öğe dönmeli, ikisi değil."""
    body = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9' "
        "xmlns:news='http://www.google.com/schemas/sitemap-news/0.9' "
        "xmlns:image='http://www.google.com/schemas/sitemap-image/1.1'>"
        "<url>"
        "<loc>https://ajansspor.com/haber/ornek-haber-1</loc>"
        "<news:news><news:title><![CDATA[Örnek Haber]]></news:title>"
        "<news:publication_date>2026-09-19T10:00:00+03:00</news:publication_date></news:news>"
        "<image:image><image:loc>https://cdn.ajansspor.com/photo/1.jpg</image:loc></image:image>"
        "</url>"
        "</urlset>"
    )
    items = AjansporAdapter().parse(body, now=NOW)
    assert len(items) == 1
    assert items[0].url == "https://ajansspor.com/haber/ornek-haber-1"
    assert items[0].title == "Örnek Haber"


def test_ajansspor_adapter_filters_disallowed_paths_as_defense_in_depth() -> None:
    """robots ölçümü (config/sources.yaml notu): /mac/, /lineup/, /oyuncu/, /lig/ DISALLOW.

    Asıl BAĞLAYICI zorlama `fetch_text` içindeki `guard_path`tir — bkz.
    `test_article_url_is_checked_against_robots_at_fetch_time`. Bu test yalnız KOLAYLIK
    katmanını sınar: sitemap sürükleyip böyle bir yol taşırsa toplayıcı onu hiç NewsItem'a
    çevirmemeli — istek atılmadan önceki ikinci, bağımsız bir süzgeç.
    """
    body = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9' "
        "xmlns:news='http://www.google.com/schemas/sitemap-news/0.9'>"
        # Yalnız İZİNLİ olan `_news_published_at`e ULAŞIR (disallow filtresi ÖNCE çalışır,
        # bkz. `_sitemap_item`); diğer dördü path'te elenir, tarihe hiç bakılmaz.
        "<url><loc>https://ajansspor.com/haber/izinli-haber</loc>"
        "<news:news><news:publication_date>2026-09-19T10:00:00+03:00</news:publication_date>"
        "</news:news></url>"
        "<url><loc>https://ajansspor.com/mac/12345</loc></url>"
        "<url><loc>https://ajansspor.com/lineup/galatasaray</loc></url>"
        "<url><loc>https://ajansspor.com/oyuncu/bir-oyuncu</loc></url>"
        "<url><loc>https://ajansspor.com/lig/super-lig</loc></url>"
        "</urlset>"
    )
    items = AjansporAdapter().parse(body, now=NOW)
    assert [item.url for item in items] == ["https://ajansspor.com/haber/izinli-haber"]


def test_ajansspor_adapter_raises_on_sitemap_index_rather_than_returning_empty() -> None:
    """Ölçüldü (2026-09-19): `config/sources.yaml`deki `declared_paths` — `/sitemap.xml` —
    canlıda 404 veriyor. robots.txt'in KENDİ `Sitemap:` satırları `/sitemap` (bu fixture —
    bir INDEX döner) ve `/sitemap/news` (yukarıdaki urlset testi). Bir INDEX sessizce boş
    listeye düşseydi bu, ayrıştırıcının KIRILDIĞI durumdan (sayfa şekli değişti) AYIRT
    EDİLEMEZDİ — `assert_schema`'nın "boş liste iddiasızlıktan ayrılamaz" ilkesiyle aynı sınıf.
    """
    body = AJANSSPOR_INDEX_FIXTURE.read_text(encoding="utf-8")
    with pytest.raises(ContractViolation, match="INDEX"):
        AjansporAdapter().parse(body, now=NOW)


def test_ajansspor_empty_urlset_raises() -> None:
    with pytest.raises(ContractViolation):
        AjansporAdapter().parse(
            "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'></urlset>", now=NOW
        )


def test_ajansspor_entity_expansion_attack_is_refused_not_expanded() -> None:
    """`AjansporAdapter` KENDİ try/except'iyle `fromstring` çağırır — Google'ın besleme
    yolunun korumalı olması bu AYRI kod yolunun da korumalı olduğunu KANITLAMAZ."""
    bomb = (
        "<?xml version='1.0'?><!DOCTYPE urlset ["
        "<!ENTITY a 'aaaaaaaaaa'>"
        "<!ENTITY b '&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;'>"
        "<!ENTITY c '&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;'>"
        "]><urlset><url><loc>&c;</loc></url></urlset>"
    )
    with pytest.raises(ContractViolation):
        AjansporAdapter().parse(bomb, now=NOW)


# ---------------------------------------------------------------------------
# Kayıt defteri kablolaması
# ---------------------------------------------------------------------------


def test_google_news_is_disabled_in_the_registry() -> None:
    """Ruling B: feed'in kendi copyright'ı ticari kullanımı yasaklıyor. Varsayılan KAPALI."""
    registry = load_sources(Path("config/sources.yaml"))
    google = next(entry for entry in registry if entry.id == "googlenews")
    assert google.enabled is False
    assert "non-commercial" in google.note


def test_enabled_adapters_excludes_disabled_sources() -> None:
    """Yalnız DIŞLAMAYI değil DAHİL ETMEYİ de kanıtlar: `enabled_adapters` her zaman `()`
    dönseydi bu test yine geçerdi (boş demet "googlenews" de İÇERMEZ) — kırılamayan bir
    iddia olurdu. `ajansspor` (enabled: true, config/sources.yaml) varlığı bu boşluğu kapatır.
    """
    registry = load_sources(Path("config/sources.yaml"))
    adapters = enabled_adapters(registry)
    source_ids = tuple(adapter.source_id for adapter in adapters)
    assert "googlenews" not in source_ids
    assert "ajansspor" in source_ids


def test_article_url_is_checked_against_robots_at_fetch_time(tmp_path: Path) -> None:
    """`declared_paths` statik yolları kapıda sorar; DİNAMİK makale URL'si burada sorulur.

    Ajansspor `/mac/` ve `/lineup/` kapatıyor. Sitemap'ten böyle bir URL gelirse istek
    ATILMAMALI — robots'a uymak, listeyi kimin ürettiğine bağlı olamaz.
    """
    write_robots(tmp_path, "ajansspor", "User-agent: *\nDisallow: /mac/\nDisallow: /lineup/\n")
    source = fake_source(id="ajansspor")
    parser = robots_for(source, tmp_path)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text="<html/>", headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceBlocked):
            fetch_text(client, source, "/mac/12345", parser, expect="text/html")
        fetch_text(client, source, "/futbol/haber-1", parser, expect="text/html")

    assert calls == ["https://example.test/futbol/haber-1"]


# ---------------------------------------------------------------------------
# Observation eşlemesi
# ---------------------------------------------------------------------------


def test_observation_key_is_the_article_url() -> None:
    items = GoogleNewsAdapter().parse(GOOGLE_FIXTURE.read_text(encoding="utf-8"), now=NOW)
    entry = news_observation(items[0])
    assert entry.entity_kind == "news"
    assert entry.entity_key == items[0].url
    # Ham içerik YENİDEN YAYINLANMAZ (spec §3.2/4): yalnız başlık ve bağlantı saklanır.
    assert set(entry.payload) == {"title", "url", "published_at", "source_id"}


def test_news_observation_stamps_observed_at_from_the_items_own_published_at() -> None:
    """R23: `assert_fresh` KENDİ `now()`ıyla damgalanan gözlemlerde ÇAĞRILAMAZ — her zaman
    doğru olan bir iddiadır. Haber öğeleri KAYNAK-VERİLİ bir zaman damgası taşır (RSS
    `pubDate`, sitemap `news:publication_date`); bu test o tasarım kararını kodda sabitler:
    `observed_at`, `now` DEĞİL öğenin KENDİ `published_at`ı olmalı — aksi hâlde bu gözlemler
    üzerinde bir gün çağrılacak `assert_fresh` sessizce anlamsızlaşır (bkz. collector.py
    docstring'i, madde 1).
    """
    items = GoogleNewsAdapter().parse(GOOGLE_FIXTURE.read_text(encoding="utf-8"), now=NOW)
    entry = news_observation(items[0])
    assert entry.observed_at == items[0].published_at
    assert entry.observed_at != NOW


# ---------------------------------------------------------------------------
# Review Important #1 — üçüncü-taraf bir tarih timezone-NAIVE olabilir ve `assert_fresh`i
# (bu görevin var olma nedenini) kendisi kırabilir. RFC 2822 "-0000" = "bilinmeyen bölge" =
# NAIVE (ölçüldü: `parsedate_to_datetime` tzinfo=None döner). Ofsetsiz ISO 8601 de aynı.
# ---------------------------------------------------------------------------


def test_rss_naive_pubdate_is_normalized_to_timezone_aware() -> None:
    """`-0000`: RFC 2822'de "kaynak zaman dilimini bilmiyor" anlamına gelir — `+0000`
    (bilinen UTC) DEĞİLDİR. `email.utils.parsedate_to_datetime` bu durumda NAIVE bir
    `datetime` döner. `assert_fresh` `now() - value` yapar; naive-aware çıkarma `TypeError`
    fırlatır — üçüncü tarafın kontrol ettiği BİR ALANIN çökertebileceği, bu görevin var
    olma nedeni olan tam o iddia."""
    body = (
        "<rss version='2.0'><channel><item>"
        "<title>Test</title><link>https://example.test/naive-rfc2822</link>"
        "<pubDate>Fri, 18 Sep 2026 17:22:52 -0000</pubDate>"
        "</item></channel></rss>"
    )
    items = GoogleNewsAdapter().parse(body, now=NOW)
    assert items[0].published_at.tzinfo is not None
    assert items[0].published_at == datetime(2026, 9, 18, 17, 22, 52, tzinfo=UTC)


def test_ajansspor_naive_publication_date_is_normalized_to_timezone_aware() -> None:
    """Ofsetsiz ISO 8601 (`2026-09-19T13:33:50`, sonda `+03:00`/`Z` yok) `datetime.
    fromisoformat`ten NAIVE döner — RSS'teki `-0000` ile aynı arıza sınıfı, farklı kaynak."""
    body = (
        "<?xml version='1.0'?>"
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9' "
        "xmlns:news='http://www.google.com/schemas/sitemap-news/0.9'>"
        "<url><loc>https://ajansspor.com/haber/naive-iso</loc>"
        "<news:news><news:title>X</news:title>"
        "<news:publication_date>2026-09-19T13:33:50</news:publication_date>"
        "</news:news></url></urlset>"
    )
    items = AjansporAdapter().parse(body, now=NOW)
    assert items[0].published_at.tzinfo is not None
    assert items[0].published_at == datetime(2026, 9, 19, 13, 33, 50, tzinfo=UTC)


def test_ajansspor_offset_publication_date_is_converted_to_utc() -> None:
    """AÇIK bir ofset (`+03:00`, gerçek Ajansspor besleme deseni) NAIVE değildir — ama
    `ledger.py:canonical_timestamp`teki desenle TUTARLI olmak için SAYISAL olarak UTC'ye
    çevrilir (yalnız etiketlenmez). 13:33:50+03:00 == 10:33:50 UTC.

    `tzinfo`i AÇIKÇA `UTC`ye eşitliyor — yalnız DEĞER eşitliği (`==`) YETMEZ: Python'da
    aware-datetime `==` MUTLAK ANA göre karşılaştırır, `13:33:50+03:00` zaten
    `10:33:50+00:00`ya DEĞER olarak eşittir (`astimezone` hiç ÇAĞRILMASA bile) — ölçüldü,
    ilk yazımda bu test `astimezone(UTC)` hiç yokken de YEŞİLDİ (kırılamayan bir iddiaydı).
    `tzinfo == UTC` normalizasyonun GERÇEKTEN olduğunu kanıtlıyor."""
    body = (
        "<?xml version='1.0'?>"
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9' "
        "xmlns:news='http://www.google.com/schemas/sitemap-news/0.9'>"
        "<url><loc>https://ajansspor.com/haber/offset-iso</loc>"
        "<news:news><news:title>X</news:title>"
        "<news:publication_date>2026-09-19T13:33:50+03:00</news:publication_date>"
        "</news:news></url></urlset>"
    )
    items = AjansporAdapter().parse(body, now=NOW)
    assert items[0].published_at == datetime(2026, 9, 19, 10, 33, 50, tzinfo=UTC)
    assert items[0].published_at.tzinfo == UTC


# ---------------------------------------------------------------------------
# Review Important #2 — eksik bir kaynak tarihi sessizce `now`a düşerse, KAYNAK-VERİLİ bir
# gözlem KENDİ-DAMGALI türe döner (R23'ün yasakladığı tam durum) — hiçbir bayrak, hiçbir
# ayırt edici değer olmadan. Sitemap: `news:publication_date` ZORUNLU alan, eksikliği/
# kırıklığı bir ŞEMA KIRIĞI — `raise` (eksik `<loc>` ile aynı muamele). RSS: `<pubDate>`
# OPSİYONEL (RSS 2.0 spec) — madde ATILMAZ, ama `NewsItem.published_at_is_source_provided`
# `False` işaretlenir ki bir çağıran `assert_fresh`i yalnız GERÇEKTEN kaynaklı öğelerde
# çalıştırabilsin.
# ---------------------------------------------------------------------------


def test_ajansspor_missing_publication_date_raises() -> None:
    """`<news:news>` var ama `<news:publication_date>` yok — ZORUNLU alan eksik."""
    body = (
        "<?xml version='1.0'?>"
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9' "
        "xmlns:news='http://www.google.com/schemas/sitemap-news/0.9'>"
        "<url><loc>https://ajansspor.com/haber/tarihsiz</loc>"
        "<news:news><news:title>X</news:title></news:news></url></urlset>"
    )
    with pytest.raises(ContractViolation):
        AjansporAdapter().parse(body, now=NOW)


def test_ajansspor_missing_news_node_raises() -> None:
    """`<news:news>` düğümünün KENDİSİ hiç yok — aynı sınıf, aynı muamele."""
    body = (
        "<?xml version='1.0'?>"
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
        "<url><loc>https://ajansspor.com/haber/newssiz</loc></url></urlset>"
    )
    with pytest.raises(ContractViolation):
        AjansporAdapter().parse(body, now=NOW)


def test_ajansspor_unparseable_publication_date_raises() -> None:
    """Alan VAR ama içeriği tarih değil — eksiklikle AYNI güvensizlik, aynı muamele."""
    body = (
        "<?xml version='1.0'?>"
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9' "
        "xmlns:news='http://www.google.com/schemas/sitemap-news/0.9'>"
        "<url><loc>https://ajansspor.com/haber/bozuk-tarih</loc>"
        "<news:news><news:title>X</news:title>"
        "<news:publication_date>bu-bir-tarih-degil</news:publication_date>"
        "</news:news></url></urlset>"
    )
    with pytest.raises(ContractViolation):
        AjansporAdapter().parse(body, now=NOW)


def test_rss_missing_pubdate_is_flagged_not_source_provided() -> None:
    body = (
        "<rss version='2.0'><channel><item>"
        "<title>Tarihsiz</title><link>https://example.test/tarihsiz</link>"
        "</item></channel></rss>"
    )
    items = GoogleNewsAdapter().parse(body, now=NOW)
    assert items[0].published_at_is_source_provided is False
    assert items[0].published_at == NOW


def test_rss_unparseable_pubdate_is_flagged_not_source_provided() -> None:
    body = (
        "<rss version='2.0'><channel><item>"
        "<title>Bozuk</title><link>https://example.test/bozuk-tarih</link>"
        "<pubDate>bu-bir-tarih-degil</pubDate>"
        "</item></channel></rss>"
    )
    items = GoogleNewsAdapter().parse(body, now=NOW)
    assert items[0].published_at_is_source_provided is False
    assert items[0].published_at == NOW


def test_rss_item_with_real_pubdate_is_flagged_source_provided() -> None:
    items = GoogleNewsAdapter().parse(GOOGLE_FIXTURE.read_text(encoding="utf-8"), now=NOW)
    assert items[0].published_at_is_source_provided is True


def test_ajansspor_item_is_always_flagged_source_provided() -> None:
    """Ajansspor için ASLA `now`a düşülmez (Important #2) — bayrak varsayılan `True`dan
    hiç sapmaz; sapsaydı zaten yukarıdaki `raise` testlerinden biri yakalardı."""
    body = AJANSSPOR_URLSET_FIXTURE.read_text(encoding="utf-8")
    items = AjansporAdapter().parse(body, now=NOW)
    assert all(item.published_at_is_source_provided for item in items)


def test_news_observation_payload_excludes_provenance_flag() -> None:
    """`published_at_is_source_provided` YALNIZ `NewsItem` üzerinde yaşar — `Observation.
    payload`a SIZMAZ (spec §3.2/4: yalnız başlık+bağlantı; anahtar seti sabit)."""
    item = NewsItem(
        title="X",
        url="https://example.test/x",
        published_at=NOW,
        source_id="googlenews",
        published_at_is_source_provided=False,
    )
    entry = news_observation(item)
    assert set(entry.payload) == {"title", "url", "published_at", "source_id"}


# ---------------------------------------------------------------------------
# Review Minor #5 (terfi ettirildi) — RSS yolu Ajansspor'un tam düzelttiği asimetriyi
# taşıyordu: `root.iter("item")` ÖZYİNELİ, kök hiç doğrulanmıyordu.
# ---------------------------------------------------------------------------


def test_rss_rejects_non_rss_root() -> None:
    """Kök `rss` değilse (ör. yanlışlıkla bir Atom besleme ya da başka bir belge verildi)
    — içinde iyi biçimli bir <item> olsa bile REDDEDİLMELİ. `root.iter("item")` kökü hiç
    sormazdı; bu test tam o eksik doğrulamayı hedefler (aşağıdaki mutasyona bkz.)."""
    body = "<feed><item><title>X</title><link>https://example.test/x</link></item></feed>"
    with pytest.raises(ContractViolation):
        GoogleNewsAdapter().parse(body, now=NOW)


def test_rss_ignores_item_tag_outside_channel() -> None:
    """Simetri: Ajansspor'daki `<image:loc>` çakışmasıyla aynı İLKE — özyineli bir tarama
    `<channel>`in DIŞINDAKİ bir `<item>`-benzeri düğümü de toplardı. Doğrudan-çocuk
    gezinmesi yalnız GERÇEK `<channel>` içeriğini görür."""
    body = (
        "<rss version='2.0'>"
        "<channel><item><title>Gerçek</title><link>https://example.test/gercek</link></item></channel>"
        "<decoy><item><title>Sahte</title><link>https://example.test/sahte</link></item></decoy>"
        "</rss>"
    )
    items = GoogleNewsAdapter().parse(body, now=NOW)
    assert len(items) == 1
    assert items[0].url == "https://example.test/gercek"


# ---------------------------------------------------------------------------
# `collect_news` kablolaması (M1/M6, merge adımı). `FakeObservationDb`
# (tests/fake_obs_db.py) yeterli: `collect_news` yalnız `source_observations`e yazar,
# `matches` tablosuna hiç dokunmaz.
# ---------------------------------------------------------------------------


def _sources_yaml(tmp_path: Path, *, googlenews_enabled: bool = False) -> Path:
    # SIRA KASITLI: googlenews ÖNCE, ajansspor SONRA (Minor #5, review, promoted).
    # `enabled_adapters()` YAML sırasını korur; ajansspor önce gelseydi
    # `test_collect_news_an_unmapped_adapter_path_isolates_only_that_source` yalnız
    # "istisna dışarı sızmıyor"u kanıtlardı (ajansspor googlenews'e ULAŞMADAN ÖNCE zaten
    # yazılmış/commit edilmiş olurdu) — docstring'in iddiası olan "SONRAKİ sağlam adaptör
    # de çalışır"ı DEĞİL. Bu sıra o iddiayı gerçekten sınar.
    path = tmp_path / "sources.yaml"
    path.write_text(
        f"""
sources:
  - id: googlenews
    base_url: https://news.google.test
    user_agent: football-edge-test/0.1
    crawl_delay_seconds: 0.0
    robots_verified_at: 2026-09-19
    declared_paths: []
    enabled: {"true" if googlenews_enabled else "false"}
    access_basis: robots
    terms_url: ''
    note: ''
  - id: ajansspor
    base_url: https://ajansspor.test
    user_agent: football-edge-test/0.1
    crawl_delay_seconds: 0.0
    robots_verified_at: 2026-09-19
    declared_paths: ['/sitemap', '/sitemap/news']
    enabled: true
    access_basis: robots
    terms_url: ''
    note: ''
""",
        encoding="utf-8",
    )
    return path


def _ajansspor_urlset(entries: list[tuple[str, str]]) -> str:
    """`entries`: (url yolu, ISO news:publication_date) çiftleri."""
    blocks = "".join(
        f"<url><loc>https://ajansspor.test/haber/{slug}</loc>"
        f"<news:news><news:title>X</news:title>"
        f"<news:publication_date>{published}</news:publication_date>"
        f"</news:news></url>"
        for slug, published in entries
    )
    return (
        "<?xml version='1.0'?>"
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9' "
        "xmlns:news='http://www.google.com/schemas/sitemap-news/0.9'>" + blocks + "</urlset>"
    )


def _rss_body(entries: list[tuple[str, str | None]]) -> str:
    """`entries`: (url yolu, RFC2822 pubDate ya da None [pubDate hiç YAZILMAZ]) çiftleri."""
    items = "".join(
        f"<item><title>X</title><link>https://news.google.test/{slug}</link>"
        + (f"<pubDate>{pub_date}</pubDate>" if pub_date else "")
        + "</item>"
        for slug, pub_date in entries
    )
    return f"<rss version='2.0'><channel>{items}</channel></rss>"


def _news_handler(bodies: dict[str, str]) -> object:
    def handler(request: httpx.Request) -> httpx.Response:
        for host, body in bodies.items():
            if host in str(request.url):
                return httpx.Response(200, text=body, headers={"content-type": "application/xml"})
        return httpx.Response(404, text="not found")

    return handler


def test_collect_news_writes_ajansspor_items_and_checks_freshness(tmp_path: Path) -> None:
    sources_path = _sources_yaml(tmp_path)
    write_robots(tmp_path, "ajansspor", "")
    fresh = (NOW - timedelta(hours=2)).isoformat()
    body = _ajansspor_urlset([("taze-haber", fresh)])
    client = httpx.Client(
        transport=httpx.MockTransport(_news_handler({"ajansspor.test": body}))  # type: ignore[arg-type]
    )
    db = FakeObservationDb()

    result = collect_news(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert result == NewsCollectResult(written=1, self_stamped=0, failed_sources=())
    assert len(db.rows) == 1


def test_collect_news_isolates_and_reports_a_stale_source_provided_batch(tmp_path: Path) -> None:
    """Kaynak-verili ama BAYAT bir haber: `assert_fresh` KIRILMALI — kendi-damgalı hiçbir
    öğe yok, bu yüzden bu tamamen sıradan bir tazelik ihlalidir (M6'nın istisnası değil)."""
    sources_path = _sources_yaml(tmp_path)
    write_robots(tmp_path, "ajansspor", "")
    stale = (NOW - timedelta(days=30)).isoformat()
    body = _ajansspor_urlset([("bayat-haber", stale)])
    client = httpx.Client(
        transport=httpx.MockTransport(_news_handler({"ajansspor.test": body}))  # type: ignore[arg-type]
    )
    db = FakeObservationDb()

    result = collect_news(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert result == NewsCollectResult(written=0, self_stamped=0, failed_sources=("ajansspor",))
    assert db.rows == []


def test_collect_news_writes_and_counts_self_stamped_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M6: kaynak tarih VERMEDİĞİ (RSS `pubDate` yok) için `now`a düşen bir öğe SESSİZCE
    yutulmaz — yazılır VE `self_stamped` sayacına eklenir."""
    # `_ARTICLE_PATHS` googlenews'i taşımıyor (`enabled: false` olduğu sürece bilinçli
    # olarak, bkz. news.py). Yalnız BU testte, self-stamped davranışını `collect_news`
    # ÜZERİNDEN sınamak için geçici olarak bir yol ekleniyor (gerçek, ölçülmüş yol —
    # task-8-report.md — ama canlıya hiç istek atılmıyor, MockTransport devrede).
    monkeypatch.setitem(
        news_module._ARTICLE_PATHS, "googlenews", "/rss/search?q=Galatasaray&hl=tr&gl=TR&ceid=TR:tr"
    )
    sources_path = _sources_yaml(tmp_path, googlenews_enabled=True)
    write_robots(tmp_path, "ajansspor", "")
    write_robots(tmp_path, "googlenews", "")
    ajansspor_body = _ajansspor_urlset([("taze-haber", (NOW - timedelta(hours=1)).isoformat())])
    rss_body = _rss_body([("tarihsiz-haber", None)])
    client = httpx.Client(
        transport=httpx.MockTransport(  # type: ignore[arg-type]
            _news_handler({"ajansspor.test": ajansspor_body, "news.google.test": rss_body})
        )
    )
    db = FakeObservationDb()

    result = collect_news(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert result == NewsCollectResult(written=2, self_stamped=1, failed_sources=())


def test_collect_news_self_stamped_items_do_not_mask_a_stale_source_provided_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M6'nın ÇEKİRDEK kanıtı (R23): AYNI feed'de biri BAYAT kaynak-verili, biri kendi-damgalı
    iki öğe olsun. Kendi-damgalı öğe `observed_at=now` taşıdığı için `assert_fresh` TÜM
    öğeler üzerinde çağrılsaydı `max(...)` `now`a sürüklenir ve BAYAT öğe SESSİZCE geçerdi —
    tam R23'ün uyardığı "kendi-damgalı gözlem gerçek tazeliği MASKELER" durumu. Doğru kod
    `assert_fresh`i YALNIZ kaynak-verili alt kümede çalıştırır: bayat öğe kendi başına
    `max_age`i aşar ve iddia KIRILIR — kaynak `failed_sources`e düşer, HİÇBİR ŞEY yazılmaz
    (kendi-damgalı öğe dahil — batch bölünmez, bkz. `collect_news` docstring'i)."""
    monkeypatch.setitem(
        news_module._ARTICLE_PATHS, "googlenews", "/rss/search?q=Galatasaray&hl=tr&gl=TR&ceid=TR:tr"
    )
    sources_path = _sources_yaml(tmp_path, googlenews_enabled=True)
    write_robots(tmp_path, "ajansspor", "")
    write_robots(tmp_path, "googlenews", "")
    stale_pub_date = (NOW - timedelta(days=30)).strftime("%a, %d %b %Y %H:%M:%S +0000")
    rss_body = _rss_body([("bayat-kaynakli", stale_pub_date), ("tarihsiz-kendi-damgali", None)])
    client = httpx.Client(
        transport=httpx.MockTransport(  # type: ignore[arg-type]
            _news_handler({"news.google.test": rss_body})
        )
    )
    db = FakeObservationDb()
    configured_sources = load_sources(sources_path)
    assert {entry.id for entry in configured_sources if entry.enabled} == {
        "ajansspor",
        "googlenews",
    }

    result = collect_news(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
        max_age=timedelta(days=2),
    )

    # ajansspor'un kendi fetch'i bu testte 404 döner (_news_handler eşleşmiyor) — o da
    # başarısız sayılır; asıl iddia googlenews'in KENDİSİ hakkında.
    assert "googlenews" in result.failed_sources, (
        f"bayat kaynak-verili öğe kendi-damgalı öğe tarafından MASKELENMİŞ olabilir: {result}"
    )
    assert result.written == 0
    assert result.self_stamped == 0


def test_collect_news_an_unmapped_adapter_path_isolates_only_that_source(tmp_path: Path) -> None:
    """`_ARTICLE_PATHS`te YOK bir adaptör (googlenews, bilinçli olarak eşlemesiz) bir
    wiring hatasıdır — ama bu döngü ADAPTÖR başına izole eder (`collect_footystats`teki
    lig izolasyonuyla aynı ilke). `_sources_yaml` googlenews'i BİLİNÇLİ olarak ÖNCE listeler
    (Minor #5, review, promoted): ajansspor önce gelseydi bu test yalnız "istisna dışarı
    sızmıyor"u kanıtlardı — ajansspor googlenews'e hiç ULAŞILMADAN ÖNCE zaten yazılıp commit
    edilmiş olurdu. Googlenews ÖNCE gelince asıl iddia sınanır: eşlemesiz (ve başarısız)
    ÖNCEKİ bir adaptör, SONRAKİ sağlam ajansspor'un çalışmasını/yazmasını ENGELLEMEMELİ."""
    sources_path = _sources_yaml(tmp_path, googlenews_enabled=True)
    write_robots(tmp_path, "ajansspor", "")
    write_robots(tmp_path, "googlenews", "")
    ajansspor_body = _ajansspor_urlset([("taze-haber", (NOW - timedelta(hours=1)).isoformat())])
    client = httpx.Client(
        transport=httpx.MockTransport(  # type: ignore[arg-type]
            _news_handler({"ajansspor.test": ajansspor_body})
        )
    )
    db = FakeObservationDb()

    result = collect_news(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert result.written == 1, f"eşlemesiz googlenews, sağlam ajansspor'u da götürdü: {result}"
    assert result.failed_sources == ("googlenews",)


def test_collect_news_does_not_count_a_batch_whose_commit_fails(tmp_path: Path) -> None:
    """Minor #4 (review, promoted) — Faz 0'ın G1'iyle AYNI sınıf arıza: "not failed" ile
    "durably written" aynı şey değildir. `commit()` düşerse satır kalıcı DEĞİLDİR;
    `written`i önceden artırmak hiç kalıcı olmamış veri için "N yeni gözlem" basmak demektir.
    """
    sources_path = _sources_yaml(tmp_path)
    write_robots(tmp_path, "ajansspor", "")
    body = _ajansspor_urlset([("taze-haber", (NOW - timedelta(hours=1)).isoformat())])
    client = httpx.Client(
        transport=httpx.MockTransport(_news_handler({"ajansspor.test": body}))  # type: ignore[arg-type]
    )
    db = FakeObservationDb(commit_fails=lambda _db: True)

    result = collect_news(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert result.written == 0
    assert result.self_stamped == 0
    assert result.failed_sources == ("ajansspor",)
    assert db.rollbacks == 1
