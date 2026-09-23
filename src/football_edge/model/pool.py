"""Log-doğrusal görüş havuzu (Faz 3 tasarımı §6.3, R131).

`p ∝ exp(Σ wᵢ · log pᵢ)`, ağırlıklar ≥ 0. `w = (1, 0, …)` havuzun içindedir: doğru fit edilmiş bir
harman, fit edildiği veride ilk bileşenden (piyasa) kötü olamaz — kapının akıl sağlığı sınaması
(G4/W1) buna yaslanır. Ağırlık için ön bilgi girilmez; başlangıç noktası yalnız piyasadır.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.optimize import minimize

Floats = npt.NDArray[np.float64]

LOG_FLOOR = 1e-15
MAX_WEIGHT = 5.0
MIN_FIT_MATCHES = 300


class TooFewMatches(ValueError):
    """Ağırlık fiti için maç sayısı `MIN_FIT_MATCHES`in altında."""


def _logs(components: npt.ArrayLike) -> Floats:
    return np.log(np.maximum(np.asarray(components, dtype=np.float64), LOG_FLOOR))


def pool(components: Sequence[Sequence[float]], weights: Sequence[float]) -> tuple[float, ...]:
    """Bileşen olasılıkları (her biri aynı sonuç sırasıyla) → havuzlanmış, toplamı 1."""
    if len(components) != len(weights):
        raise ValueError(f"{len(components)} bileşen, {len(weights)} ağırlık")
    if any(weight < 0 for weight in weights):
        raise ValueError(f"negatif ağırlık: {tuple(weights)}")
    exponent = np.asarray(weights, dtype=np.float64) @ _logs(components)
    shifted = np.exp(exponent - exponent.max())
    return tuple(float(value) for value in shifted / shifted.sum())


def _objective(
    weights: Floats, logs: Floats, outcomes: npt.NDArray[np.int64]
) -> tuple[float, Floats]:
    """Ortalama log loss ve ağırlıklara göre gradyanı; `logs` şekli (maç, bileşen, sonuç)."""
    exponent = np.einsum("c,mcs->ms", weights, logs)
    exponent = exponent - exponent.max(axis=1, keepdims=True)
    probs = np.exp(exponent)
    probs = probs / probs.sum(axis=1, keepdims=True)
    rows = np.arange(len(outcomes))
    chosen = np.maximum(probs[rows, outcomes], LOG_FLOOR)
    expected = np.einsum("ms,mcs->mc", probs, logs)
    gradient = -(logs[rows, :, outcomes] - expected).mean(axis=0)
    return float(-np.log(chosen).mean()), gradient


def fit_weights(
    components: Sequence[Sequence[Sequence[float]]], outcomes: Sequence[int]
) -> tuple[float, ...]:
    """Maç başına bileşen olasılıkları ve gerçekleşen sonuç sırası → log loss'u en küçük ağırlık."""
    if len(components) != len(outcomes):
        raise ValueError(f"{len(components)} maç, {len(outcomes)} sonuç")
    if len(outcomes) < MIN_FIT_MATCHES:
        raise TooFewMatches(f"{len(outcomes)} maç < {MIN_FIT_MATCHES}")
    logs = _logs(components)
    count = logs.shape[1]
    start = np.zeros(count)
    start[0] = 1.0
    result: Any = minimize(
        _objective,
        start,
        args=(logs, np.asarray(outcomes, dtype=np.int64)),
        jac=True,
        method="L-BFGS-B",
        bounds=[(0.0, MAX_WEIGHT)] * count,
    )
    if not bool(result.success):
        raise ValueError(f"ağırlık fiti yakınsamadı: {result.message}")
    return tuple(float(value) for value in np.asarray(result.x, dtype=np.float64))
