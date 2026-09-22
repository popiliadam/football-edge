"""Ölçütler: elle hesaplanan değerler ve kalibrasyon/bootstrap özellikleri (tasarım §7.5)."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest

from football_edge.history.types import H2H, TOTALS_25
from football_edge.market.metrics import (
    LOG_FLOOR,
    Interval,
    bootstrap_mean,
    brier,
    calibration,
    clv,
    log_loss,
    outcome_index,
    per_match_log_loss,
    rps,
)
from tests.market_factory import hist_match

# İki satırlık elle hesaplanan örnek (1X2; sonuçlar H ve D):
#   satır 1: p = (0.5, 0.3, 0.2), y = (1, 0, 0)
#     LL = −ln 0.5 = 0.693147 · Brier = 0.25 + 0.09 + 0.04 = 0.38
#     RPS = ((0.5 − 1)² + (0.8 − 1)²) / 2 = (0.25 + 0.04) / 2 = 0.145
#   satır 2: p = (0.2, 0.3, 0.5), y = (0, 1, 0)
#     LL = −ln 0.3 = 1.203973 · Brier = 0.04 + 0.49 + 0.25 = 0.78
#     RPS = ((0.2 − 0)² + (0.5 − 1)²) / 2 = (0.04 + 0.25) / 2 = 0.145
#   ortalama: LL = 0.948560 · Brier = 0.58 · RPS = 0.145
TWO_ROWS = ((0.5, 0.3, 0.2), (0.2, 0.3, 0.5))
TWO_OUTCOMES = (0, 1)
Metric = Callable[..., object]
Sample = tuple[tuple[tuple[float, ...], ...], tuple[int, ...]]


def test_two_row_example_by_hand() -> None:
    assert per_match_log_loss(TWO_ROWS, TWO_OUTCOMES) == pytest.approx(
        (-math.log(0.5), -math.log(0.3))
    )
    assert log_loss(TWO_ROWS, TWO_OUTCOMES) == pytest.approx(0.948560, abs=1e-6)
    assert brier(TWO_ROWS, TWO_OUTCOMES) == pytest.approx(0.58)
    assert rps(TWO_ROWS, TWO_OUTCOMES) == pytest.approx(0.145)


def test_perfect_forecast_scores_zero() -> None:
    probs = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    outcomes = (0, 2)
    assert log_loss(probs, outcomes) == 0.0
    assert brier(probs, outcomes) == 0.0
    assert rps(probs, outcomes) == 0.0


def test_uniform_forecast_by_hand() -> None:
    uniform = (1 / 3, 1 / 3, 1 / 3)
    # LL = ln 3 · Brier = (2/3)² + 2·(1/3)² = 2/3
    # RPS: H → ((1/3 − 1)² + (2/3 − 1)²)/2 = 5/18 · D → ((1/3)² + (2/3 − 1)²)/2 = 1/9
    #      A → ((1/3)² + (2/3)²)/2 = 5/18
    assert log_loss((uniform,), (1,)) == pytest.approx(math.log(3))
    assert brier((uniform,), (0,)) == pytest.approx(2 / 3)
    assert rps((uniform,), (0,)) == pytest.approx(5 / 18)
    assert rps((uniform,), (1,)) == pytest.approx(1 / 9)
    assert rps((uniform,) * 3, (0, 1, 2)) == pytest.approx((5 / 18 + 1 / 9 + 5 / 18) / 3)


def test_rps_penalises_mass_on_distant_outcomes_where_brier_does_not() -> None:
    near = ((0.4, 0.6, 0.0),)  # sonuç H; kaçan kütle komşu D'de
    far = ((0.4, 0.0, 0.6),)  # kaçan kütle uzak A'da
    assert brier(near, (0,)) == pytest.approx(0.72)
    assert brier(far, (0,)) == pytest.approx(0.72)
    assert rps(near, (0,)) == pytest.approx(0.18)  # (0.36 + 0) / 2
    assert rps(far, (0,)) == pytest.approx(0.36)  # (0.36 + 0.36) / 2


def test_a_certain_miss_is_floored_not_infinite() -> None:
    assert LOG_FLOOR == 1e-15
    assert per_match_log_loss(((1.0, 0.0, 0.0),), (1,)) == (-math.log(1e-15),)


@pytest.mark.parametrize("metric", (per_match_log_loss, log_loss, brier, rps, calibration))
@pytest.mark.parametrize(
    ("probs", "outcomes"),
    (
        ((), ()),
        (((0.5, 0.5),), (0, 1)),
        (((0.5, 0.5), (0.2, 0.3, 0.5)), (0, 0)),
        (((1.0,),), (0,)),
        (((0.5, 0.5),), (2,)),
        (((0.5, 0.5),), (-1,)),
        (((1.5, -0.5),), (0,)),
        (((math.nan, 0.5),), (0,)),
    ),
    ids=("bos", "uzunluk", "genislik", "tek-sonuc", "sira-ust", "sira-negatif", "aralik", "nan"),
)
def test_malformed_input_is_rejected(
    metric: Metric, probs: tuple[tuple[float, ...], ...], outcomes: tuple[int, ...]
) -> None:
    with pytest.raises(ValueError):
        metric(probs, outcomes)


def test_frequencies_that_match_the_forecasts_give_slope_one_and_no_ece() -> None:
    # (0.75, 0.25) dört maçta, üçünde ilk sonuç: p = 0.75 çiftlerinde ȳ = 3/4, p = 0.25'te 1/4.
    # İki ayrık logit değeri, iki parametre: doygun fit tam olarak a = 0, b = 1 verir.
    result = calibration(((0.75, 0.25),) * 4, (0, 0, 0, 1))
    assert result.slope == pytest.approx(1.0, abs=1e-9)
    assert result.intercept == pytest.approx(0.0, abs=1e-9)
    assert result.ece == pytest.approx(0.0, abs=1e-12)
    assert result.n == 8


def test_forecasts_that_carry_no_information_give_slope_zero() -> None:
    # Aynı tahmin, sonuçlar yarı yarıya: y p'den bağımsız → b = 0, a = 0.
    # ECE = ½·|0.5 − 0.75| + ½·|0.5 − 0.25| = 0.25
    result = calibration(((0.75, 0.25),) * 4, (0, 0, 1, 1))
    assert result.slope == pytest.approx(0.0, abs=1e-9)
    assert result.intercept == pytest.approx(0.0, abs=1e-9)
    assert result.ece == pytest.approx(0.25)


def test_ece_weights_each_bin_by_its_share_of_pairs() -> None:
    # Havuzlanmış 10 çift: p=.75 → y 1,0,1 · p=.25 → y 0,1,0 · p=.35 → y 0,0 · p=.65 → y 1,1
    # 10 kova: (3/10)·|2/3 − 0.75| + (3/10)·|1/3 − 0.25| + (2/10)·0.35 + (2/10)·0.35 = 0.19
    #   (ağırlıksız kova ortalaması 0.2167 olurdu)
    # 2 kova: [0, .5) → |Σy − Σp| = |1 − 1.45| = 0.45 · [.5, 1] → |4 − 3.55| = 0.45 → 0.9/10 = 0.09
    probs = ((0.75, 0.25),) * 3 + ((0.35, 0.65),) * 2
    outcomes = (0, 1, 0, 1, 1)
    assert calibration(probs, outcomes).ece == pytest.approx(0.19)
    assert calibration(probs, outcomes, bins=2).ece == pytest.approx(0.09)


def _synthetic(size: int, *, sharpen: float) -> Sample:
    """Gerçek olasılıktan çekilmiş sonuçlar; tahmin `truth ** sharpen` (1 = kalibre)."""
    rng = np.random.default_rng(7)
    weights = np.exp(rng.normal(0.0, 1.0, size=(size, 3)))
    truth = weights / weights.sum(axis=1, keepdims=True)
    draws = rng.random(size)
    outcomes = np.minimum((np.cumsum(truth, axis=1) < draws[:, None]).sum(axis=1), 2)
    stated = truth**sharpen
    stated = stated / stated.sum(axis=1, keepdims=True)
    probs = tuple(tuple(float(value) for value in row) for row in stated)
    return probs, tuple(int(value) for value in outcomes)


def test_a_calibrated_forecast_has_slope_near_one_and_intercept_near_zero() -> None:
    result = calibration(*_synthetic(20_000, sharpen=1.0))
    assert result.slope == pytest.approx(1.0, abs=0.05)
    assert result.intercept == pytest.approx(0.0, abs=0.05)
    assert result.ece < 0.02
    assert result.n == 60_000


def test_an_over_confident_forecast_has_slope_below_one() -> None:
    confident = calibration(*_synthetic(20_000, sharpen=2.0))
    assert confident.slope < 0.8
    assert confident.ece > calibration(*_synthetic(20_000, sharpen=1.0)).ece


def test_calibration_refuses_forecasts_without_spread() -> None:
    with pytest.raises(ValueError, match="tekil"):
        calibration(((0.5, 0.5),) * 4, (0, 1, 0, 1))


def test_calibration_refuses_a_perfectly_separated_sample() -> None:
    # En olası sonuç HER maçta gerçekleşti: ML eğimi sonsuza gider, fit yakınsayamaz.
    with pytest.raises(ValueError, match="kalibrasyon fiti"):
        calibration(((0.7, 0.3), (0.3, 0.7)), (0, 1))


def test_clv_is_price_times_fair_probability_minus_one() -> None:
    assert clv(2.2, 0.5) == pytest.approx(0.1)
    assert clv(1.8, 0.5) == pytest.approx(-0.1)
    assert clv(2.0, 0.5) == 0.0


@pytest.mark.parametrize(
    ("price", "probability"),
    ((1.0, 0.5), (0.5, 0.5), (math.inf, 0.5), (2.0, -0.1), (2.0, 1.1), (2.0, math.nan)),
)
def test_clv_rejects_impossible_inputs(price: float, probability: float) -> None:
    with pytest.raises(ValueError):
        clv(price, probability)


def test_bootstrap_is_deterministic_for_a_seed() -> None:
    values = tuple(float(value) for value in range(50))
    first = bootstrap_mean(values, resamples=500, seed=3)
    assert first == bootstrap_mean(values, resamples=500, seed=3)
    assert first != bootstrap_mean(values, resamples=500, seed=4)


def test_bootstrap_defaults_are_2000_resamples_the_project_seed_and_95_percent() -> None:
    values = (0.0, 1.0) * 50
    assert bootstrap_mean(values) == bootstrap_mean(
        values, resamples=2000, seed=20260922, level=0.95
    )


def test_bootstrap_interval_brackets_the_sample_mean() -> None:
    interval = bootstrap_mean((0.0, 1.0) * 200, resamples=2000, seed=11)
    assert interval.estimate == 0.5
    # ortalamanın standart hatası 0.5/√400 = 0.025 → %95 aralık ≈ 0.5 ± 0.049
    assert interval.low == pytest.approx(0.451, abs=0.01)
    assert interval.high == pytest.approx(0.549, abs=0.01)


def test_bootstrap_level_sets_the_width() -> None:
    values = (0.0, 1.0) * 200
    wide = bootstrap_mean(values, resamples=1000, level=0.95)
    narrow = bootstrap_mean(values, resamples=1000, level=0.50)
    assert wide.low < narrow.low < 0.5 < narrow.high < wide.high


def test_constant_values_give_a_zero_width_interval() -> None:
    assert bootstrap_mean((0.25,) * 10, resamples=50) == Interval(0.25, 0.25, 0.25)


@pytest.mark.parametrize(
    "kwargs",
    ({"resamples": 0}, {"level": 1.0}, {"level": 0.0}),
    ids=("tekrar-yok", "duzey-bir", "duzey-sifir"),
)
def test_bootstrap_rejects_meaningless_settings(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        bootstrap_mean((0.1, 0.2), **kwargs)
    with pytest.raises(ValueError):
        bootstrap_mean(())


@pytest.mark.parametrize(("goals", "index"), (((2, 0), 0), ((1, 1), 1), ((0, 3), 2)))
def test_outcome_index_for_1x2_follows_results_order(goals: tuple[int, int], index: int) -> None:
    assert outcome_index(hist_match(goals=goals), H2H) == index


@pytest.mark.parametrize(
    ("goals", "index"), (((2, 1), 0), ((3, 0), 0), ((1, 1), 1), ((2, 0), 1), ((0, 0), 1))
)
def test_outcome_index_for_totals_is_over_from_three_goals(
    goals: tuple[int, int], index: int
) -> None:
    assert outcome_index(hist_match(goals=goals), TOTALS_25) == index


def test_outcome_index_rejects_an_unknown_market() -> None:
    with pytest.raises(ValueError, match="bilinmeyen"):
        outcome_index(hist_match(), "ah")
