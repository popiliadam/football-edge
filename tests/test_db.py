from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime
from functools import lru_cache

import pytest

from football_edge.collect import _ledger_rows
from football_edge.db import (
    LEDGER_LOCK_KEY,
    insert_snapshots,
    snapshot_payload,
    upsert_matches,
)
from football_edge.ledger import chain, verify_chain
from football_edge.odds_api import PriceRow
from tests.fake_db import FakeChainDb, FakeLedgerDb, stored_row

ROW = PriceRow(
    event_id="abc123",
    sport_key="soccer_epl",
    commence_time="2026-09-20T14:00:00Z",
    home_team="Arsenal",
    away_team="Chelsea",
    bookmaker="pinnacle",
    bookmaker_last_update="2026-09-19T10:00:00Z",
    market="h2h",
    outcome="Arsenal",
    point=None,
    price=1.95,
)
OBSERVED = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def test_snapshot_payload_has_stable_keys() -> None:
    payload = snapshot_payload(ROW, OBSERVED, is_closing=False)
    assert set(payload) == {
        "match_id",
        "observed_at",
        "bookmaker",
        "market",
        "outcome",
        "point",
        "price",
        "bookmaker_last_update",
        "is_closing",
    }


def test_snapshot_payload_serialises_time_as_iso() -> None:
    payload = snapshot_payload(ROW, OBSERVED, is_closing=True)
    assert payload["observed_at"] == "2026-09-19T12:00:00+00:00"
    assert payload["is_closing"] is True
    assert payload["match_id"] == "abc123"


def test_snapshot_payload_excludes_chain_fields() -> None:
    payload = snapshot_payload(ROW, OBSERVED, is_closing=False)
    assert "row_hash" not in payload
    assert "prev_hash" not in payload


@pytest.mark.parametrize(
    "upstream_last_update",
    [
        "2026-09-19T10:00:00Z",
        "2026-09-19T10:00:00.123456Z",
        "2026-09-19T12:00:00+02:00",
    ],
)
def test_chain_survives_round_trip_through_postgres_types(upstream_last_update: str) -> None:
    """Yazma tarafı metin görür, okuma tarafı datetime/Decimal — zincir yine SAĞLAM olmalı.

    Bu testin yakaladığı arıza: yazarken hash'lenen metin ile geri okunduğunda üretilen
    metin ayrışırsa, KURCALANMAMIŞ her satır "KIRIK" der. Yanlış alarm kaçırılan
    kurcalamadan zararlıdır, çünkü bir süre sonra alarma kimse bakmaz.

    Normalizasyon burada YENİDEN YAZILMAZ; okuma yolunun kendisi (`_ledger_rows` →
    `_normalised`) koşturulur. Kopyalanmış bir normalizasyon yalnız aynı kodu iki kez
    yazabildiğimizi kanıtlar — asıl fonksiyon bozulsa test yine yeşil kalırdı.
    """
    row = replace(ROW, bookmaker_last_update=upstream_last_update)
    written = chain((snapshot_payload(row, OBSERVED, is_closing=False),))
    db = FakeChainDb(({**stored_row(written[0]), "id": 1},))

    result = verify_chain(_ledger_rows(db, None))  # type: ignore[arg-type]

    assert result.ok is True, result.error


class _SkippingCursor:
    """ON CONFLICT DO NOTHING'i taklit eder: INSERT başına 1 (yazıldı) ya da 0 (düştü)."""

    def __init__(self, outcomes: list[int]) -> None:
        self._outcomes = outcomes
        self.rowcount = -1

    def __enter__(self) -> _SkippingCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: object = None) -> None:
        self.rowcount = 0 if sql.strip().upper().startswith("SELECT") else self._outcomes.pop(0)

    def fetchone(self) -> None:
        return None


class _SkippingConn:
    def __init__(self, outcomes: list[int]) -> None:
        self._cursor = _SkippingCursor(outcomes)

    def cursor(self) -> _SkippingCursor:
        return self._cursor


def test_insert_snapshots_names_only_matches_actually_written() -> None:
    """Denenen satır değil yazılan satır sayılır; yoksa no-op batch dolu görünür.

    F1: dönen değer sayı değil KİMLİK — tek satırı ON CONFLICT ile düşen maç
    "yazıldı" sayılırsa mührü basılır ve kapanış fiyatı bir daha aranmaz.
    """
    rows = (
        ROW,
        replace(ROW, event_id="def456", outcome="Chelsea"),
        replace(ROW, bookmaker="betfair_ex_eu"),
    )
    conn = _SkippingConn([1, 0, 1])

    written = insert_snapshots(conn, rows, OBSERVED, is_closing=False)  # type: ignore[arg-type]

    assert written == ("abc123", "abc123"), "ON CONFLICT ile düşen satır yazılmış sayılmamalı"
    assert "def456" not in written, "tek satırı düşen maç yazılmış sayılamaz"


