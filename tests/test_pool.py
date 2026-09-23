"""Görüş havuzu (Faz 3 tasarımı §6.3): havuzlama kuralı ve ağırlık fiti. Veri SENTETİK."""

from __future__ import annotations

import math

import numpy as np
import pytest

from football_edge.model import pool as pooling
from football_edge.model.pool import (
    MIN_FIT_MATCHES,
    NotConverged,
    TooFewMatches,
    fit_weights,
    pool,
)

MARKET = (0.5, 0.3, 0.2)
MODEL = (0.2, 0.3, 0.5)


def test_weight_one_on_the_first_component_returns_it() -> None:
    assert pool((MARKET, MODEL), (1.0, 0.0)) == pytest.approx(MARKET)


def test_pooling_is_geometric_and_normalised() -> None:
    raw = [math.sqrt(m * o) for m, o in zip(MARKET, MODEL, strict=True)]

    assert pool((MARKET, MODEL), (0.5, 0.5)) == pytest.approx([value / sum(raw) for value in raw])


def test_zero_weights_give_the_uniform_distribution() -> None:
    assert pool((MARKET, MODEL), (0.0, 0.0)) == pytest.approx((1 / 3, 1 / 3, 1 / 3))


def test_a_zero_probability_does_not_break_the_pool() -> None:
    probs = pool(((1.0, 0.0, 0.0), MODEL), (1.0, 1.0))

    assert all(math.isfinite(value) for value in probs)
    assert sum(probs) == pytest.approx(1.0)


def test_negative_or_mismatched_weights_are_refused() -> None:
    with pytest.raises(ValueError, match="negatif"):
        pool((MARKET, MODEL), (1.0, -0.1))
    with pytest.raises(ValueError, match="ağırlık"):
        pool((MARKET, MODEL), (1.0,))


def _sample(
    count: int, truth: int, seed: int = 5
) -> tuple[list[list[tuple[float, ...]]], list[int]]:
    """İki bileşen; sonuçlar `truth` numaralı bileşenden çekilir."""
    rng = np.random.default_rng(seed)
    components: list[list[tuple[float, ...]]] = []
    outcomes: list[int] = []
    for _ in range(count):
        first = tuple(float(v) for v in rng.dirichlet((4.0, 3.0, 3.0)))
        second = tuple(float(v) for v in rng.dirichlet((3.0, 3.0, 4.0)))
        components.append([first, second])
        outcomes.append(int(rng.choice(3, p=(first, second)[truth])))
    return components, outcomes


def test_the_fit_puts_the_weight_on_the_component_that_generated_the_outcomes() -> None:
    components, outcomes = _sample(4000, truth=1)

    first, second = fit_weights(components, outcomes)

    assert second == pytest.approx(1.0, abs=0.15)
    assert first < 0.15


def test_the_fitted_pool_is_never_worse_than_the_first_component_in_sample() -> None:
    """G4/W1'in dayanağı: `(1, 0)` havuzun içinde; fit ondan kötü bir noktada duramaz."""
    components, outcomes = _sample(2000, truth=0, seed=9)
    weights = fit_weights(components, outcomes)

    def loss(ws: tuple[float, ...]) -> float:
        return -float(
            np.mean(
                [
                    math.log(pool(match, ws)[outcome])
                    for match, outcome in zip(components, outcomes, strict=True)
                ]
            )
        )

    assert loss(weights) <= loss((1.0, 0.0)) + 1e-9


def test_the_gradient_matches_finite_differences() -> None:
    from scipy.optimize import check_grad

    components, outcomes = _sample(500, truth=0)
    logs = pooling._logs([list(match) for match in components])
    target = np.asarray(outcomes, dtype=np.int64)

    error = check_grad(
        lambda w: pooling._objective(w, logs, target)[0],
        lambda w: pooling._objective(w, logs, target)[1],
        np.array([0.7, 0.4]),
    )

    assert error < 1e-6


def test_too_few_matches_are_refused() -> None:
    components, outcomes = _sample(MIN_FIT_MATCHES - 1, truth=0)

    with pytest.raises(TooFewMatches):
        fit_weights(components, outcomes)


def test_weights_stay_within_bounds() -> None:
    components, outcomes = _sample(1000, truth=1, seed=3)

    assert all(0.0 <= weight <= pooling.MAX_WEIGHT for weight in fit_weights(components, outcomes))


def test_a_fit_that_does_not_converge_is_named_not_a_bare_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """16a: yakınsamama `NotConverged`dır; uzunluk uyuşmazlığı düz `ValueError` kalır."""
    components, outcomes = _sample(MIN_FIT_MATCHES, truth=0)

    class _Failed:
        success = False
        message = "ABNORMAL_TERMINATION_IN_LNSRCH"
        x = np.array([1.0, 0.0])

    monkeypatch.setattr(pooling, "minimize", lambda *args, **kwargs: _Failed())

    with pytest.raises(NotConverged, match="yakınsamadı"):
        fit_weights(components, outcomes)
    with pytest.raises(ValueError, match="sonuç") as mismatch:
        fit_weights(components, outcomes[:-1])
    assert not isinstance(mismatch.value, NotConverged)


def test_the_weight_bound_binds_when_the_outcomes_want_a_sharper_component() -> None:
    """16l: sonuçlar ikinci bileşenin ~8. kuvvetinden gelir (5/6, 1/12, 1/12 ⇔ (4/3)^w = 10):
    sınırsız fit w ≈ 8,004 bulur; `MAX_WEIGHT` onu 5'te tutar. `bounds=None` mutantı burada
    kırmızıdır (mevcut `test_weights_stay_within_bounds` sınırı hiç zorlamaz)."""
    flat, sharp = (1 / 3, 1 / 3, 1 / 3), (0.4, 0.3, 0.3)
    count = MIN_FIT_MATCHES
    outcomes = [0] * (count * 10 // 12) + [1] * (count // 12) + [2] * (count // 12)

    weights = fit_weights([[flat, sharp]] * len(outcomes), outcomes)

    assert len(outcomes) == count
    assert weights[1] == pytest.approx(pooling.MAX_WEIGHT)
