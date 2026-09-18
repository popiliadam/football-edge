from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from football_edge.db import snapshot_payload
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
