from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
import psycopg

from football_edge.collector import ContractViolation
from football_edge.leagues import League
from football_edge.ledger import canonical_timestamp
from football_edge.odds_api import BASE_URL, Quota, read_quota

LOGGER = logging.getLogger("football_edge.collectors.results")

SOURCE_ID = "oddsapi_scores"


@dataclass(frozen=True)
class MatchOutcome:
    """Task 10 (Elo) bu tipi İTHAL ETMEZ — motor bilinçli olarak düz demet alır
    (paralel bağımsızlık). Bu tipi yalnız bu modül üretir ve tüketir."""

    match_id: str
    home_goals: int
    away_goals: int
    completed: bool
    observed_at: datetime


@dataclass(frozen=True)
class ParsedScores:
    """`parse_scores`in sonucu: sonuçlar ve GÖRÜNÜR KILINMIŞ bir arıza sınıfı bir arada.

    `scoreless_completed` (R34), `collectors.footystats.FootyStatsResult.failed_leagues`
    ile AYNI gerekçeyle var: `completed=true` ama `scores` boş/yok bir olay sessizce
    ATLANIR — uydurma bir 0-0 sonucu YAZILMAZ, bu davranış DEĞİŞMEDİ. Ama skip'in
    KENDİSİ SESSİZ kalırsa "tamamlanmış ama skorsuz" ile "henüz oynanmadı" çıktıda
    AYIRT EDİLEMEZ olur. Bugün nadir bir kenar durum; vantorun davranışı kayarsa
    (alan adı değişir, `completed` ne zaman set edildiği değişir) sistematik hâle
    gelebilir ve belirti "Elo sessizce açlık çeker, komut yine de başarı raporlar"
    olur — Faz 0'ın dört düzeltme turu harcadığı kaçan-mühür sorunuyla AYNI şekil.
    """

    outcomes: tuple[MatchOutcome, ...]
    scoreless_completed: tuple[str, ...] = ()


def _goals(scores: list[dict[str, Any]], team: str, event_id: str) -> int:
    """Skoru takım ADINA göre bulur — konuma göre DEĞİL.

    `scores` dizisinin sırası belgelenmemiştir (bkz. `parse_scores` docstring'i). Adı
    takım adlarından biriyle eşleşmeyen bir girdi SESSİZCE yok sayılmaz: raise eder.
    Aynı şekilde sayı olmayan bir skor (ör. maç ertelendiğinde API'nin döndürdüğü "-")
    de SESSİZCE 0 sayılmaz.
    """
    for entry in scores:
        if str(entry.get("name", "")) == team:
            raw = str(entry.get("score", ""))
            if not raw.lstrip("-").isdigit():
                raise ContractViolation(
                    f"{SOURCE_ID}: skor sayı değil ({event_id}, {team}): {raw!r}"
                )
            return int(raw)
    raise ContractViolation(f"{SOURCE_ID}: '{team}' skor listesiyle eşleşmedi ({event_id})")


def parse_scores(payload: list[dict[str, Any]], observed_at: datetime) -> ParsedScores:
    """Tamamlanmış maçları sonuca çevirir; tamamlanmamışlar ATLANIR, 0-0 YAZILMAZ.

    `scores` dizisinin SIRASI belgelenmemiştir; ev/deplasman ADA göre eşlenir. Konuma göre
    okumak, skorları sessizce ters çevirir — ve ters bir sonuç, eksik bir sonuçtan çok daha
    zararlıdır: Elo onu doğru sanıp iki takımı da yanlış yöne iter (bkz. `_goals`).

    Sonuç yolu HİÇ varlık eşlemesi gerektirmez: `match_id` The Odds API'nin kendi
    `id`'sidir ve `matches` tablosunda zaten aynı kimlikle duruyor (Faz 0, snapshot/seal).

    `completed=true` ama `scores` boş/yok olan olay da ATLANIR (R34) — ama bu ikinci skip
    `completed=false` skip'inden FARKLI muameleye tabidir: WARNING'e loglanır VE
    `ParsedScores.scoreless_completed`e event_id'siyle eklenir, çünkü "tamamlanmış ama
    skorsuz" nadir ve beklenmedik bir vantor arızasıdır — "henüz oynanmadı" ise sıradan,
    her turda beklenen bir durumdur. İkisini AYNI sessiz `continue`da bırakmak, bkz.
    `ParsedScores` docstring'i.
    """
    outcomes: tuple[MatchOutcome, ...] = ()
    scoreless: tuple[str, ...] = ()
    for entry in payload:
        if not entry.get("completed"):
            continue
        event_id = str(entry["id"])
        scores = entry.get("scores")
        if not scores:
            LOGGER.warning(
                "lig=%s maç=%s tamamlanmış ama skor yok — sonuç atlandı (uydurma 0-0 yazılmadı)",
                entry["sport_key"],
                event_id,
            )
            scoreless = (*scoreless, event_id)
            continue
        outcomes = (
            *outcomes,
            MatchOutcome(
                match_id=event_id,
                home_goals=_goals(scores, str(entry["home_team"]), event_id),
                away_goals=_goals(scores, str(entry["away_team"]), event_id),
                completed=True,
                observed_at=observed_at,
            ),
        )
    return ParsedScores(outcomes=outcomes, scoreless_completed=scoreless)


