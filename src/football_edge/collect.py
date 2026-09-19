from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import psycopg

from football_edge.db import (
    chain_head,
    connect,
    insert_snapshots,
    upsert_leagues,
    upsert_matches,
)
from football_edge.leagues import League, active_leagues, load_leagues
from football_edge.ledger import ChainResult, canonical_timestamp, verify_chain
from football_edge.odds_api import PriceRow, Quota, QuotaExhausted, fetch_odds, guard_quota

LOGGER = logging.getLogger("football_edge.collect")
LEAGUES_PATH = Path("config/leagues.yaml")
ANCHOR_DIR = Path("ledger")

# db/migrations/0001_init.sql → check (price > 1.0). Şema kısıtının kod tarafındaki karşılığı.
MIN_PRICE = 1.0

_LEDGER_COLUMNS = """
    SELECT match_id, observed_at, bookmaker, market, outcome, point, price,
           bookmaker_last_update, is_closing, prev_hash, row_hash
    FROM odds_snapshots
"""
_LEDGER_ALL = _LEDGER_COLUMNS + " ORDER BY id"
_LEDGER_AFTER = _LEDGER_COLUMNS + " WHERE id > %s ORDER BY id"
_ANCHOR_FIELDS = ("rows", "last_id", "head")


@dataclass(frozen=True)
class CollectResult:
    written: int
    quota: Quota | None
    failed_leagues: tuple[str, ...]
    collected_leagues: tuple[str, ...] = ()
    missed_seals: tuple[str, ...] = ()
    quota_exhausted: bool = False


@dataclass(frozen=True)
class Anchor:
    path: Path
    rows: int
    last_id: int
    head: str


@dataclass(frozen=True)
class SealCandidates:
    due: tuple[League, ...]
    missed: tuple[str, ...]


