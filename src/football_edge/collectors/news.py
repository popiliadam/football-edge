from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit
from xml.etree.ElementTree import Element, ParseError

import httpx
import psycopg
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring

from football_edge.collector import ContractViolation, Observation, assert_fresh, fetch_text
from football_edge.observations import write_observations
from football_edge.sources import Source, enabled_sources, load_sources, robots_for

LOGGER = logging.getLogger("football_edge.collectors.news")

# Google News RSS feed'inin KENDİ <copyright> metni (alıntı; ölçüldü 2026-09-19, canlı feed'e
# karşı). O ölçümün ARTEFAKTI — fetch edilen gövdenin kendisi — tests/fixtures/news/'ta ARTIK
# YOK: review Important #3, o path'in robots.txt'i HER user-agent için Disallow ölçüldü
# (protego ile doğrulandı, bkz. task-8-report.md), fetch'in kendisi ihlaldi ve commit'lemek
# yeniden-yayın olurdu (spec §3.2/4). Bu ALINTI kalıyor — bir telif bildirimini UYUM
# GEREKÇESİ olarak alıntılamak eserin yeniden yayını değildir:
#   "This XML feed is made available solely for the purpose of rendering Google News results
#    within a personal feed reader for personal, non-commercial use. Any other use of the
#    feed is expressly prohibited."
# Spec §3.1 bu kaynağı "lisanslı yüzey" diye sınıflıyordu; feed'in kendisi aksini söylüyor.
# Adaptör yine de yazılır (Ruling B — arayüz sağlayıcıdan bağımsızdır) ama
# `config/sources.yaml`da `enabled: false` ve aynı alıntı orada da birebir durur; ticari karar
# operatördedir. (İlk taslak bu kararı docs/DEFERRED.md §7'ye bağlıyordu — ölçüldü, o bölüm
# yalnız Club-Football-Match-Data lisans zincirinden bahsediyor, Google News'ten değil; yanlış
# çapraz-referans buradan kaldırıldı. Tek doğrulanmış kaynak `config/sources.yaml`'ın kendi notu.)
GOOGLE_NEWS_LICENCE = "personal, non-commercial use only — see config/sources.yaml"

# Ajansspor robots.txt (ölçüldü 2026-09-19, config/robots/ajansspor.txt): /lineup/*, /mac/,
# /oyuncu/, /lig/ ve *rsc=* DISALLOW — muhtemel 11 ve yapısal sayfalar ALINMAZ. Bu tuple yalnız
# KOLAYLIK/ikinci bir süzgeçtir (bkz. AjansporAdapter docstring'i); asıl BAĞLAYICI zorlama
# `fetch_text` içindeki `guard_path`tir.
_AJANSSPOR_DISALLOWED_PREFIXES = ("/lineup/", "/mac/", "/oyuncu/", "/lig/")


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    published_at: datetime
    source_id: str
    # KAYNAK mı SAĞLADI yoksa toplayıcı `now()`u mu yerine geçirdi? (review Important #2).
    # RSS `<pubDate>` OPSİYONELDİR (RSS 2.0 spec); eksik/bozuksa `published_at` `now`a düşer —
    # bu SESSİZCE kaynak-verili bir gözlemi KENDİ-DAMGALI türe çevirir (R23'ün yasakladığı tam
    # durum) ve bu bayrak OLMADAN iki durum AYIRT EDİLEMEZ. Bir çağıran `assert_fresh`i yalnız
    # bu bayrak `True` olan öğelerde güvenle çalıştırabilir. Ajansspor için DAİMA `True`dur:
    # `news:publication_date` ZORUNLU alandır, eksik/bozuksa `now`a hiç düşülmez —
    # `_news_published_at` bunun yerine `ContractViolation` fırlatır.
    published_at_is_source_provided: bool = True


