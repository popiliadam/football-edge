"""Kademe 2 sorguları için `FakeNewsDb` genişlemesi (Plan 2 Task 3; Task 4 dilim sorgusunu ekler).

Gölge satırları (`model_predictions` — YALNIZ varlık: maç, strateji, karar anı), `matches` adları,
kademe 1 cevap okuması ve `jev_match_answers` (tekil ve yabancı anahtar GERÇEKTEN uygulanır).
Tanımadığı sorguyu `FakeNewsDb`ye bırakır; o da tanımazsa reddeder. `SET TRANSACTION READ ONLY`den
sonra her INSERT reddedilir.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from tests.fake_news_db import FakeNewsDb, _Cursor

MATCH_ANSWER_COLUMNS = (
    "match_id",
    "decided_at",
    "prompt_version",
    "question_id",
    "variant",
    "item_set_hash",
    "choice",
    "probabilities",
    "confidence",
    "jev_model",
    "asked_at",
    "cost_usd",
)
_KEY = ("match_id", "decided_at", "prompt_version", "question_id", "variant")


@dataclass
class FakeTier2Db(FakeNewsDb):
    predictions: list[tuple[str, str, datetime]] = field(default_factory=list)
    matches: dict[str, tuple[str, str, datetime]] = field(default_factory=dict)
    match_answers: list[dict[str, Any]] = field(default_factory=list)
    read_only: bool = False

    def cursor(self) -> _Tier2Cursor:
        return _Tier2Cursor(self)


class _Tier2Cursor(_Cursor):
    def __init__(self, db: FakeTier2Db) -> None:
        super().__init__(db)
        self._t2 = db

    def execute(self, sql: str, params: Any = None) -> None:
        text = " ".join(sql.split())
        if self._t2.read_only and text.startswith("INSERT"):
            raise AssertionError(f"salt okuma işleminde yazım: {text[:60]}")
        handler = self._handler(text)
        if handler is None:
            super().execute(sql, params)
            return
        self._t2.statements = [*self._t2.statements, text]
        handler(params)

    def _handler(self, text: str) -> Callable[[Any], None] | None:
        handlers: dict[str, Callable[[Any], None]] = {
            "SET TRANSACTION READ ONLY": self._set_read_only,
            "SELECT DISTINCT p.match_id, p.decided_at": self._decisions,
            "SELECT item_id, prompt_version, question_id": self._item_answers,
            "SELECT DISTINCT match_id, decided_at, split_part": self._answered,
            "SELECT a.prompt_version, a.match_id, a.decided_at": self._slice,
            "INSERT INTO jev_match_answers": self._insert,
        }
        return next((h for prefix, h in handlers.items() if text.startswith(prefix)), None)

    def _set_read_only(self, _params: Any) -> None:
        self._t2.read_only = True
        self._result = []

    def _decisions(self, params: Any) -> None:
        since, until, strategies = params
        found = {
            (match, at)
            for match, strategy, at in self._t2.predictions
            if since <= at <= until and strategy in strategies
        }
        ordered = sorted(found, key=lambda pair: (pair[1], pair[0]))
        self._result = [(match, at, *self._t2.matches[match]) for match, at in ordered]

    def _item_answers(self, params: Any) -> None:
        version, item_ids, prefix = params
        rows = sorted(
            (
                r
                for r in self._t2.answers
                if r["prompt_version"] == version
                and r["item_id"] in item_ids
                and not r["question_id"].startswith(prefix)
            ),
            key=lambda r: (r["item_id"], r["question_id"]),
        )
        names = ("item_id", "prompt_version", "question_id", "choice")
        tail = ("confidence", "match_id", "jev_model", "asked_at", "cost_usd")
        self._result = [
            (*(r[n] for n in names), json.loads(r["probabilities"]), *(r[n] for n in tail))
            for r in rows
        ]

    def _answered(self, params: Any) -> None:
        version, variant, match_ids, question_ids = params
        self._result = sorted(
            {
                (r["match_id"], r["decided_at"], r["question_id"].split(":")[1])
                for r in self._t2.match_answers
                if r["prompt_version"] == version
                and r["variant"] == variant
                and r["match_id"] in match_ids
                and r["question_id"] in question_ids
            }
        )

    def _insert(self, params: Any) -> None:
        keys = {tuple(r[k] for k in _KEY) for r in self._t2.match_answers}
        self._result = []
        for index in range(len(params["match_id"])):
            row = {name: params[name][index] for name in MATCH_ANSWER_COLUMNS}
            if row["match_id"] not in self._t2.matches:
                raise AssertionError(f"matches'ta olmayan maç: {row['match_id']}")
            if not isinstance(json.loads(row["probabilities"]), dict):
                raise AssertionError("probabilities bir JSON nesnesi değil")
            key = tuple(row[k] for k in _KEY)
            if key in keys:
                continue
            keys = keys | {key}
            self._t2.match_answers = [*self._t2.match_answers, row]
            self._result.append((row["match_id"],))

    def _slice(self, params: Any) -> None:
        variant, question_ids, strategies = params
        shadow = {(m, d) for m, s, d in self._t2.predictions if s in strategies}
        self._result = sorted(
            {
                (r["prompt_version"], r["match_id"], r["decided_at"])
                for r in self._t2.match_answers
                if r["variant"] == variant
                and r["question_id"] in question_ids
                and (r["match_id"], r["decided_at"]) in shadow
            }
        )
