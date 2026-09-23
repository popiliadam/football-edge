"""Haber deposu (`source_observations`, `news_items`, `jev_item_answers`, `matches`) için bellek içi
taklit; UNIQUE kısıtlarını GERÇEKTEN uygular.

Sorguların WHERE ve ORDER BY'ı da uygulanır: süzmeyen bir taklit, yanlış kaynağı ya da yanlış
dönemi okuyan kodu yeşil gösterirdi. `now` veritabanı saatidir (`now()`): `news_items` INSERT'i
canlı satırda `available_at = greatest(now, published_at_claimed)` ve `first_seen_at = now` yazar
ve 0012'nin zaman kısıtlarını uygular.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

NEWS_COLUMNS = (
    "source_id",
    "lang",
    "title",
    "body",
    "url",
    "published_at_claimed",
    "available_at",
    "availability_basis",
    "content_hash",
)
ANSWER_COLUMNS = (
    "item_id",
    "prompt_version",
    "question_id",
    "choice",
    "probabilities",
    "confidence",
    "match_id",
    "jev_model",
    "asked_at",
    "cost_usd",
)


@dataclass
class FakeNewsDb:
    observations: list[dict[str, Any]] = field(default_factory=list)
    news: list[dict[str, Any]] = field(default_factory=list)
    answers: list[dict[str, Any]] = field(default_factory=list)
    fixtures: list[tuple[str, str, datetime, str, str]] = field(default_factory=list)
    statements: list[str] = field(default_factory=list)
    commits: int = 0
    autocommit: bool = False
    now: datetime = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)

    def observe(
        self, source_id: str, observed_at: datetime, payload: dict[str, Any], kind: str = "news"
    ) -> None:
        row = {
            "id": len(self.observations) + 1,
            "source_id": source_id,
            "entity_kind": kind,
            "observed_at": observed_at,
            "payload": payload,
        }
        self.observations = [*self.observations, row]

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        return None

    def __enter__(self) -> FakeNewsDb:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _Cursor:
    def __init__(self, db: FakeNewsDb) -> None:
        self._db = db
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        text = " ".join(sql.split())
        self._db.statements = [*self._db.statements, text]
        if text.startswith("SELECT source_id, observed_at, payload FROM source_observations"):
            self._select_observations(params)
        elif text.startswith("INSERT INTO news_items"):
            self._insert_news(params)
        elif text.startswith("SELECT id, source_id, lang") and "FROM news_items" in text:
            self._select_news(params)
        elif text.startswith("SELECT DISTINCT item_id FROM jev_item_answers"):
            self._select_asked(params)
        elif text.startswith("SELECT item_id, count(*) FROM jev_item_answers"):
            self._select_attempts(params)
        elif text.startswith("INSERT INTO jev_item_answers"):
            self._insert_answers(params)
        elif text.startswith("SELECT id, league_id, commence_time, home_team, away_team"):
            self._select_fixtures(params)
        else:
            raise AssertionError(f"taklit bu sorguyu tanımıyor: {text}")

    def _select_observations(self, params: Any) -> None:
        kind, sources, since = params
        rows = sorted(
            (
                row
                for row in self._db.observations
                if row["entity_kind"] == kind
                and row["source_id"] in sources
                and row["observed_at"] >= since
            ),
            key=lambda row: (row["observed_at"], row["id"]),
        )
        self._result = [(row["source_id"], row["observed_at"], row["payload"]) for row in rows]

    def _insert_news(self, params: Any) -> None:
        keys = {(row["source_id"], row["content_hash"]) for row in self._db.news}
        self._result = []
        for index in range(len(params["content_hash"])):
            row = {name: params[name][index] for name in NEWS_COLUMNS}
            key = (row["source_id"], row["content_hash"])
            if key in keys:
                continue
            keys = keys | {key}
            stored = {"id": len(self._db.news) + 1, **_timed(row, self._db.now)}
            self._db.news = [*self._db.news, stored]
            self._result.append((stored["id"],))

    def _select_news(self, params: Any) -> None:
        (since,) = params
        rows = sorted(
            (row for row in self._db.news if row["available_at"] >= since),
            key=lambda row: (row["available_at"], row["id"]),
        )
        self._result = [
            (row["id"], *(row[name] for name in NEWS_COLUMNS), row["first_seen_at"]) for row in rows
        ]

    def _select_asked(self, params: Any) -> None:
        prompt_version, item_ids, failed_prefix = params
        found = {
            row["item_id"]
            for row in self._db.answers
            if row["prompt_version"] == prompt_version
            and row["item_id"] in item_ids
            and not row["question_id"].startswith(failed_prefix)
        }
        self._result = [(item_id,) for item_id in sorted(found)]

    def _select_attempts(self, params: Any) -> None:
        prompt_version, item_ids, failed_prefix = params
        counts: dict[int, int] = {}
        for row in self._db.answers:
            if (
                row["prompt_version"] == prompt_version
                and row["item_id"] in item_ids
                and row["question_id"].startswith(failed_prefix)
            ):
                counts[row["item_id"]] = counts.get(row["item_id"], 0) + 1
        self._result = sorted(counts.items())

    def _insert_answers(self, params: Any) -> None:
        keys = {(r["item_id"], r["prompt_version"], r["question_id"]) for r in self._db.answers}
        news_ids = {row["id"] for row in self._db.news}
        self._result = []
        for index in range(len(params["item_id"])):
            row = {name: params[name][index] for name in ANSWER_COLUMNS}
            # Gerçek şemanın yük taşıyan kısıtları: yabancı anahtar ve olasılıkların JSON nesnesi.
            if row["item_id"] not in news_ids:
                raise AssertionError(f"news_items'ta olmayan haber: {row['item_id']}")
            if not isinstance(json.loads(row["probabilities"]), dict):
                raise AssertionError("probabilities bir JSON nesnesi değil")
            key = (row["item_id"], row["prompt_version"], row["question_id"])
            if key in keys:
                continue
            keys = keys | {key}
            self._db.answers = [*self._db.answers, row]
            self._result.append((row["item_id"],))

    def _select_fixtures(self, params: Any) -> None:
        since, until = params
        rows = [fixture for fixture in self._db.fixtures if since < fixture[2] <= until]
        self._result = sorted(rows, key=lambda fixture: (fixture[2], fixture[0]))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)


def _timed(row: dict[str, Any], now: datetime) -> dict[str, Any]:
    """INSERT_NEWS'in CASE/greatest'ı ve 0012'nin `news_items` zaman kısıtları."""
    claimed = row["published_at_claimed"]
    if row["availability_basis"] == "observed":
        available = now if claimed is None else max(now, claimed)
    else:
        available = row["available_at"]
        if claimed is None or available < claimed:
            raise AssertionError("0012: arşiv satırı iddia ister ve available_at ≥ iddia")
    return {**row, "available_at": available, "first_seen_at": now}