def fetch_scores(
    client: httpx.Client,
    api_key: str,
    sport_key: str,
    observed_at: datetime,
    *,
    days_from: int = 3,
) -> tuple[ParsedScores, Quota]:
    """`daysFrom` BELİRTİLİNCE maliyet 2 kredidir (1 değil) — vantor belgesinde açık.

    Geçerli aralık 1-3; dışına çıkmak API hatası verir (ve kredi HARCAR). Bu yüzden
    doğrulama isteği ATMADAN ÖNCE yapılır: geçersiz bir `days_from` hiçbir zaman ağa
    çıkmaz. Günde bir koşulduğu için varsayılan 3 seçilir: bir turun kaçması sonucu
    kaybettirmesin.
    """
    if not 1 <= days_from <= 3:
        raise ValueError(f"daysFrom 1-3 arasında olmalı, {days_from} verildi")
    response = client.get(
        f"{BASE_URL}/sports/{sport_key}/scores/",
        params={"apiKey": api_key, "daysFrom": str(days_from), "dateFormat": "iso"},
        timeout=30.0,
    )
    response.raise_for_status()
    return parse_scores(response.json(), observed_at), read_quota(response.headers)


def write_results(conn: psycopg.Connection[Any], outcomes: tuple[MatchOutcome, ...]) -> int:
    """Sonuçları yazar. `matches` tablosunda OLMAYAN maç sessizce düşer (yabancı anahtar).

    Bu bilinçlidir: `/scores` bizim topladığımızdan daha geniş bir maç kümesi döndürebilir
    (bu proje her ligin HER maçının oranını toplamamış olabilir) ve Faz 0'ın defteri
    yalnız kendi gördüğü maçlar hakkında iddia taşır. `WHERE EXISTS` bu satırı ayrı ayrı
    HATA vermeden düşürür — `matches.id` yabancı anahtarına çarpıp tüm batch'i
    patlatmak yerine.

    `match_results` GÖZLEMDİR, defter (hash zinciri) değil (bkz. db/migrations/
    0002_sources.sql): düzeltilmiş bir skor eskisinin YERİNE geçmez, `(match_id,
    observed_at)` birincil anahtarıyla YANINA eklenir — `ON CONFLICT DO NOTHING` yalnız
    AYNI gözlemin (aynı maç, aynı an) iki kez yazılmasını engeller, farklı bir `observed_at`
    her zaman yeni bir satırdır. Okuyan taraf maç başına EN YENİYİ alır.
    """
    if not outcomes:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO match_results (match_id, observed_at, home_score, away_score, completed)
            SELECT %s::text, %s::timestamptz, %s::int, %s::int, %s::boolean
            WHERE EXISTS (SELECT 1 FROM matches WHERE id = %s)
            ON CONFLICT (match_id, observed_at) DO NOTHING
            """,
            [
                (
                    entry.match_id,
                    canonical_timestamp(entry.observed_at),
                    entry.home_goals,
                    entry.away_goals,
                    entry.completed,
                    entry.match_id,
                )
                for entry in outcomes
            ],
        )
        return max(cur.rowcount, 0)


# ---------------------------------------------------------------------------
# CLI kablolaması (`fetch-results`) — Task 9'un R1 gereği ERTELEDİĞİ kablolama.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResultsCollectResult:
    written: int
    # Başarısız lig id'leri — `collect_footystats.failed_leagues` ile AYNI gerekçe
    # (review #3, task-5-report.md): boş demet "hepsi tamam" demek, sessizce yutulmaz.
    failed_leagues: tuple[str, ...] = ()
    # `ParsedScores.scoreless_completed`in TÜM liglerden BİRİKMİŞ hâli (R34) — "tamamlanmış
    # ama skorsuz" nadir bir vantor arızasıdır, ayrı raporlanır (bkz. `ParsedScores`
    # docstring'i).
    scoreless_completed: tuple[str, ...] = ()


def collect_results(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    api_key: str,
    leagues: tuple[League, ...],
    now: datetime,
    *,
    days_from: int = 3,
) -> ResultsCollectResult:
    """Etkin liglerin tamamlanmış maç sonuçlarını toplar ve yazar.

    Lig başına arıza izolasyonu Faz 0'daki `_collect`/`collect_footystats` ile AYNI
    gerekçeyle: tek ligin `/scores` çağrısı düşerse diğer liglerin sonucu kaybolmamalı.
    İzolasyon SESSİZ değildir — `failed_leagues` adıyla taşır, `main()` bunu raporlar.
    """
    written = 0
    failed: tuple[str, ...] = ()
    scoreless: tuple[str, ...] = ()
    for league in leagues:
        try:
            parsed, _quota = fetch_scores(
                client, api_key, league.odds_api_key, now, days_from=days_from
            )
            written += write_results(conn, parsed.outcomes)
            conn.commit()
        except Exception:
            conn.rollback()
            LOGGER.exception("lig=%s sonuç toplanamadı, diğerlerine devam", league.id)
            failed = (*failed, league.id)
            continue
        scoreless = (*scoreless, *parsed.scoreless_completed)
    return ResultsCollectResult(
        written=written, failed_leagues=failed, scoreless_completed=scoreless
    )
