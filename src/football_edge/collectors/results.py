from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
import psycopg

from football_edge.collector import ContractViolation
from football_edge.ledger import canonical_timestamp
from football_edge.odds_api import BASE_URL, Quota, read_quota

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


def parse_scores(payload: list[dict[str, Any]], observed_at: datetime) -> tuple[MatchOutcome, ...]:
    """Tamamlanmış maçları sonuca çevirir; tamamlanmamışlar ATLANIR, 0-0 YAZILMAZ.

    `scores` dizisinin SIRASI belgelenmemiştir; ev/deplasman ADA göre eşlenir. Konuma göre
    okumak, skorları sessizce ters çevirir — ve ters bir sonuç, eksik bir sonuçtan çok daha
    zararlıdır: Elo onu doğru sanıp iki takımı da yanlış yöne iter (bkz. `_goals`).

    Sonuç yolu HİÇ varlık eşlemesi gerektirmez: `match_id` The Odds API'nin kendi
    `id`'sidir ve `matches` tablosunda zaten aynı kimlikle duruyor (Faz 0, snapshot/seal).
    """
    outcomes: tuple[MatchOutcome, ...] = ()
    for entry in payload:
        if not entry.get("completed"):
            continue
        scores = entry.get("scores")
        if not scores:
            continue
        event_id = str(entry["id"])
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
    return outcomes


def fetch_scores(
    client: httpx.Client,
    api_key: str,
    sport_key: str,
    observed_at: datetime,
    *,
    days_from: int = 3,
) -> tuple[tuple[MatchOutcome, ...], Quota]:
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
