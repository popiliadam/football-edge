"""Dixon-Coles (Faz 3 tasarımı §6.2): gradyan, geri kazanım, zaman sınırı, skor matrisi.

Veri SENTETİK: bilinen güçlerle numpy'nin tohumlu üreteciyle çekilmiş goller.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pytest
from scipy.optimize import check_grad

from football_edge.model import dixon_coles as dc
from football_edge.model.dixon_coles import DCConfig, DCParams, GoalRecord

TEAMS = ("Alfa", "Beta", "Gama", "Delta", "Epsilon", "Zeta")
ATTACK = (0.45, 0.25, 0.05, -0.05, -0.25, -0.45)
DEFENCE = (-0.35, -0.2, 0.0, 0.05, 0.2, 0.3)
HOME = 0.3
FIRST = date(2020, 8, 1)
AT = date(2023, 7, 1)
FAST = DCConfig(xi=0.0, ridge=0.001, window_days=5000, min_matches=30)


def _season_records(rng: np.random.Generator, seasons: int = 6) -> tuple[GoalRecord, ...]:
    """Her sezon çift devreli lig; gün, sezonun ilk gününden maç sırasıyla artar."""
    found: list[GoalRecord] = []
    for season in range(seasons):
        day = FIRST + timedelta(days=season * 120)
        for h, home in enumerate(TEAMS):
            for a, away in enumerate(TEAMS):
                if h == a:
                    continue
                lam = math.exp(ATTACK[h] + DEFENCE[a] + HOME)
                mu = math.exp(ATTACK[a] + DEFENCE[h])
                found.append(
                    GoalRecord(home, away, int(rng.poisson(lam)), int(rng.poisson(mu)), day)
                )
                day += timedelta(days=1)
    return tuple(found)


RECORDS = _season_records(np.random.default_rng(20260923))


def _params(rho: float = 0.0, home: float = HOME) -> DCParams:
    order = sorted(range(len(TEAMS)), key=lambda index: TEAMS[index])
    return DCParams(
        teams=tuple(TEAMS[index] for index in order),
        attack=tuple(ATTACK[index] for index in order),
        defence=tuple(DEFENCE[index] for index in order),
        home=home,
        rho=rho,
        fitted_on=AT,
    )


def test_the_gradient_matches_finite_differences() -> None:
    used = dc._used(RECORDS, AT, 5000)
    teams = tuple(sorted(TEAMS))
    data = dc._data(used, teams, AT, 0.002)
    theta = np.random.default_rng(1).normal(0.0, 0.2, 2 * len(teams) + 2)
    theta[-1] = 0.05

    error = check_grad(
        lambda t: dc._objective(t, data, 0.01)[0],
        lambda t: dc._objective(t, data, 0.01)[1],
        theta,
    )

    assert error < 1e-5


def test_the_fit_recovers_known_strength_order_and_home_advantage() -> None:
    params = dc.fit(RECORDS, at=AT, config=FAST)

    assert params is not None
    strengths = dc.strengths(params)
    net = {team: attack - defence for team, (attack, defence) in strengths.items()}
    assert sorted(net, key=net.__getitem__, reverse=True)[:2] == ["Alfa", "Beta"]
    assert sorted(net, key=net.__getitem__)[:2] == ["Zeta", "Epsilon"]
    assert params.home == pytest.approx(HOME, abs=0.12)
    assert abs(params.rho) <= FAST.rho_bound


@pytest.mark.leakage
def test_the_fit_ignores_matches_on_or_after_the_fit_day() -> None:
    """Gelecek-fit savunması: `at` günü ve sonrası hiçbir maç parametreyi değiştirmez."""
    future = (
        GoalRecord("Zeta", "Alfa", 9, 0, AT),
        GoalRecord("Zeta", "Beta", 8, 0, AT + timedelta(days=3)),
    )

    assert dc.fit((*RECORDS, *future), at=AT, config=FAST) == dc.fit(RECORDS, at=AT, config=FAST)


def test_the_fit_ignores_matches_older_than_the_window() -> None:
    windowed = DCConfig(xi=0.0, ridge=0.001, window_days=400, min_matches=30)
    old = GoalRecord("Zeta", "Alfa", 9, 0, AT - timedelta(days=401))

    assert dc.fit((*RECORDS, old), at=AT, config=windowed) == dc.fit(
        RECORDS, at=AT, config=windowed
    )


def test_time_decay_weights_recent_matches_more() -> None:
    """Son sezonda Zeta'yı güçlü yapan maçlar sönümle daha çok, sönümsüz daha az etki eder."""
    late = tuple(
        GoalRecord("Zeta", other, 3, 0, AT - timedelta(days=5 + index))
        for index, other in enumerate(TEAMS[:5] * 2)
    )
    decayed = dc.fit((*RECORDS, *late), at=AT, config=DCConfig(xi=0.01, ridge=0.001))
    flat = dc.fit((*RECORDS, *late), at=AT, config=DCConfig(xi=0.0, ridge=0.001, window_days=5000))

    assert decayed is not None and flat is not None
    assert dc.strengths(decayed)["Zeta"][0] > dc.strengths(flat)["Zeta"][0]


