"""`collect_venues` için bellek içi taklit.

`tests/fake_db.py:FakeLedgerDb` ne `matches.home_team` ne `source_observations`i taşıyor;
`tests/fake_obs_db.py:FakeObservationDb` ise `matches`i hiç bilmiyor (yalnız
`source_observations`). `collect_venues` İKİSİNE de dokunur (stadyum koordinatını
`source_observations`e yazar, ev sahibi maçları `matches`ten okur) — bu yüzden kendi,
küçük taklidi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

OBS_COLUMNS = ("source_id", "entity_kind", "entity_key", "observed_at", "payload", "content_hash")


@dataclass
class FakeVenuesDb:
    matches: dict[str, dict[str, Any]] = field(default_factory=dict)
    rows: list[dict[str, Any]] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0

    def cursor(self) -> _VenuesCursor:
        return _VenuesCursor(self)

    def commit(self) -> None:
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
            and start <= match["commence_time"] <= end
        ]
        self._result = sorted(due, key=lambda row: row[1])

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)
