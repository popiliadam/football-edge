"""Fit edilebilir Elo (Faz 3 tasarımı §6.1, R131): iskele `EloPointInTime`ın yerine geçen strateji.

Yenilikler: marj biçimi seçilir (yok / doğrusal / log), sezon arası ortalamaya dönüş, görülmemiş
takımın grup ortalamasının altından başlaması ve beraberliğin reyting farkına bağlanması. Beraberlik
eşlemesinin İKİ biçimi vardır ve biri S'de seçilir (R142): `quadratic` — `P(D) = δ · 4E(1 − E)` —
ve `ordered` — simetrik kesimli sıralı lojit, `η = s · logit(E)`, `P(H) = σ(η − c)`,
`P(A) = σ(−η − c)`. İkisi de reyting yolunu değiştirmez (güncelleme yalnız E'yi kullanır). Reyting
(grup, takım) anahtarlıdır (R94). Değerler iskeledir; seçimi walk-forward'un S bölgesi yapar (R129).
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any

from scipy.optimize import minimize, minimize_scalar

from football_edge.backtest.harness import DecisionContext, Prediction, ResultRecord
from football_edge.elo import EloConfig, expected_home

NO_MARGIN = "none"
LINEAR_MARGIN = "linear"
LOG_MARGIN = "log"
MARGINS = frozenset({NO_MARGIN, LINEAR_MARGIN, LOG_MARGIN})
MAX_DRAW = 0.5
QUADRATIC = "quadratic"
ORDERED = "ordered"
DRAW_FORMS = frozenset({QUADRATIC, ORDERED})
_SCALE_BOUNDS = (0.05, 5.0)
_CUT_BOUNDS = (1e-3, 3.0)
_LOGIT_CLIP = 1e-9
_LOG_FLOOR = 1e-15

Key = tuple[str, str]


@dataclass(frozen=True)
class EloModelConfig:
    k: float = 20.0
    home_advantage: float = 65.0
    margin: str = LINEAR_MARGIN
    regress: float = 0.0  # sezon arasında ortalamaya dönüş payı, [0, 1]
    newcomer_offset: float = 0.0  # görülmemiş takım: grup ortalaması − offset
    draw: float = 0.26  # δ, [0, MAX_DRAW] — yalnız `quadratic`
    draw_form: str = QUADRATIC
    ordered_scale: float = 1.0  # s — yalnız `ordered`
    ordered_cut: float = 0.53  # c; E = 0.5'te P(D) = tanh(c/2) ≈ 0.26
    season_gap_days: int = 60
    initial: float = 1500.0

    def __post_init__(self) -> None:
        if self.margin not in MARGINS:
            raise ValueError(f"bilinmeyen marj biçimi: {self.margin!r}")
        if not 0.0 <= self.draw <= MAX_DRAW:
            raise ValueError(f"beraberlik payı [0, {MAX_DRAW}] dışında: {self.draw}")
        if not 0.0 <= self.regress <= 1.0:
            raise ValueError(f"ortalamaya dönüş payı [0, 1] dışında: {self.regress}")
        if self.draw_form not in DRAW_FORMS:
            raise ValueError(f"bilinmeyen beraberlik biçimi: {self.draw_form!r}")
        if self.ordered_scale <= 0.0 or self.ordered_cut <= 0.0:
            raise ValueError(
                f"sıralı lojit s ve c pozitif olmalı: {self.ordered_scale}, {self.ordered_cut}"
            )


def margin_multiplier(home_goals: int, away_goals: int, form: str) -> float:
    margin = abs(home_goals - away_goals)
    if form == NO_MARGIN or margin <= 1:
        return 1.0
    if form == LINEAR_MARGIN:
        return 1.0 + (margin - 1) * 0.5
    return 1.0 + math.log(margin)


def elo_probs(expected: float, draw: float) -> tuple[float, float, float]:
    """E (ev beklentisi) → (H, D, A); `draw ≤ 0.5` iken üçü de ≥ 0 ve toplam 1."""
    tie = draw * 4.0 * expected * (1.0 - expected)
    return expected - tie / 2.0, tie, 1.0 - expected - tie / 2.0


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def ordered_probs(expected: float, scale: float, cut: float) -> tuple[float, float, float]:
    """Sıralı lojit (R142): η = s · logit(E); P(H) = σ(η − c), P(A) = σ(−η − c), D kalan.

    `c > 0` iken üçü de pozitif ve toplam 1; P(D) = σ(c − η) − σ(−c − η), |η| büyüdükçe azalır.
    """
    clipped = min(max(expected, _LOGIT_CLIP), 1.0 - _LOGIT_CLIP)
    eta = scale * math.log(clipped / (1.0 - clipped))
    home, away = _sigmoid(eta - cut), _sigmoid(-eta - cut)
    return home, 1.0 - home - away, away


def elo_outcome_probs(expected: float, config: EloModelConfig) -> tuple[float, float, float]:
    if config.draw_form == ORDERED:
        return ordered_probs(expected, config.ordered_scale, config.ordered_cut)
    return elo_probs(expected, config.draw)


def expectation(probs: Sequence[float]) -> float:
    """`elo_probs`un (quadratic) tersi: E = H + D/2 (δ'dan bağımsız). Seçim E'yi bununla geri
    okur ve bu yüzden adayları hep `quadratic` biçimle oynatır (reyting yolu biçimden bağımsız)."""
    return probs[0] + probs[1] / 2.0


def fit_draw(expectations: Sequence[float], outcomes: Sequence[int]) -> float:
    """Sabit E dizisi ve sonuçlar (0=H, 1=D, 2=A) → log loss'u en küçük δ."""
    if len(expectations) != len(outcomes) or not outcomes:
        raise ValueError(f"{len(expectations)} beklenti, {len(outcomes)} sonuç")

    def loss(draw: float) -> float:
        return -math.fsum(
            math.log(max(elo_probs(e, draw)[o], _LOG_FLOOR))
            for e, o in zip(expectations, outcomes, strict=True)
        ) / len(outcomes)

    result: Any = minimize_scalar(loss, bounds=(0.0, MAX_DRAW), method="bounded")
    return float(result.x)


def fit_ordered(expectations: Sequence[float], outcomes: Sequence[int]) -> tuple[float, float]:
    """Sabit E dizisi ve sonuçlar → log loss'u en küçük (s, c)."""
    if len(expectations) != len(outcomes) or not outcomes:
        raise ValueError(f"{len(expectations)} beklenti, {len(outcomes)} sonuç")

    def loss(params: Any) -> float:
        scale, cut = float(params[0]), float(params[1])
        return -math.fsum(
            math.log(max(ordered_probs(e, scale, cut)[o], _LOG_FLOOR))
            for e, o in zip(expectations, outcomes, strict=True)
        ) / len(outcomes)

    result: Any = minimize(
        loss, [1.0, 0.53], method="L-BFGS-B", bounds=[_SCALE_BOUNDS, _CUT_BOUNDS]
    )
    return float(result.x[0]), float(result.x[1])


def fit_outcome_params(
    config: EloModelConfig, expectations: Sequence[float], outcomes: Sequence[int]
) -> EloModelConfig:
    """Adayın beraberlik biçiminin parametreleri verilen (S) satırlarda fit edilmiş hâli."""
    if config.draw_form == ORDERED:
        scale, cut = fit_ordered(expectations, outcomes)
        return replace(config, ordered_scale=scale, ordered_cut=cut)
    return replace(config, draw=fit_draw(expectations, outcomes))


def _empty_ratings() -> Mapping[Key, float]:
    return MappingProxyType({})


def _empty_days() -> Mapping[Key, dt.date]:
    return MappingProxyType({})


def _empty_groups() -> Mapping[str, str]:
    return MappingProxyType({})


@dataclass(frozen=True)
class EloModel:
    config: EloModelConfig = EloModelConfig()
    groups: Mapping[str, str] = field(default_factory=_empty_groups)
    ratings: Mapping[Key, float] = field(default_factory=_empty_ratings)
    last_seen: Mapping[Key, dt.date] = field(default_factory=_empty_days)

    @property
    def name(self) -> str:
        return "elo_fit"

    def _key(self, league: str, team: str) -> Key:
        return self.groups.get(league, league), team

    def _group_mean(self, group: str) -> float:
        values = [rating for (owner, _), rating in self.ratings.items() if owner == group]
        return math.fsum(values) / len(values) if values else self.config.initial

    def _current(self, key: Key, day: dt.date) -> float:
        """`day`deki reyting: görülmemişse grup ortalaması − offset; uzun aradan sonra dönüş."""
        rating = self.ratings.get(key)
        if rating is None:
            return self._group_mean(key[0]) - self.config.newcomer_offset
        seen = self.last_seen.get(key)
        if seen is not None and (day - seen).days > self.config.season_gap_days:
            mean = self._group_mean(key[0])
            return mean + (1.0 - self.config.regress) * (rating - mean)
        return rating

    def _expected(self, home: float, away: float) -> float:
        return expected_home(
            home, away, EloConfig(k=self.config.k, home_advantage=self.config.home_advantage)
        )

    def observe(self, result: ResultRecord) -> EloModel:
        home_key = self._key(result.league, result.home)
        away_key = self._key(result.league, result.away)
        home = self._current(home_key, result.date)
        away = self._current(away_key, result.date)
        actual = (
            1.0
            if result.home_goals > result.away_goals
            else 0.0
            if result.home_goals < result.away_goals
            else 0.5
        )
        multiplier = margin_multiplier(result.home_goals, result.away_goals, self.config.margin)
        change = self.config.k * multiplier * (actual - self._expected(home, away))
        return replace(
            self,
            ratings=MappingProxyType(
                {**self.ratings, home_key: home + change, away_key: away - change}
            ),
            last_seen=MappingProxyType(
                {**self.last_seen, home_key: result.date, away_key: result.date}
            ),
        )

    def predict(self, context: DecisionContext) -> Prediction:
        home = self._current(self._key(context.league, context.home), context.date)
        away = self._current(self._key(context.league, context.away), context.date)
        probs = elo_outcome_probs(self._expected(home, away), self.config)
        return Prediction(context.match_index, self.name, probs)
