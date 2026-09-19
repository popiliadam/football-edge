from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx

from football_edge.collect import _latest_anchor, horizon_iso, run_snapshot, seal_window
from football_edge.leagues import League
from football_edge.ledger import canonical_timestamp, chain, verify_chain

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def test_seal_window_true_just_before_kickoff() -> None:
    assert seal_window(NOW + timedelta(minutes=10), NOW, minutes=20) is True


def test_seal_window_false_when_far_away() -> None:
    assert seal_window(NOW + timedelta(hours=5), NOW, minutes=20) is False


def test_seal_window_false_after_kickoff() -> None:
    assert seal_window(NOW - timedelta(minutes=1), NOW, minutes=20) is False


def test_seal_window_true_at_exact_boundary() -> None:
    assert seal_window(NOW + timedelta(minutes=20), NOW, minutes=20) is True


def test_horizon_iso_formats_utc_with_z() -> None:
    assert horizon_iso(NOW, days=7) == "2026-09-26T12:00:00Z"


def test_latest_anchor_reads_newest_file(tmp_path: Path) -> None:
    (tmp_path / "head-2026-09-18.txt").write_text(
        "2026-09-18T00:00:00+00:00\nrows=10\nhead=aaa\n", encoding="utf-8"
    )
    (tmp_path / "head-2026-09-19.txt").write_text(
        "2026-09-19T00:00:00+00:00\nrows=25\nhead=bbb\n", encoding="utf-8"
    )
    anchor = _latest_anchor(tmp_path)
    assert anchor is not None
    assert anchor.rows == 25
    assert anchor.head == "bbb"


def test_latest_anchor_none_when_empty(tmp_path: Path) -> None:
    assert _latest_anchor(tmp_path) is None


def test_chain_survives_postgres_type_round_trip() -> None:
    written = {
        "match_id": "evt1",
        # Yazma tarafı (db.snapshot_payload) ile AYNI fonksiyon.
        "observed_at": canonical_timestamp("2026-09-19T12:00:00+00:00"),
        "bookmaker": "pinnacle",
        "market": "h2h",
        "outcome": "A",
        "point": None,
        "price": 2.40,
        "bookmaker_last_update": canonical_timestamp("2026-09-19T10:00:00Z"),
        "is_closing": False,
    }
    linked = chain((written,))

    # Postgres'ten dönüş: numeric -> Decimal, timestamptz -> datetime
    from_db = {
        **linked[0],
        "observed_at": datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
        "bookmaker_last_update": datetime(2026, 9, 19, 10, 0, tzinfo=UTC),
        "price": Decimal("2.40"),
        "point": None,
    }
    # verify-chain komutunun uyguladığı normalizasyonun aynısı
    normalised = {
        **from_db,
        "observed_at": canonical_timestamp(from_db["observed_at"]),
        "bookmaker_last_update": canonical_timestamp(from_db["bookmaker_last_update"]),
        "price": float(from_db["price"]),
        "point": None,
    }
    assert verify_chain((normalised,)).ok is True, "DB turu sonrası zincir kırılmamalı"


class _FakeCursor:
    def __init__(self, recorder: list[str]) -> None:
        self._recorder = recorder
        self.description: object = None
        # psycopg imleci her execute'tan sonra rowcount verir; öncesinde -1'dir.
        # db.insert_snapshots/upsert_matches bu sayıyı topluyor, taklit de vermeli.
        self.rowcount = -1

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: object = None) -> None:
        verb = sql.strip().split()[0].upper()
        self._recorder.append(verb)
        self.rowcount = 1 if verb == "INSERT" else 0

    def fetchone(self) -> None:
        return None

    def fetchall(self) -> list[object]:
        return []


class _FakeConn:
    def __init__(self) -> None:
        self.sql: list[str] = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self.sql)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


ODDS_PAYLOAD = [
    {
        "id": "evt1",
        "sport_key": "soccer_good",
        "commence_time": "2026-09-20T14:00:00Z",
        "home_team": "A",
        "away_team": "B",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "last_update": "2026-09-19T10:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [{"name": "A", "price": 1.9}, {"name": "B", "price": 4.0}],
                    }
                ],
            }
        ],
    }
]
QUOTA_HEADERS = {
    "x-requests-remaining": "400",
    "x-requests-used": "100",
    "x-requests-last": "1",
}


def _league(league_id: str, key: str) -> League:
    return League(
        id=league_id, odds_api_key=key, name=key, country="X", lang="en", gl="GB", active=True
    )


def test_collect_isolates_a_failing_league() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "soccer_bad" in str(request.url):
            return httpx.Response(500, json={"message": "boom"})
        return httpx.Response(200, json=ODDS_PAYLOAD, headers=QUOTA_HEADERS)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    leagues = (_league("bad.1", "soccer_bad"), _league("good.1", "soccer_good"))
    conn = _FakeConn()

    result = run_snapshot(conn, client, "KEY", leagues, NOW)  # type: ignore[arg-type]

    assert result.failed_leagues == ("bad.1",)
    assert result.written > 0, "sağlam lig yine de yazılmalıydı"
    assert conn.rollbacks == 1
    assert conn.commits == 1
