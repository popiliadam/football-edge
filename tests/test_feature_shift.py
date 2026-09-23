"""Logit kaydırma (R168): özelliksiz maçta harman birebir korunur."""

from __future__ import annotations

import math

import pytest

from football_edge.features.shift import shift

P = (0.45, 0.28, 0.27)


def _reference(probs: tuple[float, float, float], s: float) -> tuple[float, float, float]:
    logits = (math.log(probs[0]) + s, math.log(probs[1]), math.log(probs[2]) - s)
    total = sum(math.exp(value) for value in logits)
    home, draw, away = (math.exp(value) / total for value in logits)
    return home, draw, away


@pytest.mark.parametrize(
    ("beta", "f"), [((0.4, -1.2), (0.0, 0.0)), ((0.0, 0.0), (0.7, 0.3)), ((), ())]
)
def test_zero_shift_returns_the_input_object_itself(
    beta: tuple[float, ...], f: tuple[float, ...]
) -> None:
    assert shift(P, beta, f) is P


def test_cancelling_features_are_a_zero_shift() -> None:
    assert shift(P, (1.0, 1.0), (0.25, -0.25)) is P


def test_shift_moves_the_home_logit_up_and_the_away_logit_down() -> None:
    result = shift(P, (0.5, 0.2), (0.4, -0.5))  # β·f = 0.1

    assert result == pytest.approx(_reference(P, 0.1), abs=1e-12)
    assert math.fsum(result) == pytest.approx(1.0, abs=1e-12)
    assert result[0] > P[0] and result[2] < P[2]


def test_a_negative_shift_mirrors_a_positive_one() -> None:
    mirrored = (P[2], P[1], P[0])

    forward = shift(P, (1.0,), (0.3,))
    backward = shift(mirrored, (1.0,), (-0.3,))

    assert forward == pytest.approx((backward[2], backward[1], backward[0]), abs=1e-12)


def test_a_large_shift_stays_finite() -> None:
    result = shift(P, (1.0,), (800.0,))

    assert all(math.isfinite(value) for value in result)
    assert result[0] == pytest.approx(1.0)


def test_mismatched_lengths_are_refused() -> None:
    with pytest.raises(ValueError, match="aynı uzunlukta"):
        shift(P, (1.0, 2.0), (1.0,))


def test_negative_probabilities_are_refused() -> None:
    with pytest.raises(ValueError, match="geçersiz"):
        shift((-0.1, 0.6, 0.5), (1.0,), (0.2,))


# ── Review Focus: sonlu olmayan girdi sessizce NaN olasılık üretmemeli ──────────────────────


@pytest.mark.parametrize(
    ("beta", "f"),
    [
        ((1.0,), (math.nan,)),
        ((math.inf,), (0.1,)),
        ((1e308,), (1e308,)),
        ((1e308, 1e308), (1e308, -1e308)),
    ],
)
def test_non_finite_or_overflowing_inputs_are_refused(
    beta: tuple[float, ...], f: tuple[float, ...]
) -> None:
    with pytest.raises(ValueError):
        shift(P, beta, f)
