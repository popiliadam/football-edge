"""Faz 2'nin taban stratejileri (tasarım §7.3). Hepsi değişmez: `observe` yeni değer döner.

Vig temizleme ENJEKTE edilir (`Devig`): harness iskeleti vig modülüyle aynı dalgada yazıldı;
gerçek bağlantı bütünleşik harness'ta (`functools.partial(devig, method=...)`) kurulur.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from football_edge.backtest.harness import Bet, DecisionContext, Prediction, ResultRecord
from football_edge.elo import EloConfig, expected_home, updated
from football_edge.history.types import H2H, PRE_CLOSING, RESULTS, OddsKey

Devig = Callable[[Sequence[float]], tuple[float, ...]]

_FLOOR = 0.01
_CEILING = 0.98
# Maç başına tohum: bir maçın seçimi, başka maçların karar alıp almamasından bağımsızdır.
_SEED_STRIDE = 1_000_003


def _h2h_pre(context: DecisionContext, book: str) -> tuple[float, float, float] | None:
    """`book`un kapanış öncesi 1X2 fiyatları (H, D, A); biri eksikse None."""
    keys = [OddsKey(book=book, market=H2H, outcome=name, phase=PRE_CLOSING) for name in RESULTS]
    if not all(key in context.pre_prices for key in keys):
        return None
    home, draw, away = (context.pre_prices[key] for key in keys)
    return home, draw, away


def _fair(devig: Devig, prices: tuple[float, float, float]) -> tuple[float, float, float] | None:
    """Vig'i temizlenmiş olasılık; vig temizleyici fiyatı reddederse None (tahmin yok sayılır)."""
    try:
        probs = devig(prices)
    except ValueError:
        return None
    if len(probs) != len(RESULTS):
        raise ValueError(f"vig temizleyici {len(probs)} olasılık döndü, 1X2 üç ister")
    return probs[0], probs[1], probs[2]


def _clamp(value: float) -> float:
    return min(max(value, _FLOOR), _CEILING)


def _no_groups() -> Mapping[str, str]:
    return MappingProxyType({})


def _no_ratings() -> Mapping[tuple[str, str], float]:
    return MappingProxyType({})


@dataclass(frozen=True)
class MarketPre:
    """Piyasa taban çizgisi: `book`un kapanış öncesi fiyatının vig'i temizlenmiş olasılığı."""

    devig: Devig
    book: str = "Avg"

    @property
    def name(self) -> str:
        return "market_pre"

    def observe(self, result: ResultRecord) -> MarketPre:
        return self

    def predict(self, context: DecisionContext) -> Prediction | None:
        prices = _h2h_pre(context, self.book)
        probs = None if prices is None else _fair(self.devig, prices)
        if probs is None:
            return None
        return Prediction(match_index=context.match_index, strategy=self.name, probs=probs)


@dataclass(frozen=True)
class EloPointInTime:
    """Olay akışının Elo'su, iskele katsayılarla (Faz 3 fit eder).

    Reyting (grup, takım) anahtarlıdır (R94): ham takım adı ülkeler arasında kimlik değildir
    (sessiz birleştirme), lig kodu anahtarı ise terfi eden takımı sıfırlardı. Grup
    `groups.get(lig, lig)` — lig kodu → ülke; eşlenmemiş lig kendi grubudur. Görülmemiş
    (grup, takım) `config.initial`dan başlar.
    """

    config: EloConfig = EloConfig()
    draw_rate: float = 0.26
    groups: Mapping[str, str] = field(default_factory=_no_groups)
    ratings: Mapping[tuple[str, str], float] = field(default_factory=_no_ratings)

    @property
    def name(self) -> str:
        return "elo"

    def _key(self, league: str, team: str) -> tuple[str, str]:
        return self.groups.get(league, league), team

    def _rating(self, key: tuple[str, str]) -> float:
        return self.ratings.get(key, self.config.initial)

    def observe(self, result: ResultRecord) -> EloPointInTime:
        home_key = self._key(result.league, result.home)
        away_key = self._key(result.league, result.away)
        home, away = updated(
            self._rating(home_key),
            self._rating(away_key),
            result.home_goals,
            result.away_goals,
            self.config,
        )
        ratings = MappingProxyType({**self.ratings, home_key: home, away_key: away})
        return replace(self, ratings=ratings)

    def predict(self, context: DecisionContext) -> Prediction:
        expected = expected_home(
            self._rating(self._key(context.league, context.home)),
            self._rating(self._key(context.league, context.away)),
            self.config,
        )
        home = _clamp(expected - self.draw_rate / 2)
        away = _clamp(1.0 - home - self.draw_rate)
        total = home + self.draw_rate + away
        return Prediction(
            match_index=context.match_index,
            strategy=self.name,
            probs=(home / total, self.draw_rate / total, away / total),
        )


@dataclass(frozen=True)
class Placebo:
    """K4 negatif kontrolü: maç başına tohumlu rastgele sonuç, `book`un kapanış öncesi fiyatı."""

    devig: Devig
    seed: int = 20260922
    book: str = "Avg"

    @property
    def name(self) -> str:
        return "placebo"

    def observe(self, result: ResultRecord) -> Placebo:
        return self

    def predict(self, context: DecisionContext) -> Prediction | None:
        prices = _h2h_pre(context, self.book)
        probs = None if prices is None else _fair(self.devig, prices)
        if prices is None or probs is None:
            return None
        pick = random.Random(self.seed * _SEED_STRIDE + context.match_index).choice(RESULTS)
        bet = Bet(outcome=pick, price=prices[RESULTS.index(pick)], book=self.book)
        return Prediction(match_index=context.match_index, strategy=self.name, probs=probs, bet=bet)
