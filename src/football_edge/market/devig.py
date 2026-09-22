"""Vig temizleme: bahisçi marjını fiyatlardan ayırıp adil olasılık üretir (tasarım §6, D9).

`q_i = 1/o_i`, `B = Σ q_i`. Üç yöntem saf fonksiyondur; kök bulma stdlib ikiye bölmesidir
(scipy yok, D15). Her iki kök fonksiyonu da parametresinde kesin azalandır — bu yüzden tek kök
vardır ve ikiye bölme onu bulur.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from football_edge.history.types import MARKET_OUTCOMES, HistMatch

MULTIPLICATIVE: str = "multiplicative"
POWER: str = "power"
SHIN: str = "shin"
METHODS: tuple[str, ...] = (MULTIPLICATIVE, POWER, SHIN)
TOLERANCE: float = 1e-12
# Task 9'un ölçümü (K2) başka yöntemi seçerse controller Task 12'de günceller.
DEFAULT_METHOD: str = SHIN

# Aralık her adımda yarılanır: 200 adım float çözünürlüğünün çok ötesidir; sonsuz döngü olmaz.
_MAX_STEPS = 200
# Shin'in içeriden bilgi payı z ∈ [0, 0.5); üst uçta kök yoksa çözüm tanımsızdır.
_SHIN_Z_LIMIT = 0.5


class InvalidPrices(ValueError):
    """Vig'i temizlenemeyen fiyat kümesi (sayı, değer ya da yöntemin koşulu tutmuyor)."""


def _check_method(method: str) -> None:
    # Bilinmeyen yöntem veri değil programlama hatasıdır: InvalidPrices DEĞİL, düz ValueError.
    # `match_probs` InvalidPrices'ı None'a çevirir; yazım hatası her maçı sessizce düşürmesin.
    if method not in METHODS:
        raise ValueError(f"bilinmeyen vig yöntemi: {method!r} (seçenekler: {', '.join(METHODS)})")


def _check_market(market: str) -> None:
    # `HistMatch.prices` bilinmeyen markette çıplak KeyError verir; `outcome_index` ile aynı hata.
    if market not in MARKET_OUTCOMES:
        raise ValueError(f"bilinmeyen market: {market!r}")


def _implied(prices: Sequence[float]) -> tuple[float, ...]:
    if len(prices) < 2:
        raise InvalidPrices(f"en az iki fiyat gerekir, {len(prices)} verildi")
    for price in prices:
        if not math.isfinite(price) or price <= 1.0:
            raise InvalidPrices(f"fiyat sonlu ve 1.0'dan büyük olmalı: {price!r}")
    return tuple(1.0 / price for price in prices)


def overround(prices: Sequence[float]) -> float:
    """Kitabın marjı: Σ 1/o − 1 (adil kitapta 0)."""
    return math.fsum(_implied(prices)) - 1.0


def _bisect(excess: Callable[[float], float], low: float, high: float) -> float:
    """Azalan `excess` için excess(low) > 0 ≥ excess(high) aralığındaki kökü döner."""
    for _ in range(_MAX_STEPS):
        if high - low <= TOLERANCE:
            break
        middle = (low + high) / 2.0
        if excess(middle) > 0.0:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def _power(implied: tuple[float, ...], total: float) -> tuple[float, ...]:
    def excess(k: float) -> float:
        return math.fsum(math.pow(q, k) for q in implied) - 1.0

    # Σ q^k k'da azalır ve k = 1'de B − 1'dir: B > 1 ise kök k > 1'de, B < 1 ise k < 1'de.
    low, high = (1.0, 2.0) if total > 1.0 else (0.5, 1.0)
    while excess(high) > 0.0:
        high *= 2.0
    while excess(low) <= 0.0:
        low /= 2.0
    k = _bisect(excess, low, high)
    return tuple(math.pow(q, k) for q in implied)


def _shin_probs(implied: tuple[float, ...], total: float, z: float) -> tuple[float, ...]:
    return tuple(
        (math.sqrt(z * z + 4.0 * (1.0 - z) * q * q / total) - z) / (2.0 * (1.0 - z))
        for q in implied
    )


def _shin(implied: tuple[float, ...], total: float) -> tuple[float, ...]:
    if total < 1.0:
        raise InvalidPrices(f"Shin yöntemi Σ 1/o ≥ 1 ister, {total:.6f} verildi")

    def excess(z: float) -> float:
        return math.fsum(_shin_probs(implied, total, z)) - 1.0

    # z = 0'da Σ p = √B > 1; her p_i z'de kesin azalır (q_i²/B < 1 olduğu için).
    if excess(_SHIN_Z_LIMIT) >= 0.0:
        raise InvalidPrices(f"Shin çözümü z ∈ [0, 0.5) aralığında yok (Σ 1/o = {total:.6f})")
    return _shin_probs(implied, total, _bisect(excess, 0.0, _SHIN_Z_LIMIT))


def devig(prices: Sequence[float], method: str) -> tuple[float, ...]:
    """Vig'i temizlenmiş olasılıklar, `prices` sırasıyla; toplamları 1'dir.

    ≥ 2 fiyat, hepsi sonlu ve > 1.0; SHIN için Σ 1/o ≥ 1 — değilse InvalidPrices.
    """
    _check_method(method)
    implied = _implied(prices)
    total = math.fsum(implied)
    if total == 1.0:
        # Adil kitap: marj yok, her yöntemde p = q. Kök aramak yalnız yuvarlama gürültüsü katar.
        return implied
    if method == MULTIPLICATIVE:
        return tuple(q / total for q in implied)
    if method == POWER:
        return _power(implied, total)
    return _shin(implied, total)


def match_probs(
    match: HistMatch, *, book: str, market: str, phase: str, method: str
) -> tuple[float, ...] | None:
    """Kitap/market/evre fiyatlarının adil olasılıkları; fiyat eksik ya da çözülemezse None.

    T4, T7 ve T10 bu tek yolu paylaşır: aynı eksik-veri kuralı üç yerde ayrı yazılmaz.
    """
    _check_method(method)
    _check_market(market)
    prices = match.prices(book, market, phase)
    if prices is None:
        return None
    try:
        return devig(prices, method)
    except InvalidPrices:
        return None