def test_too_few_matches_give_no_fit() -> None:
    assert dc.fit(RECORDS[:29], at=AT, config=FAST) is None


def test_warm_start_reaches_the_same_optimum() -> None:
    cold = dc.fit(RECORDS, at=AT, config=FAST)
    assert cold is not None

    warm = dc.fit(RECORDS, at=AT, config=FAST, start=cold)

    assert warm is not None
    assert warm.attack == pytest.approx(cold.attack, abs=1e-4)
    assert warm.home == pytest.approx(cold.home, abs=1e-4)


def test_the_fit_is_deterministic() -> None:
    assert dc.fit(RECORDS, at=AT, config=FAST) == dc.fit(RECORDS, at=AT, config=FAST)


def test_an_unknown_team_has_no_score_matrix() -> None:
    assert dc.score_matrix(_params(), "Alfa", "Yabancı", 10) is None


def test_without_rho_the_matrix_is_the_normalised_product_of_two_poissons() -> None:
    matrix = dc.score_matrix(_params(rho=0.0), "Alfa", "Zeta", 10)

    assert matrix is not None
    lam = math.exp(ATTACK[0] + DEFENCE[5] + HOME)
    mu = math.exp(ATTACK[5] + DEFENCE[0])
    raw = np.outer(
        [math.exp(-lam) * lam**k / math.factorial(k) for k in range(11)],
        [math.exp(-mu) * mu**k / math.factorial(k) for k in range(11)],
    )
    assert matrix == pytest.approx(raw / raw.sum())
    assert float(matrix.sum()) == pytest.approx(1.0)


def test_rho_moves_mass_between_the_four_low_scores() -> None:
    plain = dc.score_matrix(_params(rho=0.0), "Gama", "Delta", 10)
    adjusted = dc.score_matrix(_params(rho=-0.1), "Gama", "Delta", 10)

    assert plain is not None and adjusted is not None
    # ρ < 0: 0-0 ve 1-1 artar, 1-0 ve 0-1 azalır (normalize öncesi çarpanların yönü).
    assert adjusted[0, 0] > plain[0, 0] and adjusted[1, 1] > plain[1, 1]
    assert adjusted[1, 0] < plain[1, 0] and adjusted[0, 1] < plain[0, 1]


def test_outcome_probabilities_read_rows_as_home_goals() -> None:
    matrix = np.zeros((3, 3))
    matrix[2, 0], matrix[1, 1], matrix[0, 1] = 0.5, 0.3, 0.2

    assert dc.outcome_probs(matrix) == pytest.approx((0.5, 0.3, 0.2))


def test_totals_count_three_or_more_goals_as_over() -> None:
    matrix = np.zeros((4, 4))
    matrix[1, 1], matrix[2, 1], matrix[0, 3] = 0.6, 0.3, 0.1

    assert dc.totals_probs(matrix) == pytest.approx((0.4, 0.6))


def test_a_stronger_home_side_is_favoured() -> None:
    matrix = dc.score_matrix(_params(), "Alfa", "Zeta", 10)

    assert matrix is not None
    home, draw, away = dc.outcome_probs(matrix)
    assert home > draw and home > away
    assert home + draw + away == pytest.approx(1.0)


def test_a_fit_that_does_not_converge_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bayat parametreyle tahmin hatayı gizlerdi: yakınsamayan fit None, strateji tahmin vermez."""

    @dataclass(frozen=True)
    class Failed:
        x: np.ndarray
        success: bool = False
        message: str = "ABNORMAL_TERMINATION_IN_LNSRCH"

    monkeypatch.setattr(dc, "minimize", lambda fun, x0, **kwargs: Failed(x0))

    assert dc.fit(RECORDS, at=AT, config=FAST) is None