# ── C2: iki eşzamanlı yazar zinciri KALICI olarak kırıyordu ─────────────────
# `insert_snapshots` önce zincir başını OKUR, sonra ondan zincirleyip YAZAR.
# READ COMMITTED altında iki yazar aynı başı okur ve ikisi de ondan zincirler.
# UNIQUE (row_hash) bunu YAKALAMAZ: yükler farklı → hash'ler farklı. İkisi de
# commit eder, `verify_chain` "prev_hash zincire uymuyor" der ve bu KALICIDIR —
# append-only tetikleyici bozuk satırı sildirmez, `verify-chain` exit 1 de
# `publish-head`i durdurur, yani kanıt üretimi biter.
#
# Bugün ulaşılabilir: iki cron aynı concurrency grubunda, ama dizüstünden elle
# koşulan bir `collect snapshot` o grubun içinde değildir.


def _index_of(statements: list[str], needle: str) -> int | None:
    for index, text in enumerate(statements):
        if needle in text:
            return index
    return None


def test_insert_snapshots_locks_the_ledger_before_reading_the_chain_head() -> None:
    """Kilit, BAŞ OKUMASINDAN önce alınmalı — sonra alınırsa hiçbir şey serileşmez."""
    db = FakeLedgerDb(leagues={"eng.1": ("eng.1",)})

    insert_snapshots(db, (ROW,), OBSERVED, is_closing=False)  # type: ignore[arg-type]

    lock = _index_of(db.statements, "pg_advisory_xact_lock")
    head = _index_of(db.statements, "SELECT row_hash FROM odds_snapshots")
    assert lock is not None, "defter kilidi hiç alınmıyor: iki yazar aynı baştan zincirler"
    assert head is not None, "baş okuması hiç koşmadı — test kurgusu bayatlamış"
    assert lock < head, (
        f"kilit baş okumasından SONRA alınmış (kilit={lock}, baş={head}): "
        "iki yazar da başı okuduktan sonra sıraya girer, zincir yine çatallanır"
    )


def test_insert_snapshots_takes_the_one_shared_lock_key() -> None:
    """Anahtar SABİT ve paylaşımlı olmalı; yazar başına farklı anahtar kimseyi bekletmez."""
    db = FakeLedgerDb(leagues={"eng.1": ("eng.1",)})

    insert_snapshots(db, (ROW,), OBSERVED, is_closing=False)  # type: ignore[arg-type]

    assert db.lock_keys == [LEDGER_LOCK_KEY], (
        f"kilit anahtarı modül sabiti değil: {db.lock_keys!r} — yazarlar serileşmez"
    )


def test_upsert_matches_counts_only_rows_actually_written() -> None:
    rows = (ROW, replace(ROW, event_id="def456"))
    conn = _SkippingConn([1, 0])

    written = upsert_matches(conn, rows, "eng.1")  # type: ignore[arg-type]

    assert written == 1, "zaten var olan maç yeniden yazılmış sayılmamalı"


@lru_cache(maxsize=1)
def _live_ledger_row_id() -> int | None:
    """Bu iki testin GERÇEK ön koşulu: ULAŞILABİLİR veritabanı + en az bir defter satırı.

    Guard yalnız `DATABASE_URL`in TANIMLI olmasına bakıyordu (G5). Sahte bir DSN ile iki
    test skip'ten çıkıp `psycopg.OperationalError` ile KIRMIZI veriyordu
    (`2 failed, 69 passed`) — ortam yanlış kurulduğu için kırmızı veren test, insanlara
    kırmızıyı görmezden gelmeyi öğretir.

    Ulaşılamayan veritabanı BURADA yutulur ama kapıda yutulmaz: `verify.sh`'ın `zincir`
    adımı `DATABASE_URL` tanımlıyken koşar ve bağlantı kurulamazsa adıyla kırmızı verir.
    """
    if not os.getenv("DATABASE_URL"):
        return None
    try:
        from football_edge.db import connect

        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM odds_snapshots LIMIT 1")
            found = cur.fetchone()
    except Exception:  # OperationalError, DNS, kapalı port, eksik tablo — hepsi "yok".
        return None
    return None if found is None else int(found[0])


NO_LEDGER = "ulaşılabilir veritabanı + dolu defter yok (DATABASE_URL, bağlantı ya da satır)"


@pytest.mark.skipif(_live_ledger_row_id() is None, reason=NO_LEDGER)
def test_append_only_trigger_blocks_update() -> None:
    import psycopg

    from football_edge.db import connect

    row_id = _live_ledger_row_id()
    with (
        connect() as conn,
        conn.cursor() as cur,
        pytest.raises(psycopg.errors.RaiseException, match="append-only"),
    ):
        cur.execute("UPDATE odds_snapshots SET price = 9.99 WHERE id = %s", (row_id,))


@pytest.mark.skipif(_live_ledger_row_id() is None, reason=NO_LEDGER)
def test_append_only_trigger_blocks_delete() -> None:
    import psycopg

    from football_edge.db import connect

    row_id = _live_ledger_row_id()
    with (
        connect() as conn,
        conn.cursor() as cur,
        pytest.raises(psycopg.errors.RaiseException, match="append-only"),
    ):
        cur.execute("DELETE FROM odds_snapshots WHERE id = %s", (row_id,))
