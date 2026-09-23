"""Vig temizleme: üç yöntemin tanımı, özellikleri ve reddettiği girdiler (tasarım §6)."""

from __future__ import annotations

import math
from dataclasses import replace
from types import MappingProxyType

import pytest

from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, TOTALS_25, OddsKey
from football_edge.market.devig import (
    DEFAULT_METHOD,
    METHODS,
    MULTIPLICATIVE,
    POWER,
    SHIN,
    TOLERANCE,
    InvalidPrices,
    devig,
    match_probs,
    overround,
)
from football_edge.market.metrics import outcome_index
from tests.market_factory import hist_match

LOPSIDED = (1.30, 5.50, 11.0)  # net favori + iki sürpriz; Σ 1/o ≈ 1.051
BALANCED = (2.10, 3.40, 3.60)
TWO_WAY = (1.50, 2.60)
LONGSHOT = (1.05, 12.0, 30.0)
UNDER_ROUND = (2.2, 4.4, 4.4)  # Σ 1/o = 0.909: borsa en iyi fiyatlarında görülebilir
MARKETS = (LOPSIDED, BALANCED, TWO_WAY, LONGSHOT, (1.90, 1.90))


def test_contract_constants() -> None:
    assert METHODS == (MULTIPLICATIVE, POWER, SHIN) == ("multiplicative", "power", "shin")
    # K2 (2026-09-22, n=103.232 AvgC kapanış): power 1.00188 < shin 1.00195 < multiplicative
    # 1.00248 — varsayılan ölçülen en düşük log loss'lu yöntemdir.
    assert DEFAULT_METHOD == POWER
    assert TOLERANCE == 1e-12


def test_overround_is_the_implied_sum_minus_one() -> None:
    assert overround((2.0, 4.0, 4.0)) == 0.0  # 1/2 + 1/4 + 1/4 = 1: adil kitap
    assert overround((1.9, 1.9)) == pytest.approx(2.0 / 1.9 - 1.0, abs=1e-15)
    assert overround(UNDER_ROUND) < 0.0


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("prices", MARKETS)
def test_probabilities_sum_to_one(method: str, prices: tuple[float, ...]) -> None:
    probs = devig(prices, method)
    assert len(probs) == len(prices)
    assert math.fsum(probs) == pytest.approx(1.0, abs=1e-9)
    assert all(0.0 < p < 1.0 for p in probs)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("prices", (LOPSIDED, BALANCED, TWO_WAY, (3.4, 3.5, 2.2)))
def test_shorter_price_gets_higher_probability(method: str, prices: tuple[float, ...]) -> None:
    probs = devig(prices, method)
    by_price = sorted(range(len(prices)), key=lambda index: prices[index])
    by_probability = sorted(range(len(prices)), key=lambda index: -probs[index])
    assert by_price == by_probability


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("prices", ((2.0, 4.0, 4.0), (2.0, 2.0), (4.0, 4.0, 4.0, 4.0)))
def test_fair_book_returns_the_implied_probabilities_exactly(
    method: str, prices: tuple[float, ...]
) -> None:
    assert devig(prices, method) == tuple(1.0 / price for price in prices)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("prices", ((1.9, 1.9), (2.8, 2.8, 2.8)))
def test_symmetric_prices_give_equal_probabilities(method: str, prices: tuple[float, ...]) -> None:
    share = 1.0 / len(prices)
    assert devig(prices, method) == pytest.approx((share,) * len(prices), abs=1e-12)


def test_multiplicative_divides_by_the_book_sum() -> None:
    # 1/1.9 + 2 · 1/3.8 = 1.0526… → p = (0.5263/1.0526, 0.2632/1.0526, …) = (0.5, 0.25, 0.25)
    assert devig((1.9, 3.8, 3.8), MULTIPLICATIVE) == pytest.approx((0.5, 0.25, 0.25), abs=1e-12)


