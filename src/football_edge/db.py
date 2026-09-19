from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import psycopg

from football_edge.leagues import League
from football_edge.ledger import GENESIS, canonical_timestamp, chain
from football_edge.odds_api import PriceRow


def connect(dsn: str | None = None) -> psycopg.Connection[Any]:
    resolved = dsn or os.getenv("DATABASE_URL")
    if not resolved:
        raise RuntimeError("DATABASE_URL tanımlı değil")
    # Oturum saat dilimi UTC'ye sabitlenir: zincir hash'i zaman damgasının
    # metin hâlini kapsıyor, oturum TZ'si değişirse geri okumada zincir kırılır.
    # DATABASE_URL SESSION pooler'ı göstermeli (aws-0-<bölge>.pooler.supabase.com:5432).
    # TRANSACTION pooler (6543) kullanılacaksa psycopg3'ün hazırlanmış ifadeleri
    # kapatılmalıdır (prepare_threshold=None), yoksa birkaç çağrıdan sonra bozulur.
    return psycopg.connect(resolved, options="-c timezone=UTC")


def snapshot_payload(row: PriceRow, observed_at: datetime, *, is_closing: bool) -> dict[str, Any]:
    return {
        "match_id": row.event_id,
        "observed_at": canonical_timestamp(observed_at),
        "bookmaker": row.bookmaker,
        "market": row.market,
        "outcome": row.outcome,
        "point": row.point,
        "price": row.price,
        "bookmaker_last_update": (
            None
            if row.bookmaker_last_update is None
            else canonical_timestamp(row.bookmaker_last_update)
        ),
        "is_closing": is_closing,
    }


def chain_head(conn: psycopg.Connection[Any]) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT row_hash FROM odds_snapshots ORDER BY id DESC LIMIT 1")
        found = cur.fetchone()
    return GENESIS if found is None else str(found[0])


def upsert_leagues(conn: psycopg.Connection[Any], leagues: tuple[League, ...]) -> int:
    """config/leagues.yaml'ı leagues tablosuna yansıtır. Konfigürasyon kaynak, tablo aynadır.

    matches.league_id bu tabloya yabancı anahtarla bağlı. Tablo elle doldurulursa temiz bir
    veritabanında her lig ayrı ayrı ForeignKeyViolation verir ve toplayıcının lig izolasyonu
    TEK sistemik sebebi altı bağımsız arıza gibi gösterir. Elle kurulan ön koşul değildir.
    """
    written = 0
    with conn.cursor() as cur:
        for league in leagues:
            cur.execute(
                """
                INSERT INTO leagues (id, odds_api_key, name, country, lang, gl, active)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                  odds_api_key = excluded.odds_api_key,
                  name = excluded.name,
                  country = excluded.country,
                  lang = excluded.lang,
                  gl = excluded.gl,
                  active = excluded.active
                """,
                (
                    league.id,
                    league.odds_api_key,
                    league.name,
                    league.country,
                    league.lang,
                    league.gl,
                    league.active,
                ),
            )
            written += cur.rowcount
    return written


def upsert_matches(
    conn: psycopg.Connection[Any], rows: tuple[PriceRow, ...], league_id: str
) -> int:
    seen: dict[str, PriceRow] = {}
    for row in rows:
        seen.setdefault(row.event_id, row)
    written = 0
    with conn.cursor() as cur:
        for event_id, row in seen.items():
            cur.execute(
                """
                INSERT INTO matches (id, league_id, commence_time, home_team, away_team)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (event_id, league_id, row.commence_time, row.home_team, row.away_team),
            )
            written += cur.rowcount  # ON CONFLICT DO NOTHING sonrası 1 veya 0
    return written


def insert_snapshots(
    conn: psycopg.Connection[Any],
    rows: tuple[PriceRow, ...],
    observed_at: datetime,
    *,
    is_closing: bool,
) -> tuple[str, ...]:
    """GERÇEKTEN yazılan satırların match_id'lerini sırasıyla döner.

    Sayı değil kimlik döner, çünkü mühür MAÇ bazındadır: hakkında tek satır yazılmamış
    bir maça `sealed_at` basılırsa maç bir daha denenmez ve kapanış fiyatı kalıcı olarak
    kaybolur. Denenen satır da sayılmaz: `ON CONFLICT DO NOTHING` sessizce satır düşürür
    ve yeniden deneme senaryosunda tüm batch no-op olabilir.
    """
    payloads = tuple(snapshot_payload(row, observed_at, is_closing=is_closing) for row in rows)
    linked = chain(payloads, prev_hash=chain_head(conn))
    written: tuple[str, ...] = ()
    with conn.cursor() as cur:
        for entry in linked:
            cur.execute(
                """
                INSERT INTO odds_snapshots
                  (match_id, observed_at, bookmaker, market, outcome, point, price,
                   bookmaker_last_update, is_closing, prev_hash, row_hash)
                VALUES (%(match_id)s, %(observed_at)s, %(bookmaker)s, %(market)s, %(outcome)s,
                        %(point)s, %(price)s, %(bookmaker_last_update)s, %(is_closing)s,
                        %(prev_hash)s, %(row_hash)s)
                ON CONFLICT (row_hash) DO NOTHING
                """,
                entry,
            )
            if cur.rowcount:  # ON CONFLICT DO NOTHING sonrası 1 veya 0
                written = (*written, str(entry["match_id"]))
    return written