def _anchor_values(target: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in target.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            values[key] = value
    return values


def _latest_anchor(directory: Path = ANCHOR_DIR) -> Anchor | None:
    """En son yayınlanmış zincir çıpasını okur; yoksa ya da okunamıyorsa None döner.

    Bozuk dosya traceback ile düşmez: çağıran taraf ATLANDI diye raporlar. Sessizce
    None dönmek de yasak — atlanan kontrol geçmek değildir.
    """
    files = sorted(directory.glob("head-*.txt"))
    if not files:
        return None
    target = files[-1]
    values = _anchor_values(target)
    if any(field not in values for field in _ANCHOR_FIELDS):
        LOGGER.warning("çıpa dosyası eksik alanlı (%s bekleniyor): %s", _ANCHOR_FIELDS, target)
        return None
    try:
        rows, last_id = int(values["rows"]), int(values["last_id"])
    except ValueError:
        LOGGER.warning("çıpa dosyasındaki sayılar okunamadı: %s", target)
        return None
    return Anchor(path=target, rows=rows, last_id=last_id, head=values["head"])


def horizon_iso(now: datetime, days: int) -> str:
    return (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def seal_window(commence_time: datetime, now: datetime, minutes: int) -> bool:
    delta = commence_time - now
    return timedelta(0) <= delta <= timedelta(minutes=minutes)


def _commence_at(row: PriceRow) -> datetime:
    """API'den gelen metni tek kanonik yoldan datetime'a çevirir."""
    return datetime.fromisoformat(canonical_timestamp(row.commence_time))


def _seal_row_filter(now: datetime, window_minutes: int) -> Callable[[PriceRow], bool]:
    """Mühür turu 24 saatlik ufuk çeker; kapanış damgasını YALNIZ penceredeki maç hak eder."""

    def in_window(row: PriceRow) -> bool:
        return seal_window(_commence_at(row), now, window_minutes)

    return in_window


def _priced_rows(rows: tuple[PriceRow, ...], league_id: str) -> tuple[PriceRow, ...]:
    """Şema kısıtını ihlal eden satırları ayıklar — ama adıyla loglayarak."""
    valid: tuple[PriceRow, ...] = ()
    for row in rows:
        if row.price > MIN_PRICE:
            valid = (*valid, row)
        else:
            LOGGER.warning(
                "lig=%s maç=%s bahisçi=%s piyasa=%s sonuç=%s geçersiz fiyat=%s — satır atlandı",
                league_id,
                row.event_id,
                row.bookmaker,
                row.market,
                row.outcome,
                row.price,
            )
    return valid


def _usable_rows(
    rows: tuple[PriceRow, ...], league_id: str, row_filter: Callable[[PriceRow], bool] | None
) -> tuple[PriceRow, ...]:
    windowed = rows if row_filter is None else tuple(row for row in rows if row_filter(row))
    return _priced_rows(windowed, league_id)


def _quota_spent(quota: Quota, min_remaining: int) -> bool:
    """guard_quota'nın eşiği tek kaynaktır; tur erken kapanır ama toplanan iş kaybolmaz."""
    try:
        guard_quota(quota, min_remaining)
    except QuotaExhausted:
        LOGGER.warning(
            "kalan kredi %d < eşik %d — tur erken kapatıldı", quota.remaining, min_remaining
        )
        return True
    return False


def _write_league(
    conn: psycopg.Connection[Any],
    rows: tuple[PriceRow, ...],
    league_id: str,
    now: datetime,
    *,
    is_closing: bool,
) -> int:
    if not rows:
        LOGGER.info("lig=%s yazılacak satır yok", league_id)
        return 0
    upsert_matches(conn, rows, league_id)
    return insert_snapshots(conn, rows, now, is_closing=is_closing)


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
    row_filter: Callable[[PriceRow], bool] | None = None,
) -> CollectResult:
    written = 0
    quota: Quota | None = None
    failed: tuple[str, ...] = ()
    collected: tuple[str, ...] = ()
    spent = False
    for league in leagues:
        if quota is not None and _quota_spent(quota, min_remaining):
            spent = True
            break
        try:
            rows, quota = fetch_odds(
                client, api_key, league.odds_api_key, commence_time_to=commence_time_to
            )
            usable = _usable_rows(rows, league.id, row_filter)
            written += _write_league(conn, usable, league.id, now, is_closing=is_closing)
            conn.commit()
        except Exception:
            # Tek bir ligin arızası diğer liglerin kapanış oranını kaçırmasına yol açmamalı.
            # Kapanış oranı kaçarsa geri gelmez; bozuk bir lig ise sonraki turda tekrar denenir.
            conn.rollback()
            LOGGER.exception("lig=%s toplanamadı, diğer liglere devam ediliyor", league.id)
            failed = (*failed, league.id)
            continue
        collected = (*collected, league.id)
        LOGGER.info("lig=%s satır=%d kalan_kredi=%d", league.id, len(usable), quota.remaining)
    return CollectResult(
        written=written,
        quota=quota,
        failed_leagues=failed,
        collected_leagues=collected,
        quota_exhausted=spent,
    )


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


def _seal_candidates(
    conn: psycopg.Connection[Any], leagues: tuple[League, ...], now: datetime, window_minutes: int
) -> SealCandidates:
    """Mühürlenecek ligleri ve mührü KAÇMIŞ maçları aynı sorgudan çıkarır."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, league_id, commence_time FROM matches
            WHERE sealed_at IS NULL AND commence_time > %s - interval '1 day'
            """,
            (now,),
        )
        candidates = tuple((str(record[0]), str(record[1]), record[2]) for record in cur.fetchall())
    due = {
        league_id
        for _, league_id, commence_time in candidates
        if seal_window(commence_time, now, window_minutes)
    }
    # Başlama saati geçmiş ve hâlâ mühürsüz: cron kaydı, bir daha da gelmeyecek.
    missed = tuple(match_id for match_id, _, commence_time in candidates if commence_time < now)
    return SealCandidates(
        due=tuple(league for league in leagues if league.id in due), missed=missed
    )


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
    candidates = _seal_candidates(conn, leagues, now, window_minutes)
    if not candidates.due:
        LOGGER.info("mühürlenecek maç yok")
        return CollectResult(
            written=0, quota=None, failed_leagues=(), missed_seals=candidates.missed
        )
    result = _collect(
        conn,
        client,
        api_key,
        candidates.due,
        now,
        commence_time_to=horizon_iso(now, 1),
        is_closing=True,
        min_remaining=min_remaining,
        # 24 saatlik çekimin tamamı "kapanış" değildir: pencere dışı satır yazılmaz.
        row_filter=_seal_row_filter(now, window_minutes),
    )
    # Yalnız gerçekten toplanabilen ligler mühürlenmiş sayılır; başarısız ya da kredi
    # bitince hiç denenmemiş lig sealed_at almaz ki sonraki tur tekrar denesin.
    if result.collected_leagues:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE matches SET sealed_at = %s
                WHERE sealed_at IS NULL
                  AND league_id = ANY(%s)
                  AND commence_time BETWEEN %s AND %s
                """,
                (
                    now,
                    list(result.collected_leagues),
                    now,
                    now + timedelta(minutes=window_minutes),
                ),
            )
        conn.commit()
    return replace(result, missed_seals=candidates.missed)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} tanımlı değil")
    return value


def _normalised(record: dict[str, Any]) -> dict[str, Any]:
    # ── BU NORMALİZASYON LOAD-BEARING'DİR, SADELEŞTİRMEYİN ──────────────────
    # Zincir hash'i satırın kanonik JSON METNİNİ kapsıyor. Postgres aynı değeri
    # farklı Python tipiyle geri veriyor ve metin hâli değişiyor:
    #   numeric  → Decimal: json.dumps(Decimal) TypeError fırlatır; ayrıca
    #              yazarken float 2.40 → "2.4", okurken Decimal("2.40") → "2.40"
    #   timestamptz → datetime: yazma tarafı (db.snapshot_payload) ile okuma tarafı
    #              AYNI `canonical_timestamp` fonksiyonunu çağırır. Burada ikinci bir
    #              biçimlendirme yazılırsa iki taraf sessizce ayrışır — yasak.
    # Bu dönüşümler kaldırılırsa KURCALANMAMIŞ HER SATIR "KIRIK" der —
    # yanlış alarm, kaçırılan kurcalama kadar zararlıdır çünkü alarma güven biter.
    return {
        **record,
        "observed_at": canonical_timestamp(record["observed_at"]),
        "bookmaker_last_update": (
            None
            if record["bookmaker_last_update"] is None
            else canonical_timestamp(record["bookmaker_last_update"])
        ),
        "point": None if record["point"] is None else float(record["point"]),
        "price": float(record["price"]),
    }


def _ledger_rows(conn: psycopg.Connection[Any], after_id: int | None) -> tuple[dict[str, Any], ...]:
    """Defteri okur. `after_id` verilince yalnız çıpadan SONRAKİ kuyruk çekilir."""
    with conn.cursor() as cur:
        if after_id is None:
            cur.execute(_LEDGER_ALL)
        else:
            cur.execute(_LEDGER_AFTER, (after_id,))
        columns = [desc[0] for desc in cur.description or ()]
        records = tuple(dict(zip(columns, record, strict=True)) for record in cur.fetchall())
    return tuple(_normalised(record) for record in records)


def _anchor_break(conn: psycopg.Connection[Any], anchor: Anchor) -> str | None:
    """Çıpanın işaret ettiği satır hâlâ aynı hash'i taşıyor mu?

    TRUNCATE satır-seviyesi append-only tetikleyicisini ATEŞLEMEZ. Kuyruk kesilip aynı
    sayıda sahte satır eklenirse kalan zincir kendi içinde tutarlıdır ve satır sayısı da
    tutar — çıplak zincir doğrulaması bunu göremez. Arızayı yalnız dışarıda yayınlanmış
    hash gösterir.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM odds_snapshots")
        total = int((cur.fetchone() or (0,))[0])
        cur.execute("SELECT row_hash FROM odds_snapshots WHERE id = %s", (anchor.last_id,))
        found = cur.fetchone()
    if found is None:
        return f"çıpanın işaret ettiği satır (id={anchor.last_id}) defterde yok"
    if str(found[0]) != anchor.head:
        return f"id={anchor.last_id} satırının hash'i çıpadakinden farklı"
    if total < anchor.rows:
        return f"defterde {total} satır var, çıpa {anchor.rows} diyordu"
    return None