@pytest.mark.parametrize("prices", (LOPSIDED, BALANCED, TWO_WAY))
def test_power_probabilities_are_one_common_power_of_the_implied(prices: tuple[float, ...]) -> None:
    implied = tuple(1.0 / price for price in prices)
    probs = devig(prices, POWER)
    exponents = [math.log(p) / math.log(q) for p, q in zip(probs, implied, strict=True)]
    assert max(exponents) - min(exponents) < 1e-9
    # B > 1 (B < 1 reddedilir, 16i): k > 1 — marj uzak sonuçlardan daha çok alınır
    assert exponents[0] > 1.0


@pytest.mark.parametrize(
    ("prices", "exponent"),
    (((1.25, 1.25), math.log(0.5) / math.log(0.8)),),
    ids=("ust-uc",),
)
def test_power_widens_its_start_bracket_when_the_root_lies_outside_it(
    prices: tuple[float, ...], exponent: float
) -> None:
    # Başlangıç aralığı [1, 2]. (1.25, 1.25): B = 1.6, k = ln ½ / ln 0.8 ≈ 3.106. Aralık
    # genişlemeseydi ikiye bölme uca yapışır, Σ p 1'den uzak kalırdı. (B < 1'in alt ucu artık
    # yok: 16i o kitabı reddeder.)
    probs = devig(prices, POWER)
    assert math.fsum(probs) == pytest.approx(1.0, abs=1e-9)
    implied = tuple(1.0 / price for price in prices)
    exponents = [math.log(p) / math.log(q) for p, q in zip(probs, implied, strict=True)]
    assert exponents == pytest.approx([exponent] * len(prices), abs=1e-9)


@pytest.mark.parametrize("prices", (LOPSIDED, BALANCED, TWO_WAY, LONGSHOT))
def test_shin_probabilities_solve_the_shin_equation_with_one_nonnegative_z(
    prices: tuple[float, ...],
) -> None:
    implied = tuple(1.0 / price for price in prices)
    total = math.fsum(implied)
    probs = devig(prices, SHIN)
    # p_i = (√(z² + 4(1−z)·q_i²/B) − z) / (2(1−z))  ⇔  z = (q_i²/B − p_i²) / (p_i(1 − p_i))
    zs = [(q * q / total - p * p) / (p * (1.0 - p)) for p, q in zip(probs, implied, strict=True)]
    assert min(zs) >= 0.0
    assert max(zs) < 0.5
    assert max(zs) - min(zs) < 1e-9


@pytest.mark.parametrize("method", (POWER, SHIN))
def test_power_and_shin_give_the_favourite_more_than_multiplicative(method: str) -> None:
    plain = devig(LOPSIDED, MULTIPLICATIVE)
    adjusted = devig(LOPSIDED, method)
    assert adjusted[0] > plain[0]  # favori
    assert adjusted[2] < plain[2]  # en uzak sürpriz


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(
    "prices",
    ((), (2.0,), (1.0, 3.0), (0.9, 3.0), (-2.0, 3.0), (0.0, 3.0), (math.nan, 3.0), (math.inf, 3.0)),
    ids=("bos", "tek", "bir", "birin-alti", "negatif", "sifir", "nan", "sonsuz"),
)
def test_invalid_prices_are_rejected(method: str, prices: tuple[float, ...]) -> None:
    with pytest.raises(InvalidPrices):
        devig(prices, method)
    with pytest.raises(InvalidPrices):
        overround(prices)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(
    "prices", (UNDER_ROUND, (1.06, 10_000.0), (2.05, 2.05)), ids=("uc-yol", "uzak-uc", "iki-yol")
)
def test_every_method_rejects_a_book_under_one_hundred_percent(
    method: str, prices: tuple[float, ...]
) -> None:
    """16i: multiplicative ve power Σ 1/o < 1'i kabul edip olasılığı şişiriyordu (E'nin Ü/A
    "piyasa 1 bahis" satırı). Marj ölçülür (`overround` < 0) ama vig temizlenmez."""
    with pytest.raises(InvalidPrices, match="< 1"):
        devig(prices, method)
    assert overround(prices) < 0.0


def test_shin_rejects_a_margin_it_cannot_explain_below_z_one_half() -> None:
    # (1.25, 1.25): Σ 1/o = 1.6 — z = 0.5'te bile Σ p > 1, çözüm aralıkta yok
    with pytest.raises(InvalidPrices, match="z"):
        devig((1.25, 1.25), SHIN)


