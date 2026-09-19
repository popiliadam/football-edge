"""`collect_venues` için bellek içi taklit.

`tests/fake_db.py:FakeLedgerDb` ne `matches.home_team` ne `source_observations`i taşıyor;
`tests/fake_obs_db.py:FakeObservationDb` ise `matches`i hiç bilmiyor (yalnız
`source_observations`). `collect_venues` İKİSİNE de dokunur (stadyum koordinatını
`source_observations`e yazar, ev sahibi maçları `matches`ten okur) — bu yüzden kendi,
küçük taklidi.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

OBS_COLUMNS = ("source_id", "entity_kind", "entity_key", "observed_at", "payload", "content_hash")


class CommitFailed(Exception):
    """COMMIT'in kendisi düştü, bağlantı AYAKTA — `tests/fake_db.py:CommitFailed` ile aynı
    desen (Minor #4 kanıtı: satırlar gider, `written` ÖNCEDEN artmış olmamalı — G1)."""


@dataclass
class FakeVenuesDb:
    matches: dict[str, dict[str, Any]] = field(default_factory=dict)
    rows: list[dict[str, Any]] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0
    # Minor #4 kanıtı: commit() BİLEREK düşürülebilir (varsayılan: hiç düşmez).
    commit_fails: Callable[[FakeVenuesDb], bool] | None = None
    # Minor #3 kanıtı: `_due_matches`in SQL'i BİLEREK düşürülebilir — sorgunun collect_venues
    # içinde İZOLE edildiğini (venue try'ının İÇİNDE, dışına sızmadan) sınamak için.
    due_query_fails: bool = False

    def cursor(self) -> _VenuesCursor:
        return _VenuesCursor(self)

    def commit(self) -> None:
        if self.commit_fails is not None and self.commit_fails(self):
            raise CommitFailed("COMMIT düştü, bağlantı ayakta")
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def __enter__(self) -> FakeVenuesDb:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _VenuesCursor:
    def __init__(self, db: FakeVenuesDb) -> None:
        self._db = db
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _VenuesCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        text = " ".join(sql.split())
        self._result = []
        if text.startswith("INSERT INTO source_observations"):
            self._execute_insert(params)
        elif text.startswith("SELECT id, commence_time FROM matches"):
            if self._db.due_query_fails:
                raise RuntimeError("_due_matches sorgusu düştü (taklit, Minor #3 kanıtı)")
            self._execute_due(params)
        else:
            raise AssertionError(f"taklit veritabanı bu sorguyu tanımıyor: {text}")

    def _execute_insert(self, params: dict[str, list[Any]]) -> None:
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

    def _execute_due(self, params: tuple[Any, ...]) -> None:
        home_team, start, end = params
        due = [
            (match_id, match["commence_time"])
            for match_id, match in self._db.matches.items()
            if match["home_team"] == home_team
            and match["sealed_at"] is None
            and _in_window(match["commence_time"], start, end)
        ]
        self._result = sorted(due, key=lambda row: row[1])

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)


def _in_window(commence_time: Any, start: Any, end: Any) -> bool:
    """Gerçek Postgres'te `commence_time` HER ZAMAN aware'dir (`timestamptz` sütunu); naive
    bir değer BURAYA hiçbir zaman gelmez. Bazı testler (Minor #2 kanıtı,
    `collect_venues`in KENDİSİNİN naive bir `commence_time`i reddettiğini sınamak için)
    BİLEREK sentetik bir naive değer veriyor — bu taklit SQL `BETWEEN`i birebir taklit
    etmeye çalışıp `TypeError` ile çökmemeli; asıl iddia production kodunun guard'ı,
    taklidin karşılaştırma mantığı değil. Naive bir değer bu yüzden pencere içi SAYILIR
    (üretim kodu zaten ondan önce reddetmiş olmalı — bu, testin GERÇEK iddiasıdır)."""
    if commence_time.tzinfo is None:
        return True
    return bool(start <= commence_time <= end)