def _report_chain(result: ChainResult) -> int:
    sys.stdout.write(
        f"zincir: {'SAĞLAM' if result.ok else 'KIRIK'} "
        f"kontrol={result.checked} baş={result.head[:16]} hata={result.error}\n"
    )
    return 0 if result.ok else 1


def _verify_chain_command(conn: psycopg.Connection[Any], *, anchor_dir: Path = ANCHOR_DIR) -> int:
    anchor = _latest_anchor(anchor_dir)
    if anchor is None:
        # Atlanan kontrol geçmek değildir: sessiz kalınmaz, adıyla yazılır.
        sys.stdout.write("çıpa yok ya da okunamadı — kuyruk kesme kontrolü ATLANDI\n")
        return _report_chain(verify_chain(_ledger_rows(conn, None)))
    if anchor.last_id <= 0:
        # Boş defterin çıpası: kesilecek kuyruk yok, defter GENESIS'ten doğrulanır.
        return _report_chain(verify_chain(_ledger_rows(conn, None)))
    breakage = _anchor_break(conn, anchor)
    if breakage is not None:
        sys.stdout.write(f"ÇIPA UYUŞMAZLIĞI: {breakage} ({anchor.path.name})\n")
        return 1
    return _report_chain(verify_chain(_ledger_rows(conn, anchor.last_id), start_hash=anchor.head))


