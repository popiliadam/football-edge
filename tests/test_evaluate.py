"""Değerlendirme: her tahmin kendi sonucuyla; CLV yalnız kapanışı tam bahislerde, AvgC'ye karşı."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from functools import partial
from types import MappingProxyType

import pytest

from football_edge.backtest.evaluate import evaluate
from football_edge.backtest.harness import Bet, Outcome, Prediction, ReplayResult, replay
from football_edge.backtest.strategies import Placebo
from football_edge.history.types import CLOSING, PRE_CLOSING, RESULTS, OddsKey
from football_edge.market.devig import MULTIPLICATIVE, SHIN, devig
from football_edge.market.metrics import (
    bootstrap_mean,
    brier,
    calibration,
    per_match_log_loss,
    rps,
)
from tests.backtest_builders import hist_match, quote

SCORES = {"H": (1, 0), "D": (1, 1), "A": (0, 1)}
AVG_CLOSE = quote("Avg", CLOSING, (2.0, 3.4, 4.2))
FAVOURITE = (0.6, 0.25, 0.15)
OUTSIDER = (0.2, 0.3, 0.5)
OPEN = (0.45, 0.35, 0.2)
ROWS: tuple[tuple[tuple[float, float, float], str], ...] = (
    (FAVOURITE, "H"),
    (FAVOURITE, "H"),
    (FAVOURITE, "D"),
    (FAVOURITE, "H"),
    (OUTSIDER, "A"),
    (OUTSIDER, "D"),
    (OUTSIDER, "A"),
    (OUTSIDER, "H"),
    (OPEN, "D"),
    (OPEN, "H"),
    (OPEN, "D"),
    (OPEN, "A"),
)


def _replay(
    bets: Mapping[int, Bet] | None = None,
    closings: Mapping[int, Mapping[OddsKey, float]] | None = None,
) -> ReplayResult:
    """Harness'sız sonuç: maç sırası tahmin sırası değil, sonuçlar ters sırayla eklenir."""
    bets = bets or {}
    closings = closings or {}
    indices = [10 + 3 * position for position in range(len(ROWS))]
    predictions = tuple(
        Prediction(index, "test", probs, bets.get(position))
        for position, (index, (probs, _)) in enumerate(zip(indices, ROWS, strict=True))
    )
    outcomes = {
        index: Outcome(
            match_index=index,
            result=result,
            home_goals=SCORES[result][0],
            away_goals=SCORES[result][1],
            closing=MappingProxyType(dict(closings.get(position, AVG_CLOSE))),
        )
        for position, (index, (_, result)) in reversed(
            list(enumerate(zip(indices, ROWS, strict=True)))
        )
    }
    return ReplayResult(
        strategy="test",
        predictions=predictions,
        outcomes=MappingProxyType(outcomes),
        no_decision=0,
        no_prediction=0,
    )


def test_evaluate_scores_each_prediction_against_its_own_outcome() -> None:
    evaluation = evaluate(_replay(), method=MULTIPLICATIVE, resamples=500)

    probs = [probs for probs, _ in ROWS]
    outcomes = [RESULTS.index(result) for _, result in ROWS]
    losses = [-math.log(p[o]) for p, o in zip(probs, outcomes, strict=True)]
    assert (evaluation.strategy, evaluation.n) == ("test", 12)
    assert evaluation.log_loss == bootstrap_mean(per_match_log_loss(probs, outcomes), resamples=500)
    assert evaluation.log_loss.low <= sum(losses) / len(losses) <= evaluation.log_loss.high
    assert evaluation.brier == pytest.approx(brier(probs, outcomes))
    assert evaluation.rps == pytest.approx(rps(probs, outcomes))
    assert evaluation.calibration == calibration(probs, outcomes)
    assert (evaluation.clv, evaluation.bets) == (None, 0)


