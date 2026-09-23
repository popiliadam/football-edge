"""Modelin bilinen sonuçları (Faz 3 tasarımı §9 G4; R130): E bölgesinde, haftalık.

Kapı: W1 bir DAHA KÖTÜ OLMAMA (non-inferiority) sınamasıdır (R143): maç başına
LL(harman) − LL(piyasa) ortalamasının %95 bootstrap aralığının ÜST ucu ≤ δ = `W1_MARGIN`.
Bootstrap Faz 2'ninkidir (`market.metrics.bootstrap_mean`: maç düzeyinde yeniden örnekleme, tohum
20260922, düzey 0.95, B = `--resamples`, varsayılan 2.000 — `market/efficiency.py`nin
RESAMPLES/SEED/LEVEL'i). `w = (1, 0, 0)` havuzun içinde olduğu için doğru bir fit buna uyar;
kırmızıysa fit ya da hat bozuktur ya da harmanın piyasadan kötü olmadığı gösterilemedi.
W2 fit Elo iskele Elo'dan isabetli (ortalama ΔLL < 0) · W3 Dixon-Coles S'nin sonuç oranlarından
isabetli. Rapor: W4 harmanın kalibrasyonu. Ölçülemeyen denetim GEÇMEZ ("ölçülemedi" yazar).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from football_edge.backtest.harness import Strategy
from football_edge.backtest.model_config import ModelConfig
from football_edge.backtest.selftest import Check, unmeasured
from football_edge.backtest.strategies import EloPointInTime
from football_edge.backtest.walkforward import (
    DC,
    ELO,
    ELO_SCAFFOLD,
    EVALUATION,
    MARKET,
    SELECTION,
    Row,
    group_rows,
)
from football_edge.backtest.wf_eval import blended, complete, fold_weights, log_loss_gap
from football_edge.backtest.wf_run import model_strategies
from football_edge.history.catalog import MAIN
from football_edge.history.types import HistMatch
from football_edge.market.metrics import (
    LOG_FLOOR,
    Interval,
    calibration,
    interval_text,
)

E_UNMEASURED = "E bölgesinde uygun satır yok"

# ~5 bin maçlık bir katta üç ağırlığın örneklem dışı gürültüsü ~3e-4; δ bunun üç katı.
W1_MARGIN = 0.001


def w1_passes(gap: Interval) -> bool:
    """R143: daha kötü olmama — ÜST uç ≤ δ (nokta tahmini değil)."""
    return gap.high <= W1_MARGIN


def model_rows(
    groups: Mapping[str, Sequence[HistMatch]],
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    config: ModelConfig,
) -> tuple[Row, ...]:
    def strategies(matches: Sequence[HistMatch]) -> Mapping[str, Strategy]:
        return {
            **model_strategies(matches, kinds, rating_groups, config),
            ELO_SCAFFOLD: EloPointInTime(groups=rating_groups),
        }

    return tuple(
        row
        for matches in groups.values()
        for row in group_rows(matches, kinds, strategies(matches), method=config.method)
    )


def _w1(rows: Sequence[Row], resamples: int) -> tuple[Check, Check]:
    weights, _ = fold_weights(rows)
    main = [row for row in rows if row.zone == EVALUATION and row.kind == MAIN]
    pairs = blended(main, weights)
    if not pairs:
        return unmeasured("W1", gate=True, reason=E_UNMEASURED), unmeasured(
            "W4", gate=False, reason=E_UNMEASURED
        )
    outcomes = [row.outcome for row, _ in pairs]
    probs = [p for _, p in pairs]
    gap = log_loss_gap(probs, [row.components[MARKET] for row, _ in pairs], outcomes, resamples)
    try:
        fitted = calibration(probs, outcomes)
        w4 = Check(
            "W4", False, True, f"harman kalibrasyonu b={fitted.slope:.3f} ECE={fitted.ece:.4f}"
        )
    except ValueError as error:
        w4 = Check("W4", False, False, f"W4 ölçülemedi: {error}")
    ci = interval_text(gap, digits=5, label="%95 ")
    return (
        Check(
            "W1",
            True,
            w1_passes(gap),
            f"ΔLL harman − piyasa {ci}; üst uç ≤ {W1_MARGIN} n={len(pairs)}",
        ),
        w4,
    )


def _w2(rows: Sequence[Row], resamples: int) -> Check:
    usable = [
        row
        for row in rows
        if row.zone == EVALUATION and row.kind == MAIN and complete(row, (ELO, ELO_SCAFFOLD))
    ]
    if not usable:
        return unmeasured("W2", gate=True, reason=E_UNMEASURED)
    gap = log_loss_gap(
        [row.components[ELO] for row in usable],
        [row.components[ELO_SCAFFOLD] for row in usable],
        [row.outcome for row in usable],
        resamples,
    )
    ci = interval_text(gap, digits=5, label="%95 ")
    return Check(
        "W2",
        True,
        gap.estimate < 0.0,
        f"ΔLL fit Elo − iskele {ci} n={len(usable)}",
    )


def _w3(rows: Sequence[Row]) -> Check:
    base_rows = [row for row in rows if row.zone == SELECTION and row.kind == MAIN]
    usable = [
        row for row in rows if row.zone == EVALUATION and row.kind == MAIN and DC in row.components
    ]
    if not base_rows or not usable:
        return unmeasured("W3", gate=True, reason=E_UNMEASURED)
    counts = [sum(1 for row in base_rows if row.outcome == index) for index in range(3)]
    base = [count / len(base_rows) for count in counts]
    dc = math.fsum(-math.log(max(row.components[DC][row.outcome], LOG_FLOOR)) for row in usable)
    rate = math.fsum(-math.log(max(base[row.outcome], LOG_FLOOR)) for row in usable)
    dc, rate = dc / len(usable), rate / len(usable)
    return Check(
        "W3", True, dc < rate, f"LL Dixon-Coles {dc:.5f} < S oranları {rate:.5f} n={len(usable)}"
    )


def model_checks(rows: Sequence[Row], *, resamples: int) -> tuple[Check, ...]:
    w1, w4 = _w1(rows, resamples)
    return (w1, _w2(rows, resamples), _w3(rows), w4)