def test_unknown_method_is_a_programming_error_not_invalid_prices() -> None:
    with pytest.raises(ValueError, match="bilinmeyen") as caught:
        devig((2.0, 2.0), "additive")
    assert not isinstance(caught.value, InvalidPrices)


def test_match_probs_devigs_the_requested_book_market_and_phase() -> None:
    match = hist_match(
        prices={
            ("Avg", H2H, CLOSING): (1.9, 3.8, 3.8),
            ("Avg", H2H, PRE_CLOSING): (2.0, 4.0, 4.0),
            ("Avg", TOTALS_25, CLOSING): (1.9, 1.9),
        }
    )
    closing = match_probs(match, book="Avg", market=H2H, phase=CLOSING, method=MULTIPLICATIVE)
    assert closing == pytest.approx((0.5, 0.25, 0.25), abs=1e-12)
    early = match_probs(match, book="Avg", market=H2H, phase=PRE_CLOSING, method=MULTIPLICATIVE)
    assert early == (0.5, 0.25, 0.25)
    totals = match_probs(match, book="Avg", market=TOTALS_25, phase=CLOSING, method=SHIN)
    assert totals == pytest.approx((0.5, 0.5), abs=1e-12)


def test_match_probs_is_none_when_a_price_is_missing() -> None:
    match = hist_match(prices={("Avg", H2H, CLOSING): (1.9, 3.8, 3.8)})
    assert match_probs(match, book="PS", market=H2H, phase=CLOSING, method=SHIN) is None
    assert match_probs(match, book="Avg", market=H2H, phase=PRE_CLOSING, method=SHIN) is None
    partial = replace(
        match,
        odds=MappingProxyType(
            {
                OddsKey("Avg", H2H, "H", CLOSING): 1.9,
                OddsKey("Avg", H2H, "A", CLOSING): 3.8,
            }
        ),
    )
    assert match_probs(partial, book="Avg", market=H2H, phase=CLOSING, method=SHIN) is None


def test_match_probs_is_none_when_the_method_cannot_solve_the_prices() -> None:
    under = hist_match(prices={("Avg", H2H, CLOSING): UNDER_ROUND})
    wide = hist_match(prices={("Avg", H2H, CLOSING): (1.25, 1.25, 30.0)})
    for method in METHODS:
        assert match_probs(under, book="Avg", market=H2H, phase=CLOSING, method=method) is None
    assert match_probs(wide, book="Avg", market=H2H, phase=CLOSING, method=SHIN) is None
    assert match_probs(wide, book="Avg", market=H2H, phase=CLOSING, method=POWER) is not None


def test_match_probs_does_not_hide_an_unknown_method() -> None:
    bare = hist_match()  # fiyatsız maç: yazım hatası yine de sessiz None olmamalı
    with pytest.raises(ValueError, match="bilinmeyen"):
        match_probs(bare, book="Avg", market=H2H, phase=CLOSING, method="shinn")


def test_match_probs_names_an_unknown_market_like_outcome_index() -> None:
    # Çıplak KeyError değil: bilinmeyen market iki modülde de aynı adlı ValueError'dır.
    bare = hist_match()
    with pytest.raises(ValueError, match="bilinmeyen market") as from_devig:
        match_probs(bare, book="Avg", market="ah", phase=CLOSING, method=SHIN)
    with pytest.raises(ValueError) as from_metrics:
        outcome_index(bare, "ah")
    assert str(from_devig.value) == str(from_metrics.value)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("prices", ((1.04, 26.0), (1.08, 13.5)))
def test_an_exactly_fair_book_one_ulp_short_is_still_a_fair_book(
    method: str, prices: tuple[float, ...]
) -> None:
    """Review Focus (16i): 1/1.04 + 1/26 = 1 tam, ama float toplamı 0.9999999999999999. Katı
    `< 1` koruması adil kitabı reddederdi (Shin eskiden de reddediyordu)."""
    assert math.fsum(1.0 / price for price in prices) < 1.0

    assert devig(prices, method) == tuple(1.0 / price for price in prices)