def test_clv_prices_the_bet_against_the_devigged_avg_closing_of_the_bet_outcome() -> None:
    closing = {**AVG_CLOSE, **quote("PS", CLOSING, (1.8, 3.9, 4.8))}

    evaluation = evaluate(
        _replay(bets={0: Bet("D", 3.6, "Avg")}, closings={0: closing}),
        method=MULTIPLICATIVE,
        resamples=500,
    )

    fair_draw = (1 / 3.4) / (1 / 2.0 + 1 / 3.4 + 1 / 4.2)
    assert evaluation.bets == 1
    assert evaluation.clv is not None
    assert evaluation.clv.estimate == pytest.approx(3.6 * fair_draw - 1)


def test_clv_follows_the_requested_devig_method() -> None:
    result = _replay(bets={0: Bet("D", 3.6, "Avg")})

    shin = evaluate(result, method=SHIN, resamples=500)
    multiplicative = evaluate(result, method=MULTIPLICATIVE, resamples=500)

    assert shin.clv is not None and multiplicative.clv is not None
    assert shin.clv.estimate == pytest.approx(3.6 * devig((2.0, 3.4, 4.2), SHIN)[1] - 1)
    assert shin.clv.estimate != pytest.approx(multiplicative.clv.estimate)


def test_bets_without_a_complete_avg_closing_stay_out_of_clv() -> None:
    no_draw = {key: price for key, price in AVG_CLOSE.items() if key.outcome != "D"}
    result = _replay(
        bets={0: Bet("H", 2.2, "Avg"), 1: Bet("H", 2.2, "Avg"), 2: Bet("A", 4.4, "Avg")},
        closings={1: {**no_draw, **quote("PS", CLOSING, (1.9, 3.5, 4.4))}, 2: {}},
    )

    evaluation = evaluate(result, method=MULTIPLICATIVE, resamples=500)

    fair_home = (1 / 2.0) / (1 / 2.0 + 1 / 3.4 + 1 / 4.2)
    assert (evaluation.n, evaluation.bets) == (12, 1)
    assert evaluation.clv is not None
    assert evaluation.clv.estimate == pytest.approx(2.2 * fair_home - 1)


@pytest.mark.parametrize(
    ("method", "bets"),
    [(SHIN, 0), (MULTIPLICATIVE, 1)],
    ids=["shin-refuses", "multiplicative-accepts"],
)
def test_closing_prices_the_method_refuses_stay_out_of_clv(method: str, bets: int) -> None:
    thin = quote("Avg", CLOSING, (2.5, 3.6, 3.6))  # Σ 1/o < 1: Shin için geçersiz

    evaluation = evaluate(
        _replay(bets={0: Bet("H", 2.6, "Avg")}, closings={0: thin}), method=method, resamples=500
    )

    assert evaluation.bets == bets
    assert (evaluation.clv is None) is (bets == 0)


def test_an_empty_replay_cannot_be_evaluated() -> None:
    empty = ReplayResult(
        strategy="test",
        predictions=(),
        outcomes=MappingProxyType({}),
        no_decision=0,
        no_prediction=0,
    )

    with pytest.raises(ValueError, match="tahmin yok"):
        evaluate(empty, method=MULTIPLICATIVE)


def test_evaluate_reads_a_placebo_replay_end_to_end() -> None:
    days = [date(2023, 8, 5) + timedelta(weeks=week) for week in range(9)]
    prices: Sequence[float] = (2.6, 3.3, 2.8)
    matches = tuple(
        hist_match(
            day=day,
            kickoff=datetime.combine(day, time(14), tzinfo=UTC),
            goals=SCORES[RESULTS[week % 3]],
            odds={
                **quote("Avg", PRE_CLOSING, prices),
                **({} if week == 4 else quote("Avg", CLOSING, prices)),
            },
            line=week + 1,
        )
        for week, day in enumerate(days)
    )

    result = replay(matches, Placebo(devig=partial(devig, method=MULTIPLICATIVE)))
    evaluation = evaluate(result, method=MULTIPLICATIVE, resamples=500)

    assert (evaluation.n, evaluation.bets) == (9, 8)
    assert evaluation.clv is not None
    assert evaluation.clv.estimate == pytest.approx(1 / sum(1 / price for price in prices) - 1)
