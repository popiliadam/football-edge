"""Testler için çevrimdışı Postgres taklitleri.

Taklit, şemanın **yük taşıyan kısıtlarını** uygular: `matches.league_id` yabancı
anahtarı ve `odds_snapshots.price > 1.0` kontrolü. Kısıt uygulamayan bir taklit,
temiz veritabanında patlayan kodu yeşil gösterir — tam da E1/E6'nın gizlendiği yer.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from football_edge.ledger import GENESIS, canonical_timestamp, chain

LEDGER_COLUMNS = (
    "match_id",
    "observed_at",
    "bookmaker",
    "market",
    "outcome",
    "point",
    "price",
    "bookmaker_last_update",
    "is_closing",
    "prev_hash",
    "row_hash",
)


class ForeignKeyViolation(Exception):
    """matches.league_id → leagues(id): elle doldurulmamış tabloda gerçekten böyle patlar."""


class CheckViolation(Exception):
    """odds_snapshots.price > 1.0 kontrolü."""


def _as_datetime(value: Any) -> datetime:
    return datetime.fromisoformat(canonical_timestamp(value))


def stored_row(row: dict[str, Any]) -> dict[str, Any]:
    """Kanonik yükü, PSYCOPG'NİN GERİ VERDİĞİ tiplere çevirir: datetime ve Decimal.

    Kanonik metin ve düz float saklayan bir taklit, okuma tarafındaki `datetime` ve
    `Decimal` dallarını hiç çalıştırmaz: `json.dumps(Decimal)` TypeError fırlatır ve
    `Decimal("2.40")` ile float 2.40 aynı metni vermez. Testin önlediğini iddia ettiği
    arıza tam orada yaşıyor — taklit oraya kadar gitmezse test kendi konusunu ıskalar.
    """
    return {
        **row,
        "observed_at": _as_datetime(row["observed_at"]),
        "bookmaker_last_update": (
            None
            if row["bookmaker_last_update"] is None
            else _as_datetime(row["bookmaker_last_update"])
        ),
        "point": None if row["point"] is None else Decimal(str(row["point"])),
        "price": Decimal(str(row["price"])),
    }


def chained_rows(
    count: int, *, start_hash: str = GENESIS, bookmaker: str = "pinnacle", first_id: int = 1
) -> tuple[dict[str, Any], ...]:
    """Geçerli bir hash zinciri üretir; `bookmaker` içeriği değiştirip hash'leri ayırır.

    Hash kanonik yük üzerinden hesaplanır, saklanan satır Postgres tiplerini taşır.
    """
    payloads = tuple(
        {
            "match_id": f"evt{index}",
            "observed_at": canonical_timestamp(f"2026-09-19T12:0{index}:00Z"),
            "bookmaker": bookmaker,
            "market": "h2h",
            "outcome": "A",
            "point": None,
            "price": 1.90 + index / 100,
            "bookmaker_last_update": canonical_timestamp("2026-09-19T10:00:00Z"),
            "is_closing": False,
        }
        for index in range(count)
    )
    return tuple(
        {**stored_row(row), "id": index + first_id}
        for index, row in enumerate(chain(payloads, prev_hash=start_hash))
    )


@dataclass
class FakeLedgerDb:
    """leagues/matches/odds_snapshots tablolarını bellekte taklit eder."""

    leagues: dict[str, tuple[Any, ...]] = field(default_factory=dict)
    matches: dict[str, dict[str, Any]] = field(default_factory=dict)
    snapshots: list[dict[str, Any]] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0

    def __post_init__(self) -> None:
        self._committed = self._state()

    def _state(self) -> tuple[Any, ...]:
        return copy.deepcopy((self.leagues, self.matches, self.snapshots))

    def cursor(self) -> _LedgerCursor:
        return _LedgerCursor(self)

    def commit(self) -> None:
        self.commits += 1
        self._committed = self._state()

    def rollback(self) -> None:
        self.rollbacks += 1
        self.leagues, self.matches, self.snapshots = copy.deepcopy(self._committed)

    def __enter__(self) -> FakeLedgerDb:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def put_league(self, params: tuple[Any, ...]) -> int:
        self.leagues = {**self.leagues, str(params[0]): tuple(params)}
        return 1

    def put_match(self, params: tuple[Any, ...]) -> int:
        match_id, league_id = str(params[0]), str(params[1])
        if league_id not in self.leagues:
            raise ForeignKeyViolation(f'matches.league_id="{league_id}" leagues tablosunda yok')
        if match_id in self.matches:
            return 0
        self.matches = {
            **self.matches,
            match_id: {"league_id": league_id, "commence_time": params[2], "sealed_at": None},
        }
        return 1

    def put_snapshot(self, params: dict[str, Any]) -> int:
        if float(params["price"]) <= 1.0:
            raise CheckViolation(f"odds_snapshots.price={params['price']} check (price > 1.0)")
        if any(row["row_hash"] == params["row_hash"] for row in self.snapshots):
            return 0
        self.snapshots = [*self.snapshots, {**params, "id": len(self.snapshots) + 1}]
        return 1

    def seal(self, params: tuple[Any, ...]) -> int:
        now, match_ids = params
        sealed = 0
        for match_id, match in self.matches.items():
            if match["sealed_at"] is None and match_id in match_ids:
                match["sealed_at"] = now
                sealed += 1
        return sealed

    def head_row(self) -> list[tuple[Any, ...]]:
        return [(self.snapshots[-1]["row_hash"],)] if self.snapshots else []

    def seal_candidates(self, params: tuple[Any, ...], *, with_id: bool) -> list[tuple[Any, ...]]:
        """Sorgunun İSTEDİĞİ sütunları verir; taklit, kodun şeklini dayatmaz."""
        now = params[0]
        due = [
            (match_id, match["league_id"], match["commence_time"])
            for match_id, match in self.matches.items()
            if match["sealed_at"] is None and match["commence_time"] > now - timedelta(days=1)
        ]
        return due if with_id else [row[1:] for row in due]


class _LedgerCursor:
    def __init__(self, db: FakeLedgerDb) -> None:
        self._db = db
        self.rowcount = -1
        self.description: object = None
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _LedgerCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        text = " ".join(sql.split())
        self.rowcount, self._result = 0, []
        if text.startswith("INSERT INTO leagues"):
            self.rowcount = self._db.put_league(params)
        elif text.startswith("INSERT INTO matches"):
            self.rowcount = self._db.put_match(params)
        elif text.startswith("INSERT INTO odds_snapshots"):
            self.rowcount = self._db.put_snapshot(params)
        elif text.startswith("UPDATE matches SET sealed_at"):
            self.rowcount = self._db.seal(params)
        elif "FROM odds_snapshots ORDER BY id DESC" in text:
            self._result = self._db.head_row()
        elif "FROM matches" in text and "sealed_at IS NULL" in text:
            self._result = self._db.seal_candidates(params, with_id=text.startswith("SELECT id,"))
        else:
            raise AssertionError(f"taklit veritabanı bu sorguyu tanımıyor: {text}")

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._result[0] if self._result else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)


@dataclass
class FakeChainDb:
    """verify-chain / publish-head sorguları için salt-okunur defter taklidi."""

    rows: tuple[dict[str, Any], ...] = ()

    def cursor(self) -> _ChainCursor:
        return _ChainCursor(self)

    def commit(self) -> None:
        return None

    def __enter__(self) -> FakeChainDb:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _ChainCursor:
    def __init__(self, db: FakeChainDb) -> None:
        self._db = db
        self.description: object = None
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _ChainCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        text = " ".join(sql.split())
        self.description, self._result = None, []
        rows = self._db.rows
        if text.startswith("SELECT count(*), coalesce(max(id)"):
            self._result = [(len(rows), max((row["id"] for row in rows), default=0))]
        elif text.startswith("SELECT count(*)"):
            self._result = [(len(rows),)]
        elif text.startswith("SELECT row_hash"):
            self._result = [(rows[-1]["row_hash"],)] if rows else []
        elif text.startswith("SELECT match_id") and "WHERE id = %s" in text:
            self.description = tuple((name,) for name in LEDGER_COLUMNS)
            self._result = [
                tuple(row[name] for name in LEDGER_COLUMNS)
                for row in rows
                if row["id"] == params[0]
            ]
        elif text.startswith("SELECT match_id"):
            after = 0 if params is None else int(params[0])
            self.description = tuple((name,) for name in LEDGER_COLUMNS)
            self._result = [
                tuple(row[name] for name in LEDGER_COLUMNS) for row in rows if row["id"] > after
            ]
        else:
            raise AssertionError(f"taklit veritabanı bu sorguyu tanımıyor: {text}")

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._result[0] if self._result else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)


def utc(text: str) -> datetime:
    return datetime.fromisoformat(canonical_timestamp(text))
