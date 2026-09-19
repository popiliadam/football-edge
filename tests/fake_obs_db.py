"""`source_observations` için bellek içi taklit; UNIQUE kısıtını GERÇEKTEN uygular."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

OBS_COLUMNS = ("source_id", "entity_kind", "entity_key", "observed_at", "payload", "content_hash")


class CommitFailed(Exception):
    """COMMIT'in kendisi düştü, bağlantı AYAKTA — `tests/fake_db.py:CommitFailed` ile aynı
    desen (Minor #4 kanıtı: satırlar gider, sayaç ÖNCEDEN artmış olmamalı — G1)."""


@dataclass
class FakeObservationDb:
    rows: list[dict[str, Any]] = field(default_factory=list)
    statements: list[str] = field(default_factory=list)
    rollbacks: int = 0
    commits: int = 0
    # Minor #4 kanıtı: commit() BİLEREK düşürülebilir (varsayılan: hiç düşmez).
    commit_fails: Callable[[FakeObservationDb], bool] | None = None

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def commit(self) -> None:
        if self.commit_fails is not None and self.commit_fails(self):
            raise CommitFailed("COMMIT düştü, bağlantı ayakta")
        self.commits += 1

    def rollback(self) -> None:
        # `collect_footystats` (Task 5) lig başına izolasyonda `except Exception: conn.
        # rollback()` çağırıyor — sayaç, testin "arızalı lig rollback ETTİ mi" diye
        # doğrulamasına izin verir (fake_db.py:FakeLedgerDb.rollback ile aynı desen).
        self.rollbacks += 1

    def __enter__(self) -> FakeObservationDb:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _Cursor:
    def __init__(self, db: FakeObservationDb) -> None:
        self._db = db
        self.rowcount = -1
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        text = " ".join(sql.split())
        self._db.statements = [*self._db.statements, text]
        self.rowcount, self._result = 0, []
        if text.startswith("INSERT INTO source_observations"):
            self._execute_insert(params)
        elif text.startswith("SELECT DISTINCT ON (entity_key)"):
            self._execute_latest(params)
        else:
            raise AssertionError(f"taklit bu sorguyu tanımıyor: {text}")

    def _execute_insert(self, params: Any) -> None:
        keys = {
            (row["source_id"], row["entity_kind"], row["entity_key"], row["content_hash"])
            for row in self._db.rows
        }
        for index in range(len(params["content_hash"])):
            row = {name: params[name][index] for name in OBS_COLUMNS}
            key = (row["source_id"], row["entity_kind"], row["entity_key"], row["content_hash"])
            if key in keys:
                continue
            keys = keys | {key}
            self._db.rows = [*self._db.rows, row]
            self._result.append((row["entity_key"],))
        self.rowcount = len(self._result)

    def _execute_latest(self, params: Any) -> None:
        """`latest_observations`in `SELECT DISTINCT ON (entity_key) ... ORDER BY
        entity_key, observed_at DESC` sorgusunu taklit eder: kaynak+varlık türü başına
        entity_key başına yalnız EN YENİ satır.

        `write_observations` gerçek Postgres'e yazarken `payload`i JSON METNİ, `observed_at`i
        kanonik ISO METNİ olarak gönderiyor (unnest ile ::jsonb[]/::timestamptz[] cast'i
        Postgres tarafında oluyor); GERÇEK psycopg okurken bunları dict/datetime'a geri
        çevirir. Taklit bu satırı METİN hâlde saklıyor (bkz. `_execute_insert`) — okuma
        tarafı da GERÇEK sürücü gibi metinden nesneye dönmezse, `latest_observations`
        yalnız taklide karşı yeşil görünen ama gerçek veritabanına karşı patlayacak bir
        kodu gizler (fake_db.py:`stored_row`ın aynı gerekçesi).
        """
        source_id, entity_kind = params
        latest: dict[str, dict[str, Any]] = {}
        for row in self._db.rows:
            if row["source_id"] != source_id or row["entity_kind"] != entity_kind:
                continue
            key = row["entity_key"]
            current = latest.get(key)
            if current is None or row["observed_at"] > current["observed_at"]:
                latest[key] = row
        self._result = [
            (
                row["source_id"],
                row["entity_kind"],
                row["entity_key"],
                _as_datetime(row["observed_at"]),
                _as_dict(row["payload"]),
            )
            for row in latest.values()
        ]
        self.rowcount = len(self._result)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)


def _as_datetime(value: Any) -> Any:
    from datetime import datetime

    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))


def _as_dict(value: Any) -> dict[str, Any]:
    result: dict[str, Any] = value if isinstance(value, dict) else json.loads(value)
    return result
