"""`site export`in okuduğu görünümlerin bellekteki taklidi (0014'ün süzgeçleriyle aynı kurallar).

Taklit görünüm MANTIĞINI taşır — pasif lig düşer, taban süzer, `book_key` tur içinde kitap sırası —
çünkü dışa aktarıcının birim testleri gerçek Postgres'siz koşar. Gerçek SQL'e karşı aynı yol
`tests/test_site_e2e_db.py`de kapta koşar.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from football_edge.site.contract import PUBLIC_FLOOR, RECORD_COLUMNS
from tests.fake_db import LEDGER_COLUMNS


@dataclass
class FakeSiteDb:
    leagues: Sequence[tuple[str, str, str, bool]]  # id, name, country, active
    matches: Sequence[tuple[str, str, datetime, str, str]]  # id, league_id, başlama, ev, dep.
    ledger: Sequence[dict[str, Any]]  # `tests.site_builders.ledger` satırları
    record: Sequence[tuple[Any, ...]] = ()
    isolation: tuple[str, str] = ("repeatable read", "on")
    floor: datetime = PUBLIC_FLOOR
    head_rows: int | None = None  # site.ledger_head.rows'u ezmek için (sahiplik arızası)
    head_last_id: int | None = None  # site.ledger_head.last_id'yi ezmek için
    queries: list[str] = field(default_factory=list)
    isolation_level: Any = None
    read_only: bool | None = None
    transactions: int = 0  # açılan işlem sayısı (B12: tek işlem)
    depth: int = 0  # açık işlem derinliği; 0'da gelen sorgu reddedilir

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.transactions += 1
        self.depth += 1
        try:
            yield
        finally:
            self.depth -= 1

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def site_matches(self) -> list[tuple[str, str, datetime, str, str]]:
        active = {league[0] for league in self.leagues if league[3]}
        return sorted(
            (row for row in self.matches if row[1] in active and row[2] >= PUBLIC_FLOOR),
            key=lambda row: row[0],
        )

    def h2h_quotes(self) -> list[tuple[Any, ...]]:
        shown = {row[0] for row in self.site_matches()}
        found = []
        for row in self.ledger:
            if row["market"] != "h2h" or row["match_id"] not in shown:
                continue
            books = sorted(
                {
                    other["bookmaker"]
                    for other in self.ledger
                    if other["match_id"] == row["match_id"]
                    and other["observed_at"] == row["observed_at"]
                    and other["market"] == "h2h"
                }
            )
            found.append(
                (
                    row["id"],
                    row["match_id"],
                    row["observed_at"],
                    row["is_closing"],
                    row["outcome"],
                    row["price"],
                    books.index(row["bookmaker"]) + 1,
                )
            )
        return found


class _Cursor:
    def __init__(self, db: FakeSiteDb) -> None:
        self._db = db
        self.description: Any = None
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        text = " ".join(sql.split())
        if self._db.depth == 0:
            # B12: zincir ve döküm aynı anlık görüntüden okunmalı; işlem dışı sorgu kesimi böler.
            raise AssertionError(f"işlem dışında sorgu: {text}")
        self._db.queries.append(text)
        db, self.description = self._db, None
        rows = db.ledger
        if text.startswith("SELECT current_setting('transaction_isolation')"):
            self._result = [db.isolation]
        elif text == "SELECT count(*) FROM site_audit.ledger_rows":
            self._result = [(len(rows),)]
        elif text == "SELECT coalesce(max(id), 0) FROM site_audit.ledger_rows":
            self._result = [(max((row["id"] for row in rows), default=0),)]
        elif text.startswith("SELECT match_id") and "FROM site_audit.ledger_rows" in text:
            self.description = tuple((name,) for name in LEDGER_COLUMNS)
            wanted = [row for row in rows if "WHERE id = %s" not in text or row["id"] == params[0]]
            self._result = [tuple(row[name] for name in LEDGER_COLUMNS) for row in wanted]
        elif text == "SELECT site.public_floor()":
            self._result = [(db.floor,)]
        elif text == "SELECT rows, last_id, head FROM site.ledger_head":
            count = len(rows) if db.head_rows is None else db.head_rows
            last = max((row["id"] for row in rows), default=0)
            last = last if db.head_last_id is None else db.head_last_id
            head = rows[-1]["row_hash"] if rows else "0" * 64
            self._result = [(count, last, head)]
        elif text.startswith("SELECT id, name, country FROM site.leagues"):
            self._result = sorted((lg[0], lg[1], lg[2]) for lg in db.leagues if lg[3])
        elif text.startswith("SELECT id, league_id, commence_time"):
            self._result = list(db.site_matches())
        elif "FROM site_input.h2h_quotes" in text:
            self._result = [row for row in db.h2h_quotes() if row[0] <= params[0]]
        elif text.startswith(f"SELECT {RECORD_COLUMNS[0][0]}"):
            self._result = list(db.record)
        else:
            raise AssertionError(f"taklit bu sorguyu tanımıyor: {text}")

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._result[0] if self._result else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)
