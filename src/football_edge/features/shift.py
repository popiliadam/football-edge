"""Harman çıkışında logit kaydırma (R168): `p_jev ∝ p_harman · exp(±β·f)`.

Ev logiti `+β·f`, deplasman `−β·f`, beraberlik 0. `β·f == 0` iken girdi BİREBİR döner: özelliksiz
maçta `harman_jev` ile `harman` aynı sayıdır, yuvarlama farkı bile yoktur (gölge serisi bölünmez).
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def shift(
    probs: tuple[float, float, float], beta: Sequence[float], f: Sequence[float]
) -> tuple[float, float, float]:
    if len(probs) != 3:
        raise ValueError(f"üç olasılık (ev, beraberlik, deplasman) olmalı: {probs}")
    if len(beta) != len(f):
        raise ValueError(f"β ({len(beta)}) ve f ({len(f)}) aynı uzunlukta olmalı")
    if not all(math.isfinite(value) for value in (*probs, *beta, *f)):
        raise ValueError("sonlu olmayan olasılık, β ya da özellik")
    if min(probs) < 0 or math.fsum(probs) <= 0:
        raise ValueError(f"geçersiz olasılıklar: {probs}")
    s = math.fsum(b * x for b, x in zip(beta, f, strict=True))
    if s == 0.0:
        return probs
    if not math.isfinite(s):
        raise ValueError("β·f taştı")
    home, draw, away = probs
    # Büyük |s|'de taşmasın diye ortak çarpan dışarı: (h·e^s, d, a·e^−s) ∝ (h, d·e^−s, a·e^−2s).
    if s > 0:
        weights = (home, draw * math.exp(-s), away * math.exp(-2 * s))
    else:
        weights = (home * math.exp(2 * s), draw * math.exp(s), away)
    total = math.fsum(weights)
    if total <= 0:
        raise ValueError(f"kaydırma sayısal olarak tanımsız (s={s}, p={probs})")
    return weights[0] / total, weights[1] / total, weights[2] / total
