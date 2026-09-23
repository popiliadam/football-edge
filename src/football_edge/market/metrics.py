"""Olasılık tahmini ölçütleri: log loss, Brier, RPS, kalibrasyon, CLV, bootstrap (tasarım §7.5).

`outcomes` her maçta gerçekleşen sonucun MARKET_OUTCOMES içindeki sırasıdır (1X2'de H=0, D=1,
A=2). Saf fonksiyonlar; yalnız numpy (D15).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from football_edge.history.types import H2H, RESULTS, TOTALS_25, HistMatch

# log(0) sonsuzdur: tek bir kesin yanlış tahmin ortalamayı sonsuza götürmesin.
LOG_FLOOR = 1e-15
# logit(0) ve logit(1) tanımsız: kalibrasyon fiti uçları kırpar.
LOGIT_CLIP = 1e-6
# Toplamı 1'den bundan çok sapan satır dağılım değildir; normalleştirme yuvarlaması (~1e-16)
# rahatça içeride kalır.
ROW_SUM_TOLERANCE = 1e-9
_IRLS_STEPS = 100
_IRLS_TOLERANCE = 1e-10
# exp taşmasın: |η| > 500'de sigmoid zaten 0 ya da 1'dir.
_ETA_LIMIT = 500.0

Floats = npt.NDArray[np.float64]
Indices = npt.NDArray[np.int64]


@dataclass(frozen=True)
class Interval:
    estimate: float
    low: float
    high: float


class CalibrationUnfit(ValueError):
    """Kalibrasyon fiti bu örnekte kurulamıyor (tekil, ıraksak ya da yakınsamayan): ölçülemez.

    `pool.NotConverged` deseni: veri meşru biçimde dejenereyse budur; biçim/değer hatası
    (`_checked`) çıplak `ValueError` kalır — çağıran yalnız bunu "ölçülemedi"ye çevirir."""


@dataclass(frozen=True)
class Calibration:
    slope: float
    intercept: float
    ece: float
    n: int  # havuzlanmış (olasılık, gerçekleşme) çifti sayısı: maç × sonuç


def _checked(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> tuple[Floats, Indices]:
    if len(probs) != len(outcomes):
        raise ValueError(f"olasılık ({len(probs)}) ve sonuç ({len(outcomes)}) sayısı farklı")
    if len(probs) == 0:
        raise ValueError("ölçüt boş örnekte tanımsız")
    widths = {len(row) for row in probs}
    if len(widths) != 1 or min(widths) < 2:
        raise ValueError(f"her satır aynı sayıda (≥ 2) sonuç taşımalı: {sorted(widths)}")
    matrix = np.asarray(probs, dtype=np.float64)
    if not np.all(np.isfinite(matrix)) or np.any(matrix < 0.0) or np.any(matrix > 1.0):
        raise ValueError("olasılıklar sonlu ve [0, 1] aralığında olmalı")
    drift = float(np.max(np.abs(matrix.sum(axis=1) - 1.0)))
    if drift > ROW_SUM_TOLERANCE:
        raise ValueError(
            f"her satırın olasılık toplamı 1 olmalı: sapma {drift:.3g} > {ROW_SUM_TOLERANCE:g}"
        )
    # np.asarray(…, dtype=int64) 0.9'u sessizce 0'a keserdi: tamsayı olmayan sıra adıyla reddedilir.
    strays = [value for value in outcomes if not isinstance(value, (int, np.integer))]
    if strays:
        raise ValueError(f"sonuç sırası tamsayı olmalı: {strays[0]!r}")
    index = np.asarray(outcomes, dtype=np.int64)
    if np.any(index < 0) or np.any(index >= matrix.shape[1]):
        raise ValueError("sonuç sırası olasılık satırının dışında")
    return matrix, index


def _one_hot(index: Indices, width: int) -> Floats:
    return np.eye(width, dtype=np.float64)[index]


def per_match_log_loss(
    probs: Sequence[Sequence[float]], outcomes: Sequence[int]
) -> tuple[float, ...]:
    """Maç başına −log(max(p[sonuç], 1e-15))."""
    matrix, index = _checked(probs, outcomes)
    hit = matrix[np.arange(index.size), index]
    return tuple(float(value) for value in -np.log(np.maximum(hit, LOG_FLOOR)))


def log_loss(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> float:
    values = per_match_log_loss(probs, outcomes)
    return math.fsum(values) / len(values)


def brier(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> float:
    """Çok sınıflı Brier: maç başına Σ_k (p_k − y_k)², maçlar üzerinde ortalama."""
    matrix, index = _checked(probs, outcomes)
    gap = matrix - _one_hot(index, matrix.shape[1])
    return float(np.mean(np.sum(gap * gap, axis=1)))


def rps(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> float:
    """Sıralı sonuçlar için RPS: (1/(K−1)) Σ_{k<K} (Σ_{j≤k} p_j − Σ_{j≤k} y_j)², ortalama."""
    matrix, index = _checked(probs, outcomes)
    width = matrix.shape[1]
    gap = np.cumsum(matrix, axis=1) - np.cumsum(_one_hot(index, width), axis=1)
    return float(np.mean(np.sum(gap[:, :-1] ** 2, axis=1) / (width - 1)))


def _logistic_fit(x: Floats, y: Floats) -> tuple[float, float]:
    """y ~ a + b·x lojistik fiti (Newton/IRLS); (a, b) döner."""
    if float(np.ptp(x)) == 0.0:
        raise CalibrationUnfit("kalibrasyon fiti tekil: bütün logit(p) değerleri aynı")
    design = np.column_stack((np.ones_like(x), x))
    beta = np.array([0.0, 1.0])  # mükemmel kalibrasyondan başlar
    for _ in range(_IRLS_STEPS):
        eta = np.clip(design @ beta, -_ETA_LIMIT, _ETA_LIMIT)
        mu = 1.0 / (1.0 + np.exp(-eta))
        hessian = design.T @ (design * (mu * (1.0 - mu))[:, None])
        try:
            step = np.linalg.solve(hessian, design.T @ (y - mu))
        except np.linalg.LinAlgError as error:
            raise CalibrationUnfit("kalibrasyon fiti tekil (Hessian tersinmez)") from error
        beta = beta + step
        if not np.all(np.isfinite(beta)):
            raise CalibrationUnfit("kalibrasyon fiti ıraksadı")
        if float(np.max(np.abs(step))) < _IRLS_TOLERANCE:
            return float(beta[0]), float(beta[1])
    raise CalibrationUnfit("kalibrasyon fiti yakınsamadı (ayrışan örnek olabilir)")


def _ece(p: Floats, y: Floats, bins: int) -> float:
    # Σ (n_b/n)·|ȳ_b − p̄_b| = Σ |Σy_b − Σp_b| / n; boş kova katkı vermez.
    which = np.minimum((p * bins).astype(np.int64), bins - 1)
    hits = np.bincount(which, weights=y, minlength=bins)
    stated = np.bincount(which, weights=p, minlength=bins)
    return float(np.sum(np.abs(hits - stated)) / p.size)


def calibration(
    probs: Sequence[Sequence[float]], outcomes: Sequence[int], *, bins: int = 10
) -> Calibration:
    """Tek-karşı-hepsi havuzlanmış (p, y) çiftlerinde y ~ a + b·logit(p) ve eşit kovalı ECE."""
    if bins < 1:
        raise ValueError(f"kova sayısı ≥ 1 olmalı: {bins}")
    matrix, index = _checked(probs, outcomes)
    p = matrix.ravel()
    y = _one_hot(index, matrix.shape[1]).ravel()
    clipped = np.clip(p, LOGIT_CLIP, 1.0 - LOGIT_CLIP)
    intercept, slope = _logistic_fit(np.log(clipped / (1.0 - clipped)), y)
    return Calibration(slope=slope, intercept=intercept, ece=_ece(p, y, bins), n=int(p.size))


def clv(price: float, fair_probability: float) -> float:
    """Kapanışa göre değer: price · p − 1 (p vig'i temizlenmiş kapanış olasılığı)."""
    if not math.isfinite(price) or price <= 1.0:
        raise ValueError(f"fiyat sonlu ve 1.0'dan büyük olmalı: {price!r}")
    if not 0.0 <= fair_probability <= 1.0:
        raise ValueError(f"olasılık [0, 1] aralığında olmalı: {fair_probability!r}")
    return price * fair_probability - 1.0


def bootstrap_mean(
    values: Sequence[float],
    *,
    resamples: int = 2000,
    seed: int = 20260922,
    level: float = 0.95,
) -> Interval:
    """Ortalama ve maç düzeyinde yerine koymalı yüzdelik bootstrap aralığı (sabit tohum)."""
    if len(values) == 0:
        raise ValueError("boş örneğin ortalaması yok")
    if resamples < 1:
        raise ValueError(f"yeniden örnekleme sayısı ≥ 1 olmalı: {resamples}")
    if not 0.0 < level < 1.0:
        raise ValueError(f"güven düzeyi (0, 1) aralığında olmalı: {level}")
    data = np.asarray(values, dtype=np.float64)
    rng = np.random.default_rng(seed)
    # Tekrar başına bir çekiliş: bellek n × resamples'a büyümez (havuzlanmış K1'de ~45 bin maç).
    means = np.array(
        [float(np.mean(data[rng.integers(0, data.size, size=data.size)])) for _ in range(resamples)]
    )
    tail = (1.0 - level) / 2.0 * 100.0
    low, high = np.percentile(means, [tail, 100.0 - tail])
    return Interval(estimate=math.fsum(values) / len(values), low=float(low), high=float(high))


def outcome_index(match: HistMatch, market: str) -> int:
    """Gerçekleşen sonucun MARKET_OUTCOMES[market] içindeki sırası."""
    if market == H2H:
        return RESULTS.index(match.result)
    if market == TOTALS_25:
        return 0 if match.home_goals + match.away_goals > 2.5 else 1
    raise ValueError(f"bilinmeyen market: {market!r}")
