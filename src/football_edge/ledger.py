from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

GENESIS = "0" * 64
_CHAIN_KEYS = frozenset({"prev_hash", "row_hash", "id"})


@dataclass(frozen=True)
class ChainResult:
    ok: bool
    checked: int
    head: str
    error: str | None = None
    failed_index: int | None = None


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def row_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical(payload)).encode("utf-8")).hexdigest()


def chain(
    payloads: tuple[dict[str, Any], ...], prev_hash: str = GENESIS
) -> tuple[dict[str, Any], ...]:
    rows: tuple[dict[str, Any], ...] = ()
    current = prev_hash
    for payload in payloads:
        digest = row_hash(current, payload)
        rows = (*rows, {**payload, "prev_hash": current, "row_hash": digest})
        current = digest
    return rows


def verify_chain(rows: tuple[dict[str, Any], ...], start_hash: str = GENESIS) -> ChainResult:
    current = start_hash
    for index, row in enumerate(rows):
        payload = {key: value for key, value in row.items() if key not in _CHAIN_KEYS}
        if row["prev_hash"] != current:
            return ChainResult(False, index, current, "prev_hash zincire uymuyor", index)
        expected = row_hash(current, payload)
        if row["row_hash"] != expected:
            return ChainResult(False, index, current, "row_hash içerikle uyuşmuyor", index)
        current = row["row_hash"]
    return ChainResult(True, len(rows), current)
