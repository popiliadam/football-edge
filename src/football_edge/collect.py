from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import psycopg

from football_edge.db import chain_head, connect, insert_snapshots, upsert_matches
from football_edge.leagues import League, active_leagues, load_leagues
from football_edge.ledger import verify_chain
from football_edge.odds_api import Quota, QuotaExhausted, fetch_odds, guard_quota

LOGGER = logging.getLogger("football_edge.collect")
LEAGUES_PATH = Path("config/leagues.yaml")


@dataclass(frozen=True)
class CollectResult:
    written: int
    quota: Quota | None
    failed_leagues: tuple[str, ...]


@dataclass(frozen=True)
class Anchor:
    path: Path
    rows: int
    head: str


def _latest_anchor(directory: Path = Path("ledger")) -> Anchor | None:
    """En son yayınlanmış zincir çıpasını okur; yoksa None döner."""
    files = sorted(directory.glob("head-*.txt"))
    if not files:
        return None
    target = files[-1]
    values: dict[str, str] = {}
    for line in target.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            values[key] = value
    if "rows" not in values or "head" not in values:
        return None
    return Anchor(path=target, rows=int(values["rows"]), head=values["head"])


def horizon_iso(now: datetime, days: int) -> str:
    return (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def seal_window(commence_time: datetime, now: datetime, minutes: int) -> bool:
    delta = commence_time - now
    return timedelta(0) <= delta <= timedelta(minutes=minutes)


def _collect(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    api_key: str,
    leagues: tuple[League, ...],
    now: datetime,
    *,
    commence_time_to: str,
    is_closing: bool,
    min_remaining: int,
) -> CollectResult:
    written = 0
    quota: Quota | None = None
    failed: tuple[str, ...] = ()
    for league in leagues:
        if quota is not None:
            guard_quota(quota, min_remaining)
        try:
            rows, quota = fetch_odds(
                client, api_key, league.odds_api_key, commence_time_to=commence_time_to
            )
            if not rows:
                LOGGER.info("lig=%s maç yok", league.id)
                continue
            upsert_matches(conn, rows, league.id)
            written += insert_snapshots(conn, rows, now, is_closing=is_closing)
            conn.commit()
        except Exception:
            # Tek bir ligin arızası diğer liglerin kapanış oranını kaçırmasına yol açmamalı.
            # Kapanış oranı kaçarsa geri gelmez; bozuk bir lig ise sonraki turda tekrar denenir.
            conn.rollback()
            LOGGER.exception("lig=%s toplanamadı, diğer liglere devam ediliyor", league.id)
            failed = (*failed, league.id)
            continue
        LOGGER.info("lig=%s satır=%d kalan_kredi=%d", league.id, len(rows), quota.remaining)
    return CollectResult(written=written, quota=quota, failed_leagues=failed)


def run_snapshot(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    api_key: str,
    leagues: tuple[League, ...],
    now: datetime,
    *,
    horizon_days: int = 7,
    min_remaining: int = 10,
) -> CollectResult:
    return _collect(
        conn,
        client,
        api_key,
        leagues,
        now,
        commence_time_to=horizon_iso(now, horizon_days),
        is_closing=False,
        min_remaining=min_remaining,
    )


def _leagues_due_for_seal(
    conn: psycopg.Connection[Any], leagues: tuple[League, ...], now: datetime, window_minutes: int
) -> tuple[League, ...]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT league_id, commence_time FROM matches
            WHERE sealed_at IS NULL AND commence_time > %s - interval '1 day'
            """,
            (now,),
        )
        candidates = tuple((str(record[0]), record[1]) for record in cur.fetchall())
    due = {
        league_id
        for league_id, commence_time in candidates
        if seal_window(commence_time, now, window_minutes)
    }
    return tuple(league for league in leagues if league.id in due)


def run_seal(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    api_key: str,
    leagues: tuple[League, ...],
    now: datetime,
    *,
    window_minutes: int = 20,
    min_remaining: int = 5,
) -> CollectResult:
    due = _leagues_due_for_seal(conn, leagues, now, window_minutes)
    if not due:
        LOGGER.info("mühürlenecek maç yok")
        return CollectResult(written=0, quota=None, failed_leagues=())
    result = _collect(
        conn,
        client,
        api_key,
        due,
        now,
        commence_time_to=horizon_iso(now, 1),
        is_closing=True,
        min_remaining=min_remaining,
    )
    # Yalnız gerçekten toplanabilen ligler mühürlenmiş sayılır; başarısız lig
    # sealed_at almaz ki sonraki tur tekrar denesin.
    sealed_leagues = tuple(lg.id for lg in due if lg.id not in result.failed_leagues)
    if sealed_leagues:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE matches SET sealed_at = %s
                WHERE sealed_at IS NULL
                  AND league_id = ANY(%s)
                  AND commence_time BETWEEN %s AND %s
                """,
                (now, list(sealed_leagues), now, now + timedelta(minutes=window_minutes)),
            )
        conn.commit()
    return result


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} tanımlı değil")
    return value


