from __future__ import annotations

import logging
import sys
from datetime import datetime
from typing import Any

import httpx
import psycopg

from football_edge.collect import (
    EXIT_LEAGUE_FAILED,
    EXIT_SOURCE_FAILED,
    LEAGUES_PATH,
    ROBOTS_DIR,
    SOURCES_PATH,
    _require_env,
)
from football_edge.collectors.footystats import collect_footystats
from football_edge.collectors.news import NewsCollectResult, collect_news
from football_edge.collectors.results import ResultsCollectResult, collect_results
from football_edge.collectors.tff import collect_tff
from football_edge.collectors.venues import VenuesResult, collect_venues
from football_edge.leagues import active_leagues, load_leagues

LOGGER = logging.getLogger("football_edge.fetch")

# R50 (Task 11): dört `_fetch_*_command` toplayıcı CLI tutkalıydı ve `collect.py`yi
# 774/800 satıra taşımıştı (#M41). Beşi de (footystats dâhil — aşağıya bkz.) buraya
# taşındı, DAVRANIŞ DEĞİŞMEDEN: `collect.py` artık defter komutlarını (snapshot/seal/
# verify-chain/publish-head), kaynak denetimini ve (Task 11'in eklediği) varlık
# eşlemesini taşıyor; toplayıcı dispatch'i TAMAMEN burada.
#
# Bağımlılık TEK YÖNLÜDÜR: bu modül `football_edge.collect`tan sabit/yardımcı içe
# aktarır (EXIT_*, yol sabitleri, `_require_env`) ama `collect.py` bu modülü MODÜL
# SEVİYESİNDE içe aktarmaz — `main()` içindeki gecikmeli (yerel) import ile çağırır.
# Tersi (üst düzeyde iki yönlü import) döngüsel import olurdu: `collect` `fetch`ten
# dispatch fonksiyonlarını, `fetch` da `collect`tan sabitleri isterdi.


def _fetch_footystats_command(
    conn: psycopg.Connection[Any], client: httpx.Client, now: datetime
) -> int:
    """`main()`in eski `fetch-footystats` dalının AYNEN taşınmış hâli (R50).

    Tek değişiklik: gövde kendi fonksiyonuna sarıldı. `footystats_result` adı
    (`result` değil) KORUNDU — orijinal yorumun gerekçesi (mypy --strict, `main()`
    içindeki `CollectResult` ile ad çakışması) bu fonksiyonun kendi kapsamında artık
    geçerli değil ama adı değiştirmek mekanik taşımanın dışına çıkardı.
    """
    footystats_result = collect_footystats(
        conn,
        client,
        active_leagues(load_leagues(LEAGUES_PATH)),
        sources_path=SOURCES_PATH,
        robots_dir=ROBOTS_DIR,
        now=now,
    )
    sys.stdout.write(f"footystats: {footystats_result.written} yeni gözlem\n")
    if footystats_result.failed_leagues:
        # Diğer ligler toplandı ama bu sessizce geçilmemeli: CI kırmızı olmalı
        # (aynı gerekçe collect.py:_report — F4). Sessiz kalırsa "footystats: 0
        # yeni gözlem" hem başarılı ikinci turun hem ALTI LİGİN DE kırıldığı bir
        # turun çıktısı olur (review #3).
        sys.stdout.write(
            "footystats başarısız ligler: " + ", ".join(footystats_result.failed_leagues) + "\n"
        )
        return EXIT_LEAGUE_FAILED
    return 0


def _fetch_tff_command(conn: psycopg.Connection[Any], client: httpx.Client, now: datetime) -> int:
    """`collect_tff` TEK bir ulusal sayfa fetch eder — footystats'ın aksine lig döngüsü
    yok, izole edilecek bir "parça" yok, bu yüzden arıza TÜM komuta aittir.

    `collect_tff` kendi `conn.commit()`ini zaten çağırıyor (başarı yolunda); burada
    `rollback()` yalnız `commit()`in KENDİSİ düşüp bağlantı ayaktayken KALIRSA devreye
    girer (G1 ile aynı sınıf arıza — bkz. `db.py:LEDGER_LOCK_KEY` yorumu) — traceback'i
    yutmuyor, `LOGGER.exception` onu adıyla yazıyor, yalnız bağlantıyı temiz kapatıyor.
    """
    try:
        written = collect_tff(
            conn, client, sources_path=SOURCES_PATH, robots_dir=ROBOTS_DIR, now=now
        )
    except Exception:
        conn.rollback()
        LOGGER.exception("tff toplanamadı")
        sys.stdout.write("tff: toplama başarısız — günlüğe bakın\n")
        return EXIT_SOURCE_FAILED
    sys.stdout.write(f"tff: {written} yeni gözlem\n")
    return 0


def _fetch_venues_command(
    conn: psycopg.Connection[Any], client: httpx.Client, now: datetime
) -> int:
    result: VenuesResult = collect_venues(
        conn, client, sources_path=SOURCES_PATH, robots_dir=ROBOTS_DIR, now=now
    )
    sys.stdout.write(f"venues: {result.written} yeni gözlem\n")
    if result.failed_venues:
        sys.stdout.write("venues başarısız stadyumlar: " + ", ".join(result.failed_venues) + "\n")
    if result.failed_matches:
        sys.stdout.write(
            "venues başarısız maçlar (hava): " + ", ".join(result.failed_matches) + "\n"
        )
    if result.failed_venues or result.failed_matches:
        return EXIT_SOURCE_FAILED
    return 0


def _fetch_news_command(conn: psycopg.Connection[Any], client: httpx.Client, now: datetime) -> int:
    result: NewsCollectResult = collect_news(
        conn, client, sources_path=SOURCES_PATH, robots_dir=ROBOTS_DIR, now=now
    )
    sys.stdout.write(f"news: {result.written} yeni gözlem\n")
    if result.self_stamped:
        # M6: kaynak tarih vermediği için `now`a düşmüş öğeler — yazıldı ama tazelik
        # iddiasının DIŞINDA tutuldu (bkz. collectors.news.collect_news docstring'i).
        # Sessizce yutulmaz: bu sayı burada raporlanmazsa bayrak hiçbir yerde okunmamış olur.
        sys.stdout.write(f"news kendi-damgalı (tazelik denetlenmedi): {result.self_stamped}\n")
    if result.failed_sources:
        sys.stdout.write("news başarısız kaynaklar: " + ", ".join(result.failed_sources) + "\n")
        return EXIT_SOURCE_FAILED
    return 0


def _fetch_results_command(
    conn: psycopg.Connection[Any], client: httpx.Client, now: datetime
) -> int:
    api_key = _require_env("ODDS_API_KEY")
    configured = active_leagues(load_leagues(LEAGUES_PATH))
    result: ResultsCollectResult = collect_results(conn, client, api_key, configured, now)
    sys.stdout.write(f"results: {result.written} yeni sonuç\n")
    if result.scoreless_completed:
        # R34: tamamlanmış ama skorsuz — uydurma 0-0 yazılmadı, adıyla raporlanır.
        sys.stdout.write(
            "results tamamlanmış ama skorsuz: " + ", ".join(result.scoreless_completed) + "\n"
        )
    if result.failed_leagues:
        # `EXIT_LEAGUE_FAILED`ın BİLİNÇLİ yeniden kullanımı — bkz. o sabitin yorumu.
        sys.stdout.write("results başarısız ligler: " + ", ".join(result.failed_leagues) + "\n")
        return EXIT_LEAGUE_FAILED
    return 0
