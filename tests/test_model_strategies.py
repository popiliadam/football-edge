"""Dixon-Coles stratejisi (Faz 3 tasarımı §6.2): memo, aktiflik, Ü/A ve gelecek-fit kanaryası."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from football_edge.backtest import harness
from football_edge.backtest.events import RESULT, Event, build_events
from football_edge.backtest.harness import ResultRecord, replay
from football_edge.history.types import TOTALS_25, HistMatch
from football_edge.model import strategies as model_strategies
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModel
from football_edge.model.strategies import DixonColesStrategy, fit_day
from tests.model_builders import main_history

HISTORY = main_history(2021, 2023)
CONFIG = DCConfig(xi=0.002, ridge=0.01, min_matches=40)
ACTIVE = date(2022, 7, 1)


def _probs(matches: Sequence[HistMatch], strategy: object) -> dict[int, tuple[float, ...]]:
    result = replay(matches, strategy)  # type: ignore[arg-type]
    return {prediction.match_index: prediction.probs for prediction in result.predictions}


def test_fit_day_steps_back_to_the_cadence_calendar() -> None:
    friday = date(2024, 8, 9)
    assert fit_day(friday, 1) == friday
    assert fit_day(friday, 7) == date(2024, 8, 5)  # pazartesi
    assert fit_day(date(2024, 8, 5), 7) == date(2024, 8, 5)


def test_nothing_is_predicted_before_the_active_day() -> None:
    probs = _probs(HISTORY, DixonColesStrategy(config=CONFIG, active_from=ACTIVE))

    assert probs
    assert all(HISTORY[index].date >= ACTIVE for index in probs)


def test_predictions_are_distributions_that_favour_the_stronger_side() -> None:
    probs = _probs(HISTORY, DixonColesStrategy(config=CONFIG, active_from=ACTIVE))

    for index, (home, draw, away) in probs.items():
        assert home + draw + away == pytest.approx(1.0)
        match = HISTORY[index]
        if (match.home, match.away) == ("Alfa", "Teta"):
            assert home > away


def test_totals_market_returns_over_under_and_a_zero_third_slot() -> None:
    probs = _probs(HISTORY, DixonColesStrategy(config=CONFIG, active_from=ACTIVE, market=TOTALS_25))

    assert probs
    for over, under, third in probs.values():
        assert over + under == pytest.approx(1.0) and third == 0.0


def test_the_fit_runs_once_per_group_and_fit_day(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[date] = []
    real = model_strategies.fit

    def counting(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        calls.append(kwargs["at"])  # type: ignore[arg-type]
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(model_strategies, "fit", counting)
    strategy = DixonColesStrategy(config=CONFIG, active_from=ACTIVE)
    totals = DixonColesStrategy(
        config=CONFIG, active_from=ACTIVE, market=TOTALS_25, memo=strategy.memo
    )

    _probs(HISTORY, strategy)
    _probs(HISTORY, totals)

    assert len(calls) == len(set(calls)) > 0


def test_invalid_settings_are_refused() -> None:
    with pytest.raises(ValueError, match="market"):
        DixonColesStrategy(market="ah")
    with pytest.raises(ValueError, match="cadence"):
        DixonColesStrategy(cadence_days=0)


def test_observe_keeps_old_values_intact_and_chunks_history() -> None:
    first = DixonColesStrategy()
    record = ResultRecord(
        "E0", date(2022, 8, 6), "Alfa", "Beta", 1, 0, datetime(2022, 8, 6, 17, tzinfo=UTC)
    )
    current = first
    for _ in range(model_strategies.CHUNK + 1):
        current = current.observe(record)

    assert first.history == {}
    assert [len(chunk) for chunk in current.history["E0"]] == [model_strategies.CHUNK, 1]


@pytest.mark.leakage
def test_leaked_future_results_do_not_reach_the_dixon_coles_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G2: sonuçları üç gün ERKEN açan bozuk harness'ta Elo'nun tahmini değişir (kanarya canlı);
    Dixon-Coles'unki değişmez, çünkü fit yalnız fit gününden önce oynanmış maçları okur."""
    dc = DixonColesStrategy(config=CONFIG, active_from=ACTIVE)
    honest_dc, honest_elo = _probs(HISTORY, dc), _probs(HISTORY, EloModel())

    def leaking(matches: Sequence[HistMatch]) -> tuple[Event, ...]:
        events = build_events(matches)
        return tuple(
            sorted(
                replace(event, at=event.at - timedelta(days=3)) if event.kind == RESULT else event
                for event in events
            )
        )

    monkeypatch.setattr(harness, "build_events", leaking)
    leaked_dc = _probs(HISTORY, DixonColesStrategy(config=CONFIG, active_from=ACTIVE))
    leaked_elo = _probs(HISTORY, EloModel())

    assert leaked_elo != honest_elo
    assert leaked_dc == pytest.approx(honest_dc)