def _verify_chain_command(conn: psycopg.Connection[Any]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT match_id, observed_at, bookmaker, market, outcome, point, price,
                   bookmaker_last_update, is_closing, prev_hash, row_hash
            FROM odds_snapshots ORDER BY id
            """
        )
        columns = [desc[0] for desc in cur.description or ()]
        records = tuple(dict(zip(columns, record, strict=True)) for record in cur.fetchall())

    # ── BU NORMALİZASYON LOAD-BEARING'DİR, SADELEŞTİRMEYİN ──────────────────
    # Zincir hash'i satırın kanonik JSON METNİNİ kapsıyor. Postgres aynı değeri
    # farklı Python tipiyle geri veriyor ve metin hâli değişiyor:
    #   numeric  → Decimal: json.dumps(Decimal) TypeError fırlatır; ayrıca
    #              yazarken float 2.40 → "2.4", okurken Decimal("2.40") → "2.40"
    #   timestamptz → datetime: yazarken .isoformat() metni yazılmıştı
    # Bu dönüşümler kaldırılırsa KURCALANMAMIŞ HER SATIR "KIRIK" der —
    # yanlış alarm, kaçırılan kurcalama kadar zararlıdır çünkü alarma güven biter.
    normalised = tuple(
        {
            **record,
            "observed_at": record["observed_at"].isoformat(),
            "bookmaker_last_update": (
                record["bookmaker_last_update"].strftime("%Y-%m-%dT%H:%M:%SZ")
                if record["bookmaker_last_update"] is not None
                else None
            ),
            "point": None if record["point"] is None else float(record["point"]),
            "price": float(record["price"]),
        }
        for record in records
    )
    result = verify_chain(normalised)
    sys.stdout.write(
        f"zincir: {'SAĞLAM' if result.ok else 'KIRIK'} "
        f"kontrol={result.checked} baş={result.head[:16]} hata={result.error}\n"
    )
    if not result.ok:
        return 1

    # Çıplak hash zinciri KUYRUKTAN silmeyi yakalayamaz: son satırlar atılırsa
    # kalan zincir kendi içinde tutarlıdır. Dış çıpa bunu kapatır.
    anchor = _latest_anchor()
    if anchor is not None and result.checked < anchor.rows:
        sys.stdout.write(
            f"ÇIPA UYUŞMAZLIĞI: defterde {result.checked} satır var, "
            f"son yayınlanan çıpa {anchor.rows} diyordu ({anchor.path.name}) "
            f"— kuyruktan satır silinmiş olabilir\n"
        )
        return 1
    return 0


def _publish_head_command(conn: psycopg.Connection[Any], now: datetime) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM odds_snapshots")
        count = int((cur.fetchone() or (0,))[0])
    head = chain_head(conn)
    target = Path("ledger") / f"head-{now:%Y-%m-%d}.txt"
    target.parent.mkdir(exist_ok=True)
    target.write_text(f"{now.isoformat()}\nrows={count}\nhead={head}\n", encoding="utf-8")
    sys.stdout.write(f"zincir başı yazıldı: {target}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="football-edge")
    parser.add_argument("command", choices=("snapshot", "seal", "verify-chain", "publish-head"))
    args = parser.parse_args(argv)

    now = datetime.now(UTC)

    with connect() as conn:
        if args.command == "verify-chain":
            return _verify_chain_command(conn)
        if args.command == "publish-head":
            return _publish_head_command(conn, now)

        leagues = active_leagues(load_leagues(LEAGUES_PATH))
        api_key = _require_env("ODDS_API_KEY")
        with httpx.Client() as client:
            try:
                # Ayrı if/else: run_snapshot ve run_seal farklı keyword argümanlara
                # sahip, tek değişkene atanınca mypy --strict uyumsuzluk bildirir.
                if args.command == "snapshot":
                    result = run_snapshot(conn, client, api_key, leagues, now)
                else:
                    result = run_seal(conn, client, api_key, leagues, now)
            except QuotaExhausted:
                LOGGER.exception("kredi tükendi, iş durduruldu")
                return 2
        remaining = "bilinmiyor" if result.quota is None else str(result.quota.remaining)
        sys.stdout.write(f"yazılan satır: {result.written}, kalan kredi: {remaining}\n")
        if result.failed_leagues:
            # Diğer ligler toplandı ama bu sessizce geçilmemeli: CI kırmızı olmalı.
            sys.stdout.write("başarısız ligler: " + ", ".join(result.failed_leagues) + "\n")
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