class NewsAdapter(Protocol):
    # `@property` — SALT-OKUNUR bir öznitelik bildirir. Düz `source_id: str` bir Protocol'de
    # AYARLANABİLİR (settable) bir değişken ister (mypy --strict, ölçüldü: "expected settable
    # variable, got read-only attribute"); ama bu projenin genel kısıtı HER YERDE `frozen=True`
    # zorunlu kılıyor (mutation yok) ve `AjansporAdapter`/`GoogleNewsAdapter` frozen dataclass'tır
    # — alanları SALT-OKUNURDUR. Protocol'ü `@property`ye çevirmek, immutability'yi gevşetmeden
    # doğru sözleşmeyi ifade eder: "okunabilir", "yazılabilir" değil.
    @property
    def source_id(self) -> str: ...

    def parse(self, body: str, *, now: datetime) -> tuple[NewsItem, ...]: ...


def _parse_xml(body: str, source_id: str, *, kind: str) -> Element:
    # `defusedxml`: besleme gövdesini BİZ YAZMIYORUZ — üçüncü tarafın ürettiği her girdi
    # gibi düşmanca kabul edilir. Stdlib `xml.etree.ElementTree.fromstring` varlık
    # genişlemesine (billion laughs / quadratic blowup) açıktır; `defusedxml` bunu reddeder.
    try:
        return fromstring(body)
    except (ParseError, DefusedXmlException) as error:
        raise ContractViolation(
            f"{source_id}: {kind} ayrıştırılamadı ({type(error).__name__})"
        ) from error


def _local_name(tag: str) -> str:
    """`{ad-alanı-uri}yerel-ad` → `yerel-ad`. Önek umursanmaz, yalnız YEREL ad karşılaştırılır.

    Ad alanı URI'sini sabit kodlamak yerine yalnız yerel ada bakmak KASITLIDIR: `<url><loc>`
    (sitemap.org ad alanı) ile `<image:image><image:loc>` (image ad alanı) FARKLI URI'lerde
    ama İKİSİ de yerel ad `loc`dur ve yalnız `tag.endswith("}loc")` diye kör bakan bir tarama
    (ölçüldü: bu projenin ilk taslağı tam bunu yapıyordu) ikisini AYIRT EDEMEZ. Burada ad alanı
    hiç kullanılmaz; ayrım DOĞRUDAN-ÇOCUK gezinmesiyle yapılır (bkz. `_sitemap_items`,
    `_rss_items`) — `<image:loc>` `<url>`in torunu, çocuğu değil; aynı ilke RSS `<channel>`
    dışındaki bir `<item>`-benzeri düğüm için de geçerlidir (review Minor #5, terfi ettirildi).
    """
    return tag.rsplit("}", 1)[-1]


def _direct_child(node: Element, local_name: str) -> Element | None:
    return next((child for child in node if _local_name(child.tag) == local_name), None)


