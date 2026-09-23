"""Karar anı filtresi ve özellik vektörü (spec §5/1, §6; R166).

Kademe 2'nin haber kümesi YALNIZ burada seçilir. Koşul katıdır: `available_at < decided_at` ve
canlıda kademe 1 cevabı için `asked_at < decided_at`. Tam eşit an DIŞARIDADIR — karar anında
"kullanılabilir" olan haber o karara yetişmiş sayılamaz. Arşivde kademe 1 sonradan (geri doldurma)
sorulur; orada koruma `available_at`in güvenlik payıdır (`news.archive_available_at`).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from football_edge.features.types import ItemGate, StoredNews


def _usable(
    item: StoredNews,
    gate: ItemGate,
    *,
    match_id: str,
    decided_at: datetime,
    live: bool,
    min_belongs: float,
    min_reliability: float,
) -> bool:
    if gate.match_id != match_id:
        return False
    if not item.available_at < decided_at:
        return False
    if live and not gate.asked_at < decided_at:
        return False
    return gate.belongs >= min_belongs and gate.reliability >= min_reliability


def select_items(
    items: Sequence[StoredNews],
    gates: Mapping[int, ItemGate],
    *,
    match_id: str,
    decided_at: datetime,
    live: bool,
    min_belongs: float,
    min_reliability: float,
) -> tuple[StoredNews, ...]:
    """Maçın karar anında kullanılabilir haberleri; küme başına en erken tek haber.

    Kümenin temsilcisi SÜZGEÇTEN SONRA seçilir: kararla aynı anda ya da sonra gelen bir tekrar,
    daha önce gelmiş haberin yerini alamaz.
    """
    if decided_at.tzinfo is None:
        raise ValueError("decided_at saat dilimsiz")
    earliest: dict[str, StoredNews] = {}
    for item in sorted(items, key=_order):
        if item.item_id is None:
            continue
        gate = gates.get(item.item_id)
        if gate is not None and _usable(
            item,
            gate,
            match_id=match_id,
            decided_at=decided_at,
            live=live,
            min_belongs=min_belongs,
            min_reliability=min_reliability,
        ):
            earliest.setdefault(gate.cluster_id, item)
    return tuple(sorted(earliest.values(), key=_order))


def _order(item: StoredNews) -> tuple[datetime, int]:
    return item.available_at, -1 if item.item_id is None else item.item_id


def item_set_hash(items: Sequence[StoredNews]) -> str:
    """Haber kümesinin sıradan bağımsız özeti; kademe 2 satırı hangi kümeyle sorulduğunu taşır."""
    keys = sorted({(item.source_id, item.content_hash) for item in items})
    return hashlib.sha256(json.dumps(keys, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class SideAnswer:
    home: float | None
    away: float | None
    confidence: float


@dataclass(frozen=True)
class FeatureVector:
    names: tuple[str, ...]
    values: tuple[float, ...]
    missing: int


def _feature(answer: SideAnswer | None, c_min: float) -> float | None:
    if answer is None or answer.home is None or answer.away is None:
        return None
    # NaN her karşılaştırmada False döner; süzülmezse `confidence < c_min` onu içeri alırdı.
    if not all(math.isfinite(v) for v in (answer.home, answer.away, answer.confidence)):
        return None
    if answer.confidence < c_min:
        return None
    return answer.home - answer.away


def features_of(
    answers: Mapping[str, SideAnswer], names: Sequence[str], *, c_min: float
) -> FeatureVector:
    """`f = ev − deplasman`; eksik, sonlu olmayan ya da `confidence < c_min` cevap → 0 ve eksik."""
    if len(set(names)) != len(names):
        raise ValueError(f"özellik adları tekil olmalı: {list(names)}")
    raw = tuple(_feature(answers.get(name), c_min) for name in names)
    return FeatureVector(
        names=tuple(names),
        values=tuple(0.0 if value is None else value for value in raw),
        missing=sum(1 for value in raw if value is None),
    )
