"""Yeniden oynatmanın değerlendirmesi (tasarım §7.5): isabet, kalibrasyon, CLV.

Kapanış YALNIZ burada, bütün tahminler dondurulduktan sonra `ReplayResult.outcomes`tan okunur.
CLV'nin referansı vig'i temizlenmiş kapanış `AvgC`'dir (D3); kapanışı tam olmayan bahis CLV'ye
girmez, sayısı `bets` ile bahisli tahmin sayısının farkıdır.
"""

from __future__ import annotations

from dataclasses import dataclass

from football_edge.backtest.harness import Outcome, ReplayResult
from football_edge.history.types import CLOSING, H2H, REFERENCE_BOOK, RESULTS, OddsKey
from football_edge.market.devig import InvalidPrices, devig
from football_edge.market.metrics import (
    Calibration,
    Interval,
    bootstrap_mean,
    brier,
    calibration_or_none,
    clv,
    per_match_log_loss,
    rps,
)

DEFAULT_RESAMPLES = 2000


@dataclass(frozen=True)
class Evaluation:
    strategy: str
    n: int
    log_loss: Interval
    brier: float
    rps: float
    calibration: Calibration | None
    clv: Interval | None
    bets: int


def _closing_probs(outcome: Outcome, method: str) -> tuple[float, ...] | None:
    """Kapanış `AvgC` 1X2'sinin adil olasılığı; eksik ya da reddedilen fiyatta None."""
    keys = [
        OddsKey(book=REFERENCE_BOOK, market=H2H, outcome=name, phase=CLOSING) for name in RESULTS
    ]
    if not all(key in outcome.closing for key in keys):
        return None
    try:
        return devig([outcome.closing[key] for key in keys], method)
    except InvalidPrices:
        return None


def clv_values(result: ReplayResult, *, method: str) -> tuple[float, ...]:
    """Bahisli ve kapanışı tam tahminlerin CLV'si, tahmin sırasıyla (K4 de bunu kullanır)."""
    values: list[float] = []
    for prediction in result.predictions:
        if prediction.bet is None:
            continue
        fair = _closing_probs(result.outcomes[prediction.match_index], method)
        if fair is not None:
            values.append(clv(prediction.bet.price, fair[RESULTS.index(prediction.bet.outcome)]))
    return tuple(values)


def evaluate(
    result: ReplayResult, *, method: str, resamples: int = DEFAULT_RESAMPLES
) -> Evaluation:
    """Her tahmini KENDİ maçının sonucuyla ölçer; bahislerin CLV'si kapanışı tam olanlarda."""
    if not result.predictions:
        raise ValueError(f"{result.strategy}: değerlendirilecek tahmin yok")
    probs = [prediction.probs for prediction in result.predictions]
    outcomes = [
        RESULTS.index(result.outcomes[prediction.match_index].result)
        for prediction in result.predictions
    ]
    values = clv_values(result, method=method)
    return Evaluation(
        strategy=result.strategy,
        n=len(probs),
        log_loss=bootstrap_mean(per_match_log_loss(probs, outcomes), resamples=resamples),
        brier=brier(probs, outcomes),
        rps=rps(probs, outcomes),
        calibration=calibration_or_none(probs, outcomes),
        clv=bootstrap_mean(values, resamples=resamples) if values else None,
        bets=len(values),
    )
