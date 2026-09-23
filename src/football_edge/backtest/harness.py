"""Olay akışlı yeniden oynatma (tasarım §7.1–7.2, §10).

Strateji yalnız karar anından ÖNCE bilinen sonuçları görür. Bağlam kapanış ve sonuç alanı
taşımaz; kapanış ve sonuç ayrı bir değerlendirme kaydındadır ve bütün tahminler dondurulduktan
SONRA kurulur. Olay sıralaması sızıntıyı zaten önler; `_walk`teki denetim ikinci katmandır.
"""

from __future__ import annotations

import datetime as dt  # `date` bir alan adı: sınıf gövdesinde tip adını gölgelerdi
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from football_edge.backtest.context import check_unique, context_of, record_of, result_of
from football_edge.backtest.events import DECISION, RESULT, Event, build_events
from football_edge.backtest.records import DecisionContext as DecisionContext
from football_edge.backtest.records import MatchKey as MatchKey
from football_edge.backtest.records import ResultRecord as ResultRecord
from football_edge.history.types import CLOSING, HistMatch, OddsKey


class LeakageError(RuntimeError):
    """Bir karar, anı karar anına eşit ya da sonra olan bir sonucu görmüş olurdu."""


@dataclass(frozen=True)
class Outcome:
    match_index: int
    result: str
    home_goals: int
    away_goals: int
    closing: Mapping[OddsKey, float]  # yalnız CLOSING anahtarları


@dataclass(frozen=True)
class Bet:
    outcome: str
    price: float
    book: str


@dataclass(frozen=True)
class Prediction:
    match_index: int
    strategy: str
    probs: tuple[float, float, float]
    bet: Bet | None = None


class Strategy(Protocol):
    @property
    def name(self) -> str: ...

    def observe(self, result: ResultRecord) -> Strategy: ...

    def predict(self, context: DecisionContext) -> Prediction | None: ...


@dataclass(frozen=True)
class ReplayResult:
    strategy: str
    predictions: tuple[Prediction, ...]
    outcomes: Mapping[int, Outcome]  # yalnız tahmin edilen maçlar
    no_decision: int
    no_prediction: int


def _phase_prices(match: HistMatch, phase: str) -> Mapping[OddsKey, float]:
    return MappingProxyType({key: price for key, price in match.odds.items() if key.phase == phase})


def _result_record(match: HistMatch, known_at: dt.datetime) -> ResultRecord:
    return result_of(record_of(match), known_at)


def _context(index: int, match: HistMatch, decided: dt.datetime) -> DecisionContext:
    return context_of(index, record_of(match), decided)


def _outcome(index: int, match: HistMatch) -> Outcome:
    return Outcome(
        match_index=index,
        result=match.result,
        home_goals=match.home_goals,
        away_goals=match.away_goals,
        closing=_phase_prices(match, CLOSING),
    )


def _walk(
    matches: Sequence[HistMatch], events: Sequence[Event], strategy: Strategy
) -> tuple[tuple[Prediction, ...], int]:
    """Olayları verilen sırayla oynatır; (dondurulan tahminler, tahminsiz karar sayısı) döner."""
    current = strategy
    latest: dt.datetime | None = None
    predictions: list[Prediction] = []
    skipped = 0
    for event in events:
        match = matches[event.match_index]
        if event.kind == RESULT:
            current = current.observe(_result_record(match, event.at))
            latest = event.at if latest is None else max(latest, event.at)
            continue
        if latest is not None and event.at <= latest:
            raise LeakageError(
                f"maç {event.match_index}: karar {event.at.isoformat()}, oysa "
                f"{latest.isoformat()} anında bilinen bir sonuç zaten görüldü"
            )
        prediction = current.predict(_context(event.match_index, match, event.at))
        if prediction is None:
            skipped += 1
            continue
        if prediction.match_index != event.match_index:
            raise ValueError(
                f"strateji {prediction.strategy}: maç {event.match_index} kararında başka bir "
                f"maç ({prediction.match_index}) için tahmin döndü"
            )
        predictions.append(prediction)
    return tuple(predictions), skipped


def replay(matches: Sequence[HistMatch], strategy: Strategy) -> ReplayResult:
    """Maçları olay akışıyla oynatır; sonuç kayıtları döngü BİTTİKTEN sonra kurulur.

    Yinelenen `MatchKey` `DuplicateMatch` verir: aynı maçın iki kararı ve çift durum güncellemesi
    sessiz geçmez (Faz 3 tasarımı §7.5).
    """
    check_unique(record_of(match).key for match in matches)
    events = build_events(matches)
    predictions, no_prediction = _walk(matches, events, strategy)
    decisions = sum(1 for event in events if event.kind == DECISION)
    predicted = [prediction.match_index for prediction in predictions]
    outcomes = MappingProxyType({index: _outcome(index, matches[index]) for index in predicted})
    return ReplayResult(
        strategy=strategy.name,
        predictions=predictions,
        outcomes=outcomes,
        no_decision=len(matches) - decisions,
        no_prediction=no_prediction,
    )
