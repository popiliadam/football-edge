"""`hist_files`/`hist_fetches` için bellek içi taklit (db/migrations/0006_history.sql).

Yük taşıyan kısıtları UYGULAR: NOT NULL sütunlar, `hist_files.path` birincil anahtarı (upsert) ve
`hist_fetches`in append-only oluşu (UPDATE/DELETE ifadesi tanınmaz). Commit/rollback gerçek bir
işlem gibi davranır: rollback commit'lenmemiş her yazmayı geri alır. `bytea` okunurken
`memoryview` döner — sürücünün ikili biçimde döndürdüğü tip; kod `bytes`a çevirmeyi unutursa
burada görünür.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

FILE_COLUMNS = (
    "path",
    "sha256",
    "fetched_at",
    "http_last_modified",
    "byte_size",
    "row_count",
    "content",
)
FETCH_COLUMNS = ("path", "fetched_at", "sha256", "http_status", "rows_parsed", "rows_rejected")
FILE_NULLABLE = frozenset({"http_last_modified"})
FETCH_NULLABLE = frozenset({"sha256", "http_status"})


class NotNullViolation(Exception):
    """Gerçek şemada NOT NULL olan sütuna None yazıldı."""


class CommitFailed(Exception):
    """COMMIT'in kendisi düştü, bağlantı ayakta (`tests/fake_db.py:CommitFailed` deseni)."""


@dataclass
class FakeHistDb:
    files: dict[str, dict[str, Any]] = field(default_factory=dict)
    fetches: list[dict[str, Any]] = field(default_factory=list)
    statements: list[str] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0
    commit_fails: Callable[[FakeHistDb], bool] | None = None

    def __post_init__(self) -> None:
        self._committed = copy.deepcopy((self.files, self.fetches))

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def commit(self) -> None:
        if self.commit_fails is not None and self.commit_fails(self):
            raise CommitFailed("COMMIT düştü, bağlantı ayakta")
        self.commits += 1
        self._committed = copy.deepcopy((self.files, self.fetches))

    def rollback(self) -> None:
        self.rollbacks += 1
        self.files, self.fetches = copy.deepcopy(self._committed)

    def __enter__(self) -> FakeHistDb:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _row(
    columns: tuple[str, ...], params: tuple[Any, ...], nullable: frozenset[str]
) -> dict[str, Any]:
    row = dict(zip(columns, params, strict=True))
    empty = sorted(name for name, value in row.items() if value is None and name not in nullable)
    if empty:
        raise NotNullViolation(f"NOT NULL ihlali: {empty}")
    return row


class _Cursor:
    def __init__(self, db: FakeHistDb) -> None:
        self._db = db
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        text = " ".join(sql.split())
        self._db.statements = [*self._db.statements, text]
        self._result = []
        if text == "SELECT sha256 FROM hist_files WHERE path = %s":
            found = self._db.files.get(params[0])
            self._result = [] if found is None else [(found["sha256"],)]
        elif text.startswith("INSERT INTO hist_files") and "ON CONFLICT (path) DO UPDATE" in text:
            row = _row(FILE_COLUMNS, params, FILE_NULLABLE)
            self._db.files = {**self._db.files, row["path"]: row}
        elif text.startswith("INSERT INTO hist_fetches"):
            self._db.fetches = [*self._db.fetches, _row(FETCH_COLUMNS, params, FETCH_NULLABLE)]
        elif text.startswith("SELECT path, sha256, fetched_at, content FROM hist_files WHERE"):
            wanted = set(params[0])
            self._result = [
                (row["path"], row["sha256"], row["fetched_at"], memoryview(row["content"]))
                for path, row in self._db.files.items()
                if path in wanted
            ]
        else:
            raise AssertionError(f"taklit bu sorguyu tanımıyor: {text}")

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._result[0] if self._result else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)


def at(minute: int) -> datetime:
    """Testlerin sabit saati: 2026-09-28 10:<minute> UTC."""
    return datetime(2026, 9, 28, 10, minute, tzinfo=UTC)
