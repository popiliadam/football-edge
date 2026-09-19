from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
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


def canonical_timestamp(value: str | datetime) -> str:
    """Zaman damgasını hash'lenebilir TEK kanonik metne çevirir.

    Yazma tarafı API'den gelen metni verir, okuma tarafı Postgres'ten gelen
    datetime'ı verir; ikisi de AYNI metni üretmek zorundadır. Aksi hâlde zincir
    kurcalanmamış satırlar için yanlış alarm verir — ki bu, kaçırılan kurcalamadan
    daha zararlıdır, çünkü bir süre sonra alarma kimse bakmaz.
    """
    parsed = (
        datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def row_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical(payload)).encode("utf-8")).hexdigest()


def payload_of(row: dict[str, Any]) -> dict[str, Any]:
    """Satırdan zincir alanlarını (prev_hash/row_hash/id) ayıklar: hash'lenen METİN budur.

    Tek kaynak: hem `verify_chain` hem çıpa kontrolü bu ayıklamayı kullanır. İki yerde
    iki kopya tutulursa biri diğerinden sessizce ayrışır ve kontrol kendi konusunu
    yeniden yazmış olur.
    """
    return {key: value for key, value in row.items() if key not in _CHAIN_KEYS}


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
        payload = payload_of(row)
        if row["prev_hash"] != current:
            return ChainResult(False, index, current, "prev_hash zincire uymuyor", index)
        expected = row_hash(current, payload)
        if row["row_hash"] != expected:
            return ChainResult(False, index, current, "row_hash içerikle uyuşmuyor", index)
        current = row["row_hash"]
    return ChainResult(True, len(rows), current)