def _publish_head_command(
    conn: psycopg.Connection[Any], now: datetime, *, directory: Path = ANCHOR_DIR
) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*), coalesce(max(id), 0) FROM odds_snapshots")
        found = cur.fetchone() or (0, 0)
    count, last_id = int(found[0]), int(found[1])
    head = chain_head(conn)
    target = directory / f"head-{now:%Y-%m-%d}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    # last_id olmadan kuyruk kesme kontrolü kurulamaz: doğrulama nereden devam edeceğini bilemez.
    target.write_text(
        f"{now.isoformat()}\nrows={count}\nlast_id={last_id}\nhead={head}\n", encoding="utf-8"
    )
    sys.stdout.write(f"zincir başı yazıldı: {target}\n")
    return 0


def _report(result: CollectResult) -> int:
    remaining = "bilinmiyor" if result.quota is None else str(result.quota.remaining)
    sys.stdout.write(f"yazılan satır: {result.written}, kalan kredi: {remaining}\n")
    if result.missed_seals:
        # Kaçan mühür kalıcıdır; sessiz exit 0 arızayı gizler.
        sys.stdout.write("kaçan mühür: " + ", ".join(result.missed_seals) + "\n")
    if result.quota_exhausted:
        sys.stdout.write("kredi tükendi — tur erken kapandı\n")
        return 2
    if result.failed_leagues:
        # Diğer ligler toplandı ama bu sessizce geçilmemeli: CI kırmızı olmalı.
        sys.stdout.write("başarısız ligler: " + ", ".join(result.failed_leagues) + "\n")
        return 3
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

        api_key = _require_env("ODDS_API_KEY")
        configured = load_leagues(LEAGUES_PATH)
        # matches.league_id'nin yabancı anahtarı her turdan ÖNCE konfigürasyondan tazelenir.
        upsert_leagues(conn, configured)
        conn.commit()
        with httpx.Client() as client:
            # Ayrı if/else: run_snapshot ve run_seal farklı keyword argümanlara
            # sahip, tek değişkene atanınca mypy --strict uyumsuzluk bildirir.
            if args.command == "snapshot":
                result = run_snapshot(conn, client, api_key, active_leagues(configured), now)
            else:
                result = run_seal(conn, client, api_key, active_leagues(configured), now)
        return _report(result)


if __name__ == "__main__":
    raise SystemExit(main())
