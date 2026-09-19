from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import psycopg

from football_edge.leagues import League
from football_edge.ledger import GENESIS, canonical_timestamp, chain
from football_edge.odds_api import PriceRow

# ── DEFTER YAZMA KİLİDİ ─────────────────────────────────────────────────────
# `insert_snapshots` önce zincir başını OKUR, sonra ondan zincirleyip YAZAR.
# READ COMMITTED altında (Postgres varsayılanı) bu kilitsiz bir oku-sonra-yazdır:
# iki yazar aynı başı `H` okur, ikisi de `H`den zincirler, ikisi de commit eder.
# UNIQUE (row_hash) bunu YAKALAMAZ — yükler farklı olduğu için hash'ler de farklı.
# Sonuç KALICIDIR: `verify_chain` o çatalda sonsuza dek "prev_hash zincire uymuyor"
# der, append-only tetikleyici bozuk satırı sildirmez, `verify-chain` exit 1 de
# `publish-head`i durdurur — yani kanıt üretimi tamamen durur.
#
# Neden `pg_advisory_xact_lock`: TRANSACTION kapsamlıdır, commit ya da rollback'te
# kendiliğinden bırakılır (düşen yazar kilidi tutamaz) ve hem session (5432) hem
# transaction (6543) Supabase pooler'ında çalışır — `pg_advisory_lock` transaction
# pooler'da bırakılmayan kilit sızdırırdı.
#
# Anahtar SABİT ve TEK olmalı: yazarlar aynı sayıyı istemezse kimse kimseyi
# beklemez ve kilit hiçbir şey serileştirmez. Değer keyfîdir, yalnız bu defter
# için ayrılmıştır ve DEĞİŞTİRİLEMEZ — eski sürümü koşan bir yazar kalırsa
# serileşme sessizce biter.
LEDGER_LOCK_KEY = 0x0DD51EDE  # "ODDS-LEDGE" — keyfî ama sabit

# Toplu yazmanın kolon sırası. `_SNAPSHOT_COLUMNS` hem SQL metnini hem parametre sözlüğünü
# üretir: iki listeyi elle eşlemek, sessizce kayan bir sütun eşlemesine davetiyedir.
_SNAPSHOT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("match_id", "text"),
    ("observed_at", "timestamptz"),
    ("bookmaker", "text"),
    ("market", "text"),
    ("outcome", "text"),
    ("point", "numeric"),
    ("price", "numeric"),
    ("bookmaker_last_update", "timestamptz"),
    ("is_closing", "boolean"),
    ("prev_hash", "text"),
    ("row_hash", "text"),
)

_NAMES = ", ".join(name for name, _ in _SNAPSHOT_COLUMNS)
_ARRAYS = ", ".join(f"%({name})s::{kind}[]" for name, kind in _SNAPSHOT_COLUMNS)

# `WITH ORDINALITY ... ORDER BY ord` LOAD-BEARING'DİR: defter `ORDER BY id` ile geri okunur
# ve `verify_chain` her satırın `prev_hash`ini bir öncekinin `row_hash`i sanar. Satırlar dizi
# sırasından FARKLI bir sırayla eklenirse bigserial sırası zinciri çapraz keser ve KURCALANMAMIŞ
# bir defter "KIRIK" der. Append-only olduğu için o satırlar silinemez.
INSERT_SNAPSHOTS = f"""
    INSERT INTO odds_snapshots ({_NAMES})
    SELECT {_NAMES}
    FROM unnest({_ARRAYS}) WITH ORDINALITY AS t({_NAMES}, ord)
    ORDER BY ord
    ON CONFLICT (row_hash) DO NOTHING
    RETURNING match_id
"""


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


def lock_ledger(conn: psycopg.Connection[Any]) -> None:
    """Defter yazma kilidini alır; `insert_snapshots`ın İLK ifadesi budur.

    Kilit baş okumasından SONRA alınırsa hiçbir şey serileşmez: iki yazar da başı
    okuduktan sonra sıraya girer ve yine aynı baştan zincirler. Sıra yük taşır.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (LEDGER_LOCK_KEY,))


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
    """Maçları tazeler. `commence_time` HER TURDA güncellenir.

    `DO NOTHING` ertelenen maçın ESKİ saatini taşımaya devam ediyordu: satır filtresi API'nin
    güncel saatine, mühür adaylığı veritabanının bayat saatine bakıyor ve maç eski saatinden
    24 saat sonra `_seal_candidates` penceresinden SESSİZCE düşüyordu — ne mühürlenir ne de
    kaçan mühür olarak raporlanır. Kapanış fiyatı kaybolur ve kimse görmez (DEFERRED §3.1).

    Dönen sayı "yeni maç" değil "GÖRÜLEN maç"tır: `DO UPDATE` her satır için 1 bildirir.
    Çağıran bu değeri karar için kullanmaz.
    """
    seen: dict[str, PriceRow] = {}
    for row in rows:
        seen.setdefault(row.event_id, row)
    if not seen:
        return 0
    params = [
        (event_id, league_id, row.commence_time, row.home_team, row.away_team)
        for event_id, row in seen.items()
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO matches (id, league_id, commence_time, home_team, away_team)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET commence_time = excluded.commence_time
            """,
            params,
        )
        return max(cur.rowcount, 0)


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

    İLK İFADE defter kilididir: baş okuması ile insert arasındaki yarış, zinciri
    KALICI olarak çatallar (bkz. LEDGER_LOCK_KEY). Kilit transaction kapsamlı
    olduğu için çağıranın commit/rollback'inde kendiliğinden bırakılır.
    """
    lock_ledger(conn)
    payloads = tuple(snapshot_payload(row, observed_at, is_closing=is_closing) for row in rows)
    linked = chain(payloads, prev_hash=chain_head(conn))
    if not linked:
        return ()
    columns = {name: [entry[name] for entry in linked] for name, _ in _SNAPSHOT_COLUMNS}
    with conn.cursor() as cur:
        cur.execute(INSERT_SNAPSHOTS, columns)
        return tuple(str(record[0]) for record in cur.fetchall())