def _ensure_aware_utc(value: datetime) -> datetime:
    """KAYNAK-VERİLİ bir zaman damgasını UTC'ye normalize eder (review Important #1).

    RFC 2822 "-0000" ("kaynak bölgeyi bilmiyor", `+0000`/bilinen-UTC'den FARKLI) ve ofsetsiz
    ISO 8601 girdileri timezone-NAIVE bir `datetime` üretir (ölçüldü:
    `parsedate_to_datetime("... -0000")` ve `fromisoformat("2026-09-19T13:33:50")` ikisi de
    `tzinfo=None` döner). `assert_fresh` `now() - value` yapar; naive-aware çıkarma
    `TypeError` fırlatır — bu, `defusedxml`i motive eden AYNI "düşman üçüncü-taraf girdisi"
    duruşunun BİR KATMAN YUKARIDA gözden kaçmış hâli: ayrıştırıcıyı düşmanca XML'e karşı
    sertleştirip İÇİNDEKİ bir alana (zaman damgası metnine) güvenmek.

    Desen `ledger.py:canonical_timestamp`ten (satır 33-35) BİREBİR alınmıştır: naive ise
    ÖNCE UTC etiketlenir (sayısal dönüşüm YOK, "zaten UTC" varsayılır — bu proje UTC'yi
    varsayılan kabul eder, bkz. testlerdeki `NOW = datetime(..., tzinfo=UTC)`), SONRA
    `astimezone(UTC)` ile (varsa) başka bir açık ofset SAYISAL olarak UTC'ye çevrilir — yalnız
    `==` değer eşitliği DEĞİL, `tzinfo`nin KENDİSİ de `UTC` olur (ölçüldü:
    `tests/test_news.py::test_ajansspor_offset_publication_date_is_converted_to_utc`; ilk
    yazımda yalnız `==` sınayan bir test `astimezone` hiç yokken de yeşildi — Python'da aware
    datetime eşitliği MUTLAK ANA göredir, `tzinfo`nin kendisine değil).
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


# ---------------------------------------------------------------------------
# Google News — RSS 2.0. `enabled: false` (Ruling B); adaptör yine de yazılır ve test edilir.
# ---------------------------------------------------------------------------


def _rss_published_at(node: Element, now: datetime) -> tuple[datetime, bool]:
    """`(zaman damgası, kaynak mı sağladı)`. RSS 2.0'da `<pubDate>` OPSİYONELDİR (sitemap'in
    `news:publication_date`sinin AKSİNE — bkz. `_news_published_at`); eksikliği bir şema
    kırığı DEĞİLDİR, bu yüzden madde burada ATILMAZ. Ama sessizce `now`a düşmek KAYNAK-VERİLİ
    bir gözlemi KENDİ-DAMGALI türe çevirir (review Important #2) — ikinci eleman bunu GÖRÜNMEZ
    bırakmaz: `False` = "bu `published_at` kaynaktan gelmedi, `now` yerine geçti."
    """
    raw_date = node.findtext("pubDate")
    if not raw_date:
        return now, False
    try:
        published = parsedate_to_datetime(raw_date)
    except (TypeError, ValueError):
        return now, False
    return _ensure_aware_utc(published), True


def _rss_item(node: Element, source_id: str, now: datetime) -> NewsItem | None:
    title = (node.findtext("title") or "").strip()
    link = (node.findtext("link") or "").strip()
    if not title or not link:
        return None
    published, is_source_provided = _rss_published_at(node, now)
    return NewsItem(
        title=title,
        url=link,
        published_at=published,
        source_id=source_id,
        published_at_is_source_provided=is_source_provided,
    )


def _rss_items(body: str, source_id: str, now: datetime) -> tuple[NewsItem, ...]:
    # Simetri (review Minor #5, terfi ettirildi): kök doğrulanır ve YALNIZ `<channel>`ın
    # DOĞRUDAN çocukları taranır. `root.iter("item")` (özyineli, kök doğrulamasız) Ajansspor
    # yolunun (`_sitemap_item`) tam düzelttiği arıza SINIFIYDI — burada asimetrik bırakılmıştı.
    root = _parse_xml(body, source_id, kind="RSS")
    if _local_name(root.tag) != "rss":
        raise ContractViolation(f"{source_id}: beklenmeyen RSS kökü '{_local_name(root.tag)}'")
    channel = _direct_child(root, "channel")
    if channel is None:
        raise ContractViolation(f"{source_id}: RSS'te <channel> yok")
    items: tuple[NewsItem, ...] = ()
    for node in channel:
        if _local_name(node.tag) != "item":
            continue
        item = _rss_item(node, source_id, now)
        if item is not None:
            items = (*items, item)
    if not items:
        raise ContractViolation(f"{source_id}: feed'de hiç item yok")
    return items


@dataclass(frozen=True)
class GoogleNewsAdapter:
    source_id: str = "googlenews"

    def parse(self, body: str, *, now: datetime) -> tuple[NewsItem, ...]:
        return _rss_items(body, self.source_id, now)


# ---------------------------------------------------------------------------
# Ajansspor — sitemap.org urlset (+ Google news: uzantısı). Ölçüldü (2026-09-19):
# `config/sources.yaml`'daki `declared_paths` — `/sitemap.xml` — canlıda 404 verir. robots.txt'in
# KENDİ `Sitemap:` satırları `/sitemap` (bir sitemap INDEX'i döner) ve `/sitemap/news` (gerçek
# makale urlset'i) — ikisi de `/sitemap.xml` DEĞİL. `declared_paths` bu görevin salt-okunur
# dosyasında olduğu için burada düzeltilmedi; bkz. task-8-report.md "concerns".
# ---------------------------------------------------------------------------


def _is_ajansspor_path_allowed(url: str) -> bool:
    path = urlsplit(url).path
    return not any(path.startswith(prefix) for prefix in _AJANSSPOR_DISALLOWED_PREFIXES)


def _news_title(news_node: Element | None, fallback_url: str) -> str:
    title_node = None if news_node is None else _direct_child(news_node, "title")
    text = "" if title_node is None else (title_node.text or "").strip()
    return text or fallback_url.rsplit("/", 1)[-1]


def _news_published_at(news_node: Element | None, source_id: str) -> datetime:
    """`news:publication_date` news-sitemap protokolünde `news:news`in ZORUNLU bir alt
    öğesidir (Google News Sitemap uzantısı) — RSS'in OPSİYONEL `pubDate`sinin AKSİNE (bkz.
    `_rss_published_at`). Eksikliği/bozukluğu bir KOLAYLIK varsayılanı (bugüne düş) DEĞİL, bir
    ŞEMA KIRIĞIdır — eksik `<loc>` durumuyla AYNI muameleyi görür (review Important #2):
    sessizce `now`a düşmek KAYNAK-VERİLİ bir gözlemi tam da `assert_fresh`in docstring'inin
    yasakladığı KENDİ-DAMGALI türe çevirir, hiçbir bayrak/sayaç/ayırt edici değer olmadan. Bu
    yüzden bu fonksiyon `now` PARAMETRESİ ALMAZ — düşülecek bir yol yok: alan yoksa ya da
    ayrıştırılamıyorsa `ContractViolation`.
    """
    date_node = None if news_node is None else _direct_child(news_node, "publication_date")
    raw = None if date_node is None else (date_node.text or "").strip()
    if not raw:
        raise ContractViolation(f"{source_id}: news:publication_date yok (zorunlu alan)")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as error:
        raise ContractViolation(
            f"{source_id}: news:publication_date ayrıştırılamadı ({raw!r})"
        ) from error
    return _ensure_aware_utc(parsed)


def _sitemap_item(url_node: Element, source_id: str) -> NewsItem | None:
    # YALNIZ DOĞRUDAN çocuk `loc` okunur — `url_node.iter("loc")` gibi özyineli bir tarama
    # `<image:image><image:loc>`u da (torun, `<url>`in İKİ seviye altı) yakalardı. Ölçüldü:
    # gerçek besleme HER <url> için bir <image:loc> taşıyor, makale <loc>'uyla TAM AYNI SAYIDA
    # (1000/1000) — özyineli bir tarama fotoğraf CDN URL'sini "haber" diye ikiye katlardı. Bu,
    # `collectors/footystats.py`nin `_data_rows`de zaten öğrendiği aynı arıza sınıfıdır: gömülü
    # bir düğüm üst düzeyle karışır.
    loc = _direct_child(url_node, "loc")
    text = None if loc is None else (loc.text or "").strip()
    if not text or not _is_ajansspor_path_allowed(text):
        return None
    news_node = _direct_child(url_node, "news")
    return NewsItem(
        title=_news_title(news_node, text),
        url=text,
        published_at=_news_published_at(news_node, source_id),
        source_id=source_id,
    )


def _sitemapindex_candidates(root: Element) -> str:
    names: list[str] = []
    for child in root:
        if _local_name(child.tag) != "sitemap":
            continue
        loc = _direct_child(child, "loc")
        if loc is not None and loc.text:
            names.append(loc.text.strip().rsplit("/", 1)[-1])
    return ", ".join(names) if names else "?"


def _sitemap_items(body: str, source_id: str) -> tuple[NewsItem, ...]:
    root = _parse_xml(body, source_id, kind="sitemap")
    root_name = _local_name(root.tag)
    if root_name == "sitemapindex":
        # "Handle it or report it; do not silently produce zero items" (task-8-brief). Bir
        # INDEX'in KENDİSİNDE makale yoktur — alt sitemap'lerden biri AYRICA çekilmeli. Sessizce
        # `()` dönmek, ayrıştırıcının KIRILDIĞI durumdan (sayfa şekli değişti) AYIRT EDİLEMEZ.
        raise ContractViolation(
            f"{source_id}: sitemap bir INDEX döndürdü, urlset değil — alt sitemap'lerden biri "
            f"ayrıca çekilip ayrıştırılmalı (adaylar: {_sitemapindex_candidates(root)})"
        )
    if root_name != "urlset":
        raise ContractViolation(f"{source_id}: beklenmeyen sitemap kökü '{root_name}'")
    items: tuple[NewsItem, ...] = ()
    for url_node in root:
        if _local_name(url_node.tag) != "url":
            continue
        item = _sitemap_item(url_node, source_id)
        if item is not None:
            items = (*items, item)
    if not items:
        raise ContractViolation(f"{source_id}: sitemap'te izinli hiç haber URL'si yok")
    return items


@dataclass(frozen=True)
class AjansporAdapter:
    """Yalnız robots'un izin verdiği haber yolları.

    `/lineup/`, `/mac/`, `/oyuncu/`, `/lig/` DISALLOW (ölçüldü 2026-09-19). Spec §3.1
    Ajansspor'dan "muhtemel 11" bekliyordu; o yol kapalıdır ve alınmaz. `_is_ajansspor_
    path_allowed` filtresi burada KOLAYLIK/ikinci bir savunma katmanıdır — asıl BAĞLAYICI
    zorlama `fetch_text` içindeki `guard_path`tir (bkz.
    `tests/test_news.py::test_article_url_is_checked_against_robots_at_fetch_time`, istek
    hiç ATILMADIĞINI transport çağrı sayısıyla kanıtlar).
    """

    source_id: str = "ajansspor"

    def parse(self, body: str, *, now: datetime) -> tuple[NewsItem, ...]:
        # `now`, `GoogleNewsAdapter`la PAYLAŞILAN `NewsAdapter.parse` imzasına UYUM için
        # alınır ama burada KULLANILMAZ: `news:publication_date` ZORUNLU alandır (review
        # Important #2) — eksik/bozuksa `_news_published_at` `ContractViolation` fırlatır,
        # düşülecek bir `now` yolu yoktur (bkz. o fonksiyonun docstring'i).
        _ = now
        return _sitemap_items(body, self.source_id)


# ---------------------------------------------------------------------------
# Observation eşlemesi ve kayıt defteri kablolaması
# ---------------------------------------------------------------------------


def news_observation(item: NewsItem) -> Observation:
    """Haber gözlemi: YALNIZ başlık ve bağlantı.

    Ham içerik yeniden yayınlanmaz (spec §3.2/4) ve gövde saklanmaz: Faz 4'te Jev makaleyi
    okuduğunda ondan yalnız SAYISAL özellik türetilir. `item.published_at_is_source_provided`
    payload'a SIZMAZ (aynı gerekçe — yalnız `NewsItem` üzerinde yaşayan bizim kendi ayrıştırma
    metadata'mızdır, "başlık+bağlantı" değildir): bir çağıran `assert_fresh`i yalnız o bayrak
    `True` olan öğelerde çalıştırmak isterse `news_observation`ı ÇAĞIRMADAN ÖNCE
    `tuple[NewsItem, ...]` üzerinde süzmelidir.

    `observed_at=item.published_at` — KAYNAK-VERİLİ zaman damgasıdır (RSS `pubDate`, sitemap
    `news:publication_date`), toplayıcının kendi `now()`ı DEĞİL (R23). Bu seçim kasıtlıdır:
    `assert_fresh` yalnız KAYNAKTAN gelen bir zaman damgası üzerinde anlamlıdır (bkz.
    `collector.assert_fresh` docstring'i, madde 1) — bu fonksiyon `assert_fresh`i KENDİSİ
    ÇAĞIRMAZ (toplama döngüsü kablolaması Task 8 kapsamı dışı, ruling R1), ama üretilen
    `Observation.observed_at` ileride üzerinde çağrılacak `assert_fresh`i ANLAMLI kılacak
    şekilde damgalanır (ve `_ensure_aware_utc` sayesinde her zaman timezone-AWARE'dir — review
    Important #1 — `assert_fresh`in kendi `now() - value` çıkarması hiç TypeError fırlatmaz).
    `tests/test_news.py::test_news_observation_stamps_observed_at_from_the_items_own_published_at`
    bunu sabitler.
    """
    return Observation(
        source_id=item.source_id,
        entity_kind="news",
        entity_key=item.url,
        observed_at=item.published_at,
        payload={
            "title": item.title,
            "url": item.url,
            "published_at": item.published_at.isoformat(),
            "source_id": item.source_id,
        },
    )


_ADAPTERS: dict[str, NewsAdapter] = {
    "ajansspor": AjansporAdapter(),
    "googlenews": GoogleNewsAdapter(),
}


def enabled_adapters(sources: tuple[Source, ...]) -> tuple[NewsAdapter, ...]:
    """`enabled: false` olan kaynakların adaptörünü DIŞLAR (ör. googlenews, Ruling B).

    `_ADAPTERS`de KAYITLI OLMAYAN etkin kaynaklar (footystats, tff, ...) sessizce atlanır —
    bu bir hata değil: bu modül yalnız HABER adaptörlerini bilir.
    """
    return tuple(_ADAPTERS[entry.id] for entry in enabled_sources(sources) if entry.id in _ADAPTERS)


# ---------------------------------------------------------------------------
# CLI kablolaması (`fetch-news`) — Task 8'in R1 gereği ERTELEDİĞİ kablolama.
#
# Her adaptörün GERÇEKTEN fetch ettiği tek yol burada adlandırılır (R7 — bkz.
# `config/sources.yaml`nin ajansspor notu, M4): `/sitemap/news` bir urlset döner,
# `AjansporAdapter.parse` onu doğrudan tüketir. `/sitemap` (index) `declared_paths`te
# beyan edilir ama BURADA fetch edilmez — bir index'in içindeki alt-sitemap'i keşfetmek
# ayrı bir iş, bu görevin kapsamı dışı. `googlenews` bu sözlükte YOK: `enabled: false`
# olduğu sürece `enabled_adapters` onu zaten hiç döndürmez (bkz. `test_enabled_adapters_
# excludes_disabled_sources`); ileride açılırsa BURAYA bir yol eklenmeden `collect_news`
# adıyla (RuntimeError) durur — sessizce atlanmaz.
# ---------------------------------------------------------------------------

_ARTICLE_PATHS: dict[str, str] = {"ajansspor": "/sitemap/news"}


@dataclass(frozen=True)
class NewsCollectResult:
    written: int
    # `published_at_is_source_provided=False` olan (kaynak tarih vermediği için `now`a
    # düşmüş) öğe sayısı — YAZILIR (kaybolmaz) ama tazelik iddiasının DIŞINDA tutulur.
    # Sessizce yutulmaz: M6 kararı budur, aşağıdaki `collect_news` docstring'ine bkz.
    self_stamped: int = 0
    failed_sources: tuple[str, ...] = ()


def _source_by_id(sources: tuple[Source, ...], source_id: str) -> Source:
    for entry in sources:
        if entry.id == source_id:
            return entry
    raise RuntimeError(f"{source_id}: kaynak kaydı yok — toplama durduruldu")


def collect_news(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    *,
    sources_path: Path,
    robots_dir: Path,
    now: datetime,
    max_age: timedelta = timedelta(days=2),
) -> NewsCollectResult:
    """Etkin haber adaptörlerini toplar ve yazar.

    **M6 kararı — `assert_fresh` YALNIZ kaynak-verili öğelerde çağrılır.** `NewsItem.
    published_at_is_source_provided` RSS yolunda `False` olur (Ajansspor'da HİÇ olmaz —
    zorunlu alan, bkz. `_news_published_at`): kaynak kullanılabilir bir `pubDate` vermeyip
    toplayıcı kendi `now()`ını yerine geçirdiğinde. Böyle bir öğe üzerinde `assert_fresh`
    çağırmak `collector.assert_fresh`in KENDİ docstring'inin 1. maddesinin yasakladığı TAM
    durumdur (R23): `observed_at` toplayıcının kendi damgaladığı an olduğu için `now -
    observed_at ≈ 0`, iddia HER ZAMAN doğru olur — kırılamaz bir kontrol, testsizlikten
    kötü. Bu yüzden bu fonksiyon, tazelik kontrolünü YALNIZ `published_at_is_source_
    provided=True` öğelerinin ALT KÜMESİ üzerinde çalıştırır (`sourced`); kendi-damgalı
    öğeler bu kontrolün DIŞINDA tutulur.

    Kendi-damgalı öğeler SESSİZCE YUTULMAZ: (a) yine de YAZILIR — kaynak gerçekten bir
    haber yayınladı, yalnız tarihini vermedi; veriyi atmak eksik-ama-var'ı hiç-yokla
    karıştırır. (b) sayıları `NewsCollectResult.self_stamped`e eklenir ve `main()` bunu
    adıyla raporlar — aksi hâlde bu bayrak (Task 8'in var olma nedeni) hiçbir yerde
    OKUNMAMIŞ olur, tam qa-loop'un "kırılamayan test" uyarısının veri sözleşmesi hâli.
    Eğer `sourced` TAMAMEN boşsa `assert_fresh` hiç ÇAĞRILMAZ (boş demet üzerinde çağrılan
    `assert_fresh` "hiç gözlem yok" der — ama gözlem VAR, yalnız hiçbiri kaynak-verili
    değil; bu farklı bir arıza, karıştırılmamalı).

    Arıza izolasyonu ADAPTÖR bazındadır (`collect_footystats`teki lig izolasyonuyla aynı
    gerekçe): bir kaynağın feed'i çekilemez/ayrıştırılamazsa ya da tazelik iddiası
    kırılırsa o kaynak `failed_sources`e eklenir, diğer adaptörler denenmeye devam eder.
    """
    sources = load_sources(sources_path)
    written = 0
    self_stamped = 0
    failed: tuple[str, ...] = ()

    for adapter in enabled_adapters(sources):
        try:
            source = _source_by_id(sources, adapter.source_id)
            path = _ARTICLE_PATHS.get(adapter.source_id)
            if path is None:
                # `try` İÇİNDE, KASITLI: bu bir wiring/yapılandırma hatasıdır ve
                # `_enabled_source`'un (tff.py/footystats.py) tek-kaynaklı, döngüsüz
                # çağrısında uncaught kalması doğruydu — ama BURADA birden çok adaptör
                # AYNI döngüde. Dışarıda bırakılsaydı bir adaptörün eksik eşlemesi
                # DİĞER (doğru yapılandırılmış) adaptörün hiç denenmeden çökmesine yol
                # açardı — tam bu fonksiyonun docstring'inin vaat ettiği ADAPTÖR bazlı
                # izolasyonun ihlali. Yakalanınca da SESSİZ değil: adıyla loglanır ve
                # `failed_sources`e düşer, aynı diğer arızalar gibi.
                raise RuntimeError(f"{adapter.source_id}: fetch yolu tanımlı değil — wiring eksik")
            parser = robots_for(source, robots_dir)
            # Ölçüldü (2026-09-19, M4): ajansspor.com/sitemap/news content-type'ı
            # "application/xml" döner (canlı curl, config/sources.yaml notu).
            body = fetch_text(client, source, path, parser, expect="application/xml")
            items = adapter.parse(body, now=now)
            sourced = tuple(item for item in items if item.published_at_is_source_provided)
            if sourced:
                assert_fresh(
                    tuple(news_observation(item) for item in sourced),
                    now,
                    max_age=max_age,
                    source_id=adapter.source_id,
                )
            new_rows = write_observations(conn, tuple(news_observation(item) for item in items))
            conn.commit()
            # `written` ve `self_stamped` yalnız BAŞARILI (commit edilen) turda sayılır (Minor
            # #4, review, promoted — G1 ile aynı gerekçe: commit() kendisi düşerse satırlar
            # geri alınır ama sayaç ÖNCEDEN artmış olurdu, "N yeni gözlem" hiç kalıcı olmamış
            # veri için basılırdı). `assert_fresh` yukarıda RAISE ederse bu satırlara hiç
            # gelinmez: yarım kalmış bir turun "N öğe kendi-damgalıydı" demesi de aynı hataydı.
            written += new_rows
            self_stamped += len(items) - len(sourced)
        except Exception:
            conn.rollback()
            LOGGER.exception("kaynak=%s haber toplanamadı", adapter.source_id)
            failed = (*failed, adapter.source_id)

    return NewsCollectResult(written=written, self_stamped=self_stamped, failed_sources=failed)
