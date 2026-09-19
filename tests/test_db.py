from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from football_edge.db import insert_snapshots, snapshot_payload, upsert_matches
from football_edge.ledger import canonical_timestamp, chain, verify_chain
from football_edge.odds_api import PriceRow

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
    """
    row = replace(ROW, bookmaker_last_update=upstream_last_update)
    written = chain((snapshot_payload(row, OBSERVED, is_closing=False),))

    # Postgres'in geri verdiği tipler: timestamptz → datetime (UTC), numeric → Decimal.
    stored = {
        **written[0],
        "observed_at": OBSERVED,
        "bookmaker_last_update": datetime.fromisoformat(
            upstream_last_update.replace("Z", "+00:00")
        ).astimezone(UTC),
        "price": Decimal("1.95"),
    }

    # _verify_chain_command ile BİREBİR aynı normalizasyon.
    normalised = {
        **stored,
        "observed_at": canonical_timestamp(stored["observed_at"]),
        "bookmaker_last_update": canonical_timestamp(stored["bookmaker_last_update"]),
        "point": None if stored["point"] is None else float(stored["point"]),
        "price": float(stored["price"]),
    }

    result = verify_chain((normalised,))
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


def test_insert_snapshots_counts_only_rows_actually_written() -> None:
    """Denenen satır değil yazılan satır sayılır; yoksa no-op batch dolu görünür."""
    rows = (
        ROW,
        replace(ROW, outcome="Chelsea"),
        replace(ROW, bookmaker="betfair_ex_eu"),
    )
    conn = _SkippingConn([1, 0, 1])

    written = insert_snapshots(conn, rows, OBSERVED, is_closing=False)  # type: ignore[arg-type]

    assert written == 2, "ON CONFLICT ile düşen satır yazılmış sayılmamalı"


def test_upsert_matches_counts_only_rows_actually_written() -> None:
    rows = (ROW, replace(ROW, event_id="def456"))
    conn = _SkippingConn([1, 0])

    written = upsert_matches(conn, rows, "eng.1")  # type: ignore[arg-type]

    assert written == 1, "zaten var olan maç yeniden yazılmış sayılmamalı"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL yok")
def test_append_only_trigger_blocks_update() -> None:
    import psycopg

    from football_edge.db import connect

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM odds_snapshots LIMIT 1")
        found = cur.fetchone()
        if found is None:
            pytest.skip("defter boş")
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            cur.execute("UPDATE odds_snapshots SET price = 9.99 WHERE id = %s", (found[0],))


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL yok")
def test_append_only_trigger_blocks_delete() -> None:
    import psycopg

    from football_edge.db import connect

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM odds_snapshots LIMIT 1")
        found = cur.fetchone()
        if found is None:
            pytest.skip("defter boş")
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            cur.execute("DELETE FROM odds_snapshots WHERE id = %s", (found[0],))
