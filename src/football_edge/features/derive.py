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
from types import MappingProxyType

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


# ── Taraf cevapları ve "yok" ataması (Plan 2 I-1) ───────────────────────────────────────────

NONE_LEVEL = "none"
# Dört düzeyli ortak ölçeğin (`questions.LEVEL_CRITERIA`) sayısal karşılığı: eşit aralıklı [0, 1].
LEVEL_SCORES: Mapping[str, float] = MappingProxyType(
    {"none": 0.0, "low": 1 / 3, "medium": 2 / 3, "high": 1.0}
)


@dataclass(frozen=True)
class LevelAnswer:
    value: float
    confidence: float


# Haberi olmadığı için SORULMAYAN taraf: "yok" düzeyi, tam güven (eksik değil, atanmış — `imputed`).
IMPUTED = LevelAnswer(LEVEL_SCORES[NONE_LEVEL], 1.0)


def level_answer(probabilities: Mapping[str, float], confidence: float) -> LevelAnswer | None:
    """Olasılık ağırlıklı ölçek değeri ∈ [0, 1]; ölçek dışı, sonlu olmayan ya da boş → None."""
    if not probabilities or not set(probabilities) <= set(LEVEL_SCORES):
        return None
    if not all(math.isfinite(v) and v >= 0 for v in (*probabilities.values(), confidence)):
        return None
    total = math.fsum(probabilities.values())
    if total <= 0:
        return None
    weighted = math.fsum(LEVEL_SCORES[key] * p for key, p in probabilities.items())
    return LevelAnswer(weighted / total, confidence)


@dataclass(frozen=True)
class MatchAnswers:
    answers: Mapping[str, SideAnswer]
    imputed: int  # "yok" atanan (sorulmayan) taraf sayısı


def _pick(side: Mapping[str, LevelAnswer] | None, name: str) -> LevelAnswer | None:
    return IMPUTED if side is None else side.get(name)


def side_answers(
    names: Sequence[str],
    *,
    home: Mapping[str, LevelAnswer] | None,
    away: Mapping[str, LevelAnswer] | None,
) -> MatchAnswers:
    """`None` taraf = haberi olmadığı için SORULMADI: her soruda "yok" (I-1), `imputed` sayılır.
    Sorulmuş ama cevabı gelmemiş soru eksik kalır (`features_of` → 0 ve `missing`)."""
    answers: dict[str, SideAnswer] = {}
    for name in names:
        home_answer, away_answer = _pick(home, name), _pick(away, name)
        given = [a.confidence for a in (home_answer, away_answer) if a is not None]
        answers[name] = SideAnswer(
            home=None if home_answer is None else home_answer.value,
            away=None if away_answer is None else away_answer.value,
            confidence=min(given, default=0.0),
        )
    return MatchAnswers(MappingProxyType(answers), imputed=(home is None) + (away is None))
