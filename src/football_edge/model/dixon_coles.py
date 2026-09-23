"""Zaman sönümlü Dixon-Coles (Faz 3 tasarımı §6.2, R131): saf fit ve skor matrisi.

Gol süreci: ev golü `Poisson(exp(a_ev + d_dep + h))`, deplasman golü `Poisson(exp(a_dep + d_ev))`;
düşük skorlarda `τ(ρ)` düzeltmesi. Maç ağırlığı `exp(−ξ · gün)`; güçlere sırt (L2) cezası hem
az maçlı takımı hem kimlik kısıtını karşılar. Fit YALNIZ `at`ten önceki maçları görür — çağıran
ne verirse versin (sızıntı savunması burada da bir katman). Yakınsamayan fit `None` döner:
bayat parametreyle tahmin etmek hatayı gizlerdi.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.optimize import minimize

Floats = npt.NDArray[np.float64]
Ints = npt.NDArray[np.int64]

_TAU_FLOOR = 1e-10
_START_HOME = 0.25
_MAX_ITERATIONS = 500


@dataclass(frozen=True)
class GoalRecord:
    home: str
    away: str
    home_goals: int
    away_goals: int
    day: date


@dataclass(frozen=True)
class DCConfig:
    xi: float = 0.0019  # gün başına sönüm; yarı ömür ~1 yıl (S'de seçilir)
    ridge: float = 0.01
    window_days: int = 1095
    max_goals: int = 10
    rho_bound: float = 0.2
    min_matches: int = 30


@dataclass(frozen=True)
class DCParams:
    teams: tuple[str, ...]  # sıralı
    attack: tuple[float, ...]  # log ölçek
    defence: tuple[float, ...]  # log ölçek; büyük = kötü savunma
    home: float
    rho: float
    fitted_on: date

    def index(self, team: str) -> int | None:
        position = bisect.bisect_left(self.teams, team)
        if position < len(self.teams) and self.teams[position] == team:
            return position
        return None


@dataclass(frozen=True)
class _Data:
    home: Ints
    away: Ints
    x: Floats
    y: Floats
    w: Floats
    size: int


def _used(records: Sequence[GoalRecord], at: date, window_days: int) -> list[GoalRecord]:
    return [
        record for record in records if record.day < at and (at - record.day).days <= window_days
    ]


def _data(used: Sequence[GoalRecord], teams: tuple[str, ...], at: date, xi: float) -> _Data:
    position = {team: index for index, team in enumerate(teams)}
    ages = np.array([(at - record.day).days for record in used], dtype=np.float64)
    return _Data(
        home=np.array([position[record.home] for record in used], dtype=np.int64),
        away=np.array([position[record.away] for record in used], dtype=np.int64),
        x=np.array([record.home_goals for record in used], dtype=np.float64),
        y=np.array([record.away_goals for record in used], dtype=np.float64),
        w=np.exp(-xi * ages),
        size=len(teams),
    )


def _tau_terms(
    data: _Data, lam: Floats, mu: Floats, rho: float
) -> tuple[Floats, Floats, Floats, Floats]:
    """(τ, ∂logτ/∂η_ev, ∂logτ/∂η_dep, ∂logτ/∂ρ) maç başına."""
    zero_zero = (data.x == 0) & (data.y == 0)
    zero_one = (data.x == 0) & (data.y == 1)
    one_zero = (data.x == 1) & (data.y == 0)
    one_one = (data.x == 1) & (data.y == 1)
    tau = np.ones_like(lam)
    tau = np.where(zero_zero, 1.0 - lam * mu * rho, tau)
    tau = np.where(zero_one, 1.0 + lam * rho, tau)
    tau = np.where(one_zero, 1.0 + mu * rho, tau)
    tau = np.where(one_one, 1.0 - rho, tau)
    tau = np.maximum(tau, _TAU_FLOOR)
    d_home = np.where(zero_zero, -lam * mu * rho / tau, 0.0)
    d_home = np.where(zero_one, lam * rho / tau, d_home)
    d_away = np.where(zero_zero, -lam * mu * rho / tau, 0.0)
    d_away = np.where(one_zero, mu * rho / tau, d_away)
    d_rho = np.where(zero_zero, -lam * mu / tau, 0.0)
    d_rho = np.where(zero_one, lam / tau, d_rho)
    d_rho = np.where(one_zero, mu / tau, d_rho)
    d_rho = np.where(one_one, -1.0 / tau, d_rho)
    return tau, d_home, d_away, d_rho


def _objective(theta: Floats, data: _Data, ridge: float) -> tuple[float, Floats]:
    """Ağırlıklı ortalama negatif log olabilirlik + sırt cezası ve gradyanı."""
    n = data.size
    attack, defence = theta[:n], theta[n : 2 * n]
    home, rho = float(theta[2 * n]), float(theta[2 * n + 1])
    eta_home = attack[data.home] + defence[data.away] + home
    eta_away = attack[data.away] + defence[data.home]
    lam, mu = np.exp(eta_home), np.exp(eta_away)
    tau, d_home, d_away, d_rho = _tau_terms(data, lam, mu, rho)
    total = float(np.sum(data.w))
    ll = data.w * (np.log(tau) + data.x * eta_home - lam + data.y * eta_away - mu)
    g_home = data.w * (data.x - lam + d_home)
    g_away = data.w * (data.y - mu + d_away)
    grad_attack = np.bincount(data.home, g_home, n) + np.bincount(data.away, g_away, n)
    grad_defence = np.bincount(data.away, g_home, n) + np.bincount(data.home, g_away, n)
    penalty = ridge * float(attack @ attack + defence @ defence)
    value = -float(np.sum(ll)) / total + penalty
    gradient = np.concatenate(
        [
            -grad_attack / total + 2.0 * ridge * attack,
            -grad_defence / total + 2.0 * ridge * defence,
            np.array([-float(np.sum(g_home)) / total, -float(np.sum(data.w * d_rho)) / total]),
        ]
    )
    return value, gradient


def _start(teams: tuple[str, ...], start: DCParams | None) -> Floats:
    n = len(teams)
    theta = np.zeros(2 * n + 2)
    theta[2 * n] = _START_HOME
    if start is None:
        return theta
    for index, team in enumerate(teams):
        previous = start.index(team)
        if previous is not None:
            theta[index] = start.attack[previous]
            theta[n + index] = start.defence[previous]
    theta[2 * n] = start.home
    theta[2 * n + 1] = start.rho
    return theta


def fit(
    records: Sequence[GoalRecord],
    *,
    at: date,
    config: DCConfig,
    start: DCParams | None = None,
) -> DCParams | None:
    """`at`ten ÖNCEKİ ve pencere içindeki maçlarla fit; az maçta ya da yakınsamazsa None."""
    used = _used(records, at, config.window_days)
    if len(used) < config.min_matches:
        return None
    teams = tuple(sorted({record.home for record in used} | {record.away for record in used}))
    data = _data(used, teams, at, config.xi)
    n = len(teams)
    bounds = [(None, None)] * (2 * n + 1) + [(-config.rho_bound, config.rho_bound)]
    result: Any = minimize(
        _objective,
        _start(teams, start),
        args=(data, config.ridge),
        jac=True,
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": _MAX_ITERATIONS},
    )
    theta = np.asarray(result.x, dtype=np.float64)
    if not bool(result.success) or not bool(np.all(np.isfinite(theta))):
        return None
    return DCParams(
        teams=teams,
        attack=tuple(float(value) for value in theta[:n]),
        defence=tuple(float(value) for value in theta[n : 2 * n]),
        home=float(theta[2 * n]),
        rho=float(theta[2 * n + 1]),
        fitted_on=at,
    )


def _poisson(rate: float, max_goals: int) -> Floats:
    return np.array(
        [math.exp(k * math.log(rate) - rate - math.lgamma(k + 1)) for k in range(max_goals + 1)]
    )


def score_matrix(params: DCParams, home: str, away: str, max_goals: int) -> Floats | None:
    """P(ev = i, deplasman = j), i, j ≤ `max_goals`, toplamı 1'e normalize; takım yoksa None."""
    h, a = params.index(home), params.index(away)
    if h is None or a is None:
        return None
    lam = math.exp(params.attack[h] + params.defence[a] + params.home)
    mu = math.exp(params.attack[a] + params.defence[h])
    matrix = np.outer(_poisson(lam, max_goals), _poisson(mu, max_goals))
    matrix[0, 0] *= max(1.0 - lam * mu * params.rho, _TAU_FLOOR)
    matrix[0, 1] *= max(1.0 + lam * params.rho, _TAU_FLOOR)
    matrix[1, 0] *= max(1.0 + mu * params.rho, _TAU_FLOOR)
    matrix[1, 1] *= max(1.0 - params.rho, _TAU_FLOOR)
    return np.asarray(matrix / matrix.sum(), dtype=np.float64)


def outcome_probs(matrix: Floats) -> tuple[float, float, float]:
    """(ev, beraberlik, deplasman) — satır ev golü, sütun deplasman golü."""
    home = float(np.tril(matrix, -1).sum())
    draw = float(np.trace(matrix))
    away = float(np.triu(matrix, 1).sum())
    return home, draw, away


def totals_probs(matrix: Floats, line: float = 2.5) -> tuple[float, float]:
    """(üst, alt) — `MARKET_OUTCOMES[TOTALS_25]` sırası."""
    goals = np.add.outer(np.arange(matrix.shape[0]), np.arange(matrix.shape[1]))
    over = float(matrix[goals > line].sum())
    return over, 1.0 - over


def strengths(params: DCParams) -> Mapping[str, tuple[float, float]]:
    """Takım → (atak, savunma); rapor ve test için."""
    return MappingProxyType(
        {
            team: (params.attack[index], params.defence[index])
            for index, team in enumerate(params.teams)
        }
    )
