"""Fit edilebilir Elo (Faz 3 tasarımı §6.1). Bağlamlar yalnız `harness._context` ve `replay` ile
kurulur: `DecisionContext`in alanları dalga 1'in başka bir görevinde değişebilir."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from types import MappingProxyType

import numpy as np
import pytest

from football_edge.backtest import harness
from football_edge.backtest.harness import DecisionContext, ResultRecord, replay
from football_edge.elo import EloConfig, expected_home, updated
from football_edge.model.elo_model import (
    LINEAR_MARGIN,
    LOG_MARGIN,
    NO_MARGIN,
    ORDERED,
    EloModel,
    EloModelConfig,
    elo_probs,
    expectation,
    fit_draw,
    fit_ordered,
    fit_outcome_params,
    margin_multiplier,
    ordered_probs,
)
from tests.backtest_builders import hist_match

DECIDED = datetime(2024, 8, 9, 11, tzinfo=UTC)


def _result(
    home: str, away: str, goals: tuple[int, int], day: date = date(2024, 8, 3), league: str = "E0"
) -> ResultRecord:
    return ResultRecord(
        league=league,
        date=day,
        home=home,
        away=away,
        home_goals=goals[0],
        away_goals=goals[1],
        known_at=datetime.combine(day, time(17), tzinfo=UTC),
    )


def _context(
    home: str = "Alfa", away: str = "Beta", day: date = date(2024, 8, 10), league: str = "E0"
) -> DecisionContext:
    match = hist_match(
        day=day,
        kickoff=datetime.combine(day, time(14), tzinfo=UTC),
        home=home,
        away=away,
        league=league,
    )
    return harness._context(0, match, DECIDED)


def test_with_scaffold_settings_the_update_equals_the_phase_one_engine() -> None:
    config = EloModelConfig(k=20.0, home_advantage=65.0, margin=LINEAR_MARGIN)

    model = EloModel(config=config).observe(_result("Alfa", "Beta", (3, 0)))

    home, away = updated(1500.0, 1500.0, 3, 0, EloConfig(k=20.0, home_advantage=65.0))
    assert model.ratings[("E0", "Alfa")] == pytest.approx(home)
    assert model.ratings[("E0", "Beta")] == pytest.approx(away)


def test_margin_forms() -> None:
    assert margin_multiplier(1, 0, LINEAR_MARGIN) == 1.0
    assert margin_multiplier(4, 0, NO_MARGIN) == 1.0
    assert margin_multiplier(4, 0, LINEAR_MARGIN) == 2.5
    assert margin_multiplier(0, 4, LOG_MARGIN) == pytest.approx(1.0 + math.log(4))


@pytest.mark.parametrize("expected", [0.0, 0.2, 0.5, 0.83, 1.0])
def test_probabilities_are_valid_and_the_draw_peaks_at_even(expected: float) -> None:
    home, draw, away = elo_probs(expected, 0.5)

    assert min(home, draw, away) >= 0.0
    assert home + draw + away == pytest.approx(1.0)
    assert expectation((home, draw, away)) == pytest.approx(expected)
    assert draw <= elo_probs(0.5, 0.5)[1]


def test_the_prediction_uses_the_home_advantage_and_the_draw_share() -> None:
    config = EloModelConfig(home_advantage=80.0, draw=0.3)
    model = EloModel(
        config=config, ratings=MappingProxyType({("E0", "Alfa"): 1600.0, ("E0", "Beta"): 1550.0})
    )

    prediction = model.predict(_context())

    expected = expected_home(1600.0, 1550.0, EloConfig(home_advantage=80.0))
    assert prediction.probs == pytest.approx(elo_probs(expected, 0.3))
    assert prediction.strategy == "elo_fit"


def test_invalid_settings_are_refused() -> None:
    with pytest.raises(ValueError, match="marj"):
        EloModelConfig(margin="square")
    with pytest.raises(ValueError, match="beraberlik"):
        EloModelConfig(draw=0.6)
    with pytest.raises(ValueError, match="dönüş"):
        EloModelConfig(regress=1.5)


def test_a_newcomer_starts_below_the_group_mean() -> None:
    ratings = MappingProxyType(
        {("E0", "Alfa"): 1600.0, ("E0", "Beta"): 1500.0, ("SP1", "Gama"): 2000.0}
    )
    model = EloModel(config=EloModelConfig(newcomer_offset=100.0, draw=0.0), ratings=ratings)

    prediction = model.predict(_context(home="Yeni", away="Beta"))

    expected = expected_home(1450.0, 1500.0, EloConfig())
    assert prediction.probs == pytest.approx(elo_probs(expected, 0.0))


def test_the_first_team_of_a_group_starts_at_the_initial_rating() -> None:
    model = EloModel(config=EloModelConfig(newcomer_offset=100.0))

    assert model._current(("E0", "Alfa"), date(2024, 8, 3)) == pytest.approx(1400.0)


def test_a_long_gap_regresses_the_rating_toward_the_group_mean() -> None:
    ratings = MappingProxyType({("E0", "Alfa"): 1700.0, ("E0", "Beta"): 1500.0})
    seen = MappingProxyType({("E0", "Alfa"): date(2024, 5, 20), ("E0", "Beta"): date(2024, 8, 1)})
    model = EloModel(config=EloModelConfig(regress=0.25), ratings=ratings, last_seen=seen)

    # grup ortalaması 1600; dönüş payı 0.25 → 1600 + 0.75 · 100
    assert model._current(("E0", "Alfa"), date(2024, 8, 10)) == pytest.approx(1675.0)
    assert model._current(("E0", "Beta"), date(2024, 8, 10)) == pytest.approx(1500.0)


def test_observe_stores_the_regressed_rating_before_the_update() -> None:
    ratings = MappingProxyType({("E0", "Alfa"): 1700.0, ("E0", "Beta"): 1500.0})
    seen = MappingProxyType({("E0", "Alfa"): date(2024, 5, 20), ("E0", "Beta"): date(2024, 5, 20)})
    config = EloModelConfig(regress=0.25, k=0.0)

    model = EloModel(config=config, ratings=ratings, last_seen=seen).observe(
        _result("Alfa", "Beta", (1, 1), date(2024, 8, 10))
    )

    assert model.ratings[("E0", "Alfa")] == pytest.approx(1675.0)
    assert model.last_seen[("E0", "Alfa")] == date(2024, 8, 10)


def test_observe_returns_a_new_value_and_leaves_the_old_one_untouched() -> None:
    before = EloModel()

    after = before.observe(_result("Alfa", "Beta", (2, 0)))

    assert dict(before.ratings) == {} and after is not before
    assert isinstance(after.ratings, MappingProxyType)


def test_groups_keep_same_named_teams_apart_and_join_leagues_of_a_country() -> None:
    groups = MappingProxyType({"E0": "England", "E1": "England", "SP1": "Spain"})
    model = EloModel(groups=groups).observe(_result("Alfa", "Beta", (2, 0), league="E1"))

    assert ("England", "Alfa") in model.ratings
    assert (
        model._current(("Spain", "Alfa"), date(2024, 8, 10)) != model.ratings[("England", "Alfa")]
    )


@pytest.mark.leakage
def test_ratings_at_a_decision_come_only_from_results_known_before_it() -> None:
    """Cuma kararı cumartesi sonucunu görmez; bir sonraki haftanın kararı görür."""
    days = [date(2024, 8, 3) + timedelta(weeks=week) for week in range(2)]
    matches = tuple(
        hist_match(
            day=day,
            kickoff=datetime.combine(day, time(14), tzinfo=UTC),
            goals=(4, 0),
            line=index + 1,
        )
        for index, day in enumerate(days)
    )

    result = replay(matches, EloModel(config=EloModelConfig(draw=0.0)))

    first, second = (prediction.probs for prediction in result.predictions)
    assert first == pytest.approx(elo_probs(expected_home(1500.0, 1500.0, EloConfig()), 0.0))
    assert second[0] > first[0]


def test_fit_draw_recovers_the_draw_share() -> None:
    rng = np.random.default_rng(11)
    expectations = [float(value) for value in rng.uniform(0.2, 0.8, 6000)]
    outcomes = [int(rng.choice(3, p=elo_probs(e, 0.3))) for e in expectations]

    assert fit_draw(expectations, outcomes) == pytest.approx(0.3, abs=0.03)


def test_fit_draw_refuses_mismatched_input() -> None:
    with pytest.raises(ValueError):
        fit_draw([0.5], [])


# ── Sıralı lojit (R142): quadratic'in rakibi, seçimi S yapar ─────────────────────────────


@pytest.mark.parametrize("expected", [0.0, 0.05, 0.3, 0.5, 0.71, 0.97, 1.0])
def test_ordered_probabilities_are_valid_distributions(expected: float) -> None:
    home, draw, away = ordered_probs(expected, 1.3, 0.6)

    assert min(home, draw, away) > 0.0
    assert home + draw + away == pytest.approx(1.0)


def test_the_ordered_draw_shrinks_as_the_rating_gap_grows_either_way() -> None:
    """P(D) E = 0.5 iken en büyük; |ΔElo| büyüdükçe tekdüze azalır, iki yönde simetrik."""
    upward = [ordered_probs(e, 1.2, 0.5)[1] for e in (0.5, 0.6, 0.7, 0.8, 0.9, 0.99)]
    downward = [ordered_probs(1.0 - e, 1.2, 0.5)[1] for e in (0.5, 0.6, 0.7, 0.8, 0.9, 0.99)]

    assert all(a > b for a, b in zip(upward, upward[1:], strict=False))
    assert upward == pytest.approx(downward)
    assert ordered_probs(0.5, 1.2, 0.5)[1] == pytest.approx(math.tanh(0.25))


def test_the_ordered_home_probability_rises_with_the_expectation() -> None:
    homes = [ordered_probs(e, 1.0, 0.5)[0] for e in (0.2, 0.4, 0.6, 0.8)]

    assert homes == sorted(homes) and homes[0] < homes[-1]


def test_the_prediction_follows_the_configured_draw_form() -> None:
    config = EloModelConfig(draw_form=ORDERED, ordered_scale=1.4, ordered_cut=0.7)
    model = EloModel(
        config=config, ratings=MappingProxyType({("E0", "Alfa"): 1600.0, ("E0", "Beta"): 1500.0})
    )

    prediction = model.predict(_context())

    expected = expected_home(1600.0, 1500.0, EloConfig())
    assert prediction.probs == pytest.approx(ordered_probs(expected, 1.4, 0.7))
    assert prediction.probs != pytest.approx(elo_probs(expected, config.draw))


def test_fit_ordered_recovers_the_scale_and_the_cut() -> None:
    rng = np.random.default_rng(12)
    expectations = [float(value) for value in rng.uniform(0.15, 0.85, 8000)]
    outcomes = [int(rng.choice(3, p=ordered_probs(e, 1.3, 0.6))) for e in expectations]

    scale, cut = fit_ordered(expectations, outcomes)

    assert scale == pytest.approx(1.3, abs=0.12) and cut == pytest.approx(0.6, abs=0.05)


def test_fit_outcome_params_fits_only_the_selected_form() -> None:
    rng = np.random.default_rng(13)
    expectations = [float(value) for value in rng.uniform(0.2, 0.8, 3000)]
    outcomes = [int(rng.choice(3, p=elo_probs(e, 0.3))) for e in expectations]
    base = EloModelConfig()

    quadratic = fit_outcome_params(base, expectations, outcomes)
    ordered = fit_outcome_params(replace(base, draw_form=ORDERED), expectations, outcomes)

    assert (
        quadratic.draw == pytest.approx(0.3, abs=0.04) and quadratic.ordered_cut == base.ordered_cut
    )
    assert ordered.draw == base.draw and ordered.ordered_cut != base.ordered_cut


def test_an_unknown_draw_form_or_non_positive_ordered_parameters_are_refused() -> None:
    with pytest.raises(ValueError, match="beraberlik biçimi"):
        EloModelConfig(draw_form="probit")
    with pytest.raises(ValueError, match="pozitif"):
        EloModelConfig(ordered_cut=0.0)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("k", -1.0, "K sonlu"),
        ("k", float("nan"), "K sonlu"),
        ("home_advantage", float("inf"), "ev avantajı"),
        ("initial", float("nan"), "başlangıç"),
        ("initial", 0.0, "başlangıç"),
        ("season_gap_days", 0, "sezon arası"),
        ("season_gap_days", 60.5, "sezon arası"),
        ("season_gap_days", True, "sezon arası"),
    ],
)
def test_an_invalid_elo_config_is_refused_by_name(field: str, value: object, message: str) -> None:
    """NaN K ya da sıfır başlangıç sessizce NaN reyting üretirdi (DEFERRED 16k)."""
    with pytest.raises(ValueError, match=message):
        EloModelConfig(**{field: value})  # type: ignore[arg-type]


def test_the_sealed_faz3_elo_config_still_loads() -> None:
    from football_edge.backtest.model_config import load_model_config

    config = load_model_config(Path("config/model_faz3.yaml"))
    assert config.elo.k == 10.0
