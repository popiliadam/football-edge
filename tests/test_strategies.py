"""Faz 2 taban stratejileri: kapanış öncesi piyasa, nokta-zamanlı Elo, placebo."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from types import MappingProxyType

import pytest

from football_edge.backtest.harness import (
    DecisionContext,
    Prediction,
    ResultRecord,
    Strategy,
    replay,
)
from football_edge.backtest.strategies import EloPointInTime, MarketPre, Placebo
from football_edge.elo import EloConfig, expected_home, updated
from football_edge.history.types import CLOSING, PRE_CLOSING, RESULTS, OddsKey
from tests.backtest_builders import hist_match, quote

CONFIG = EloConfig()
FLAT = EloConfig(home_advantage=0.0, goal_scaling=False)
AVG_PRE = quote("Avg", PRE_CLOSING, (2.6, 3.3, 2.8))


def _normalise(prices: Sequence[float]) -> tuple[float, ...]:
    """Yer tutucu vig temizleyici (çarpımsal); gerçeği market/devig.py'de."""
    inverse = [1.0 / price for price in prices]
    total = sum(inverse)
    return tuple(value / total for value in inverse)


def _refusing(prices: Sequence[float]) -> tuple[float, ...]:
    raise ValueError("geçersiz fiyat")


def _context(
    pre: Mapping[OddsKey, float] | None = None,
    *,
    index: int = 0,
    home: str = "Alfa",
    away: str = "Beta",
    league: str = "E0",
) -> DecisionContext:
    return DecisionContext(
        match_index=index,
        league=league,
        season="2324",
        date=date(2024, 8, 10),
        home=home,
        away=away,
        decision_at=datetime(2024, 8, 9, 11, tzinfo=UTC),
        pre_prices=MappingProxyType(dict(pre or {})),
    )


def _record(
    home: str, away: str, home_goals: int, away_goals: int, *, league: str = "E0"
) -> ResultRecord:
    return ResultRecord(
        league=league,
        date=date(2024, 8, 3),
        home=home,
        away=away,
        home_goals=home_goals,
        away_goals=away_goals,
        known_at=datetime(2024, 8, 3, 17, tzinfo=UTC),
    )


def _elo_probs(
    home_rating: float, away_rating: float, config: EloConfig, draw_rate: float
) -> tuple[float, float, float]:
    """Sözleşmedeki formülün testteki bağımsız yazımı."""
    expected = expected_home(home_rating, away_rating, config)
    home = min(max(expected - draw_rate / 2, 0.01), 0.98)
    away = min(max(1.0 - home - draw_rate, 0.01), 0.98)
    total = home + draw_rate + away
    return home / total, draw_rate / total, away / total


def _pick(strategy: Placebo, index: int) -> str:
    """`index`. maç: adı sıradan gelen ayrı bir maç (tohum kimlikten, sıradan değil — 14l)."""
    prediction = strategy.predict(_context(AVG_PRE, index=index, home=f"Ev {index}"))
    assert prediction is not None and prediction.bet is not None
    return prediction.bet.outcome


def test_market_pre_devigs_the_pre_closing_prices_of_its_book_in_h_d_a_order() -> None:
    received: list[tuple[float, ...]] = []

    def recording(prices: Sequence[float]) -> tuple[float, ...]:
        received.append(tuple(prices))
        return _normalise(prices)

    pre = {
        **quote("Avg", PRE_CLOSING, (1.9, 3.5, 4.2)),
        **quote("Max", PRE_CLOSING, (2.1, 3.8, 4.6)),
    }

    prediction = MarketPre(devig=recording).predict(_context(pre))

    assert received == [(1.9, 3.5, 4.2)]
    assert prediction is not None
    assert prediction.probs == pytest.approx(_normalise((1.9, 3.5, 4.2)))
    assert (prediction.match_index, prediction.strategy, prediction.bet) == (0, "market_pre", None)


def test_market_pre_reads_the_configured_book() -> None:
    pre = {
        **quote("Avg", PRE_CLOSING, (1.9, 3.5, 4.2)),
        **quote("Max", PRE_CLOSING, (2.1, 3.8, 4.6)),
    }

    prediction = MarketPre(devig=_normalise, book="Max").predict(_context(pre))

    assert prediction is not None
    assert prediction.probs == pytest.approx(_normalise((2.1, 3.8, 4.6)))


@pytest.mark.leakage
def test_market_pre_never_completes_a_pre_closing_quote_with_a_closing_price() -> None:
    avg_pre = quote("Avg", PRE_CLOSING, (1.9, 3.5, 4.2))
    pre = {
        **{key: price for key, price in avg_pre.items() if key.outcome != "D"},
        **quote("Avg", CLOSING, (1.8, 3.6, 4.4)),
    }

    assert MarketPre(devig=_normalise).predict(_context(pre)) is None


def test_market_pre_predicts_nothing_when_devig_refuses_the_prices() -> None:
    assert MarketPre(devig=_refusing).predict(_context(AVG_PRE)) is None


def test_market_pre_is_stateless() -> None:
    strategy = MarketPre(devig=_normalise)

    assert strategy.observe(_record("Alfa", "Beta", 1, 0)) == strategy


def test_elo_starts_teams_it_has_never_seen_at_the_initial_rating() -> None:
    prediction = EloPointInTime(config=FLAT).predict(_context())

    assert prediction.probs == pytest.approx((0.37, 0.26, 0.37))
    assert (prediction.strategy, prediction.bet) == ("elo", None)


def test_elo_observe_returns_a_new_value_and_leaves_the_old_one_untouched() -> None:
    before = EloPointInTime(config=FLAT)

    after = before.observe(_record("Alfa", "Beta", 2, 0))

    home, away = updated(1500.0, 1500.0, 2, 0, FLAT)
    assert dict(before.ratings) == {}
    assert dict(after.ratings) == pytest.approx({("E0", "Alfa"): home, ("E0", "Beta"): away})
    assert isinstance(after.ratings, MappingProxyType)


def test_elo_probabilities_follow_the_expectation_and_the_draw_rate() -> None:
    strategy = EloPointInTime(
        ratings=MappingProxyType({("E0", "Alfa"): 1600.0, ("E0", "Beta"): 1450.0})
    )

    prediction = strategy.predict(_context())

    assert prediction.probs == pytest.approx(_elo_probs(1600.0, 1450.0, CONFIG, 0.26))
    assert sum(prediction.probs) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("home_rating", "away_rating", "draw_rate", "expected"),
    [
        (2600.0, 1000.0, 0.26, _elo_probs(2600.0, 1000.0, FLAT, 0.26)),  # deplasman tabanda
        (1000.0, 2600.0, 0.26, (0.01, 0.26, 0.73)),  # ev tabanda
        (2600.0, 1000.0, 0.0, (0.98, 0.0, 0.02)),  # ev tavanda
    ],
    ids=["away-floor", "home-floor", "home-ceiling"],
)
def test_elo_clamps_extreme_expectations_and_renormalises(
    home_rating: float, away_rating: float, draw_rate: float, expected: tuple[float, ...]
) -> None:
    strategy = EloPointInTime(
        config=FLAT,
        draw_rate=draw_rate,
        ratings=MappingProxyType({("E0", "Alfa"): home_rating, ("E0", "Beta"): away_rating}),
    )

    probs = strategy.predict(_context()).probs

    assert probs == pytest.approx(expected)
    assert sum(probs) == pytest.approx(1.0)


def test_elo_keeps_same_named_teams_of_different_groups_apart() -> None:
    """R94: ham takım adı ülkeler arasında kimlik değildir — sessiz birleştirme hatası olurdu."""
    groups = MappingProxyType({"E0": "England", "BRA": "Brazil"})

    after = EloPointInTime(config=FLAT, groups=groups).observe(
        _record("Alfa", "Beta", 2, 0, league="E0")
    )

    assert set(after.ratings) == {("England", "Alfa"), ("England", "Beta")}
    elsewhere = after.predict(_context(home="Alfa", away="Beta", league="BRA"))
    assert elsewhere.probs == pytest.approx((0.37, 0.26, 0.37))


def test_elo_carries_a_rating_across_leagues_of_the_same_group() -> None:
    """Terfi eden takım reytingini taşır: E1'de oynadığı maç E0'daki ilk kararını besler."""
    groups = MappingProxyType({"E0": "England", "E1": "England"})

    after = EloPointInTime(config=FLAT, groups=groups).observe(
        _record("Alfa", "Beta", 2, 0, league="E1")
    )

    promoted, _ = updated(1500.0, 1500.0, 2, 0, FLAT)
    prediction = after.predict(_context(home="Alfa", away="Gama", league="E0"))
    assert prediction.probs == pytest.approx(_elo_probs(promoted, 1500.0, FLAT, 0.26))


def test_elo_groups_an_unmapped_league_by_its_own_code() -> None:
    after = EloPointInTime(config=FLAT, groups=MappingProxyType({"E0": "England"})).observe(
        _record("Alfa", "Beta", 2, 0, league="XX")
    )

    assert set(after.ratings) == {("XX", "Alfa"), ("XX", "Beta")}
    mapped = after.predict(_context(home="Alfa", away="Beta", league="E0"))
    assert mapped.probs == pytest.approx((0.37, 0.26, 0.37))


@dataclass(frozen=True)
class _RatingSpy:
    """Her kararda sarmaladığı Elo'nun reytinglerini kaydeder."""

    inner: EloPointInTime
    seen: dict[int, dict[tuple[str, str], float]]

    @property
    def name(self) -> str:
        return self.inner.name

    def observe(self, result: ResultRecord) -> _RatingSpy:
        return _RatingSpy(self.inner.observe(result), self.seen)

    def predict(self, context: DecisionContext) -> Prediction | None:
        self.seen[context.match_index] = dict(self.inner.ratings)
        return self.inner.predict(context)


@pytest.mark.leakage
def test_elo_ratings_at_a_decision_come_only_from_results_known_before_it() -> None:
    matches = (
        hist_match(
            day=date(2024, 8, 3),
            kickoff=datetime(2024, 8, 3, 14, tzinfo=UTC),
            home="Alfa",
            away="Beta",
            goals=(2, 0),
        ),
        # cuma 09:00 BST: kararı yok; sonucu tam 2. maçın karar anında (cuma 12:00 BST) bilinir
        hist_match(
            day=date(2024, 8, 9),
            kickoff=datetime(2024, 8, 9, 8, tzinfo=UTC),
            home="Gama",
            away="Delta",
            goals=(3, 1),
            line=2,
        ),
        hist_match(
            day=date(2024, 8, 10),
            kickoff=datetime(2024, 8, 10, 14, tzinfo=UTC),
            home="Beta",
            away="Gama",
            goals=(1, 1),
            line=3,
        ),
        hist_match(
            day=date(2024, 8, 13),
            kickoff=datetime(2024, 8, 13, 18, 45, tzinfo=UTC),
            home="Alfa",
            away="Delta",
            goals=(0, 1),
            line=4,
        ),
    )
    seen: dict[int, dict[tuple[str, str], float]] = {}

    result = replay(matches, _RatingSpy(EloPointInTime(config=CONFIG), seen))

    alfa, beta = updated(1500.0, 1500.0, 2, 0, CONFIG)
    gama, delta = updated(1500.0, 1500.0, 3, 1, CONFIG)
    beta_after, gama_after = updated(beta, gama, 1, 1, CONFIG)
    assert set(seen) == {0, 2, 3}
    assert seen[0] == {}
    assert seen[2] == pytest.approx({("E0", "Alfa"): alfa, ("E0", "Beta"): beta})
    assert seen[3] == pytest.approx(
        {
            ("E0", "Alfa"): alfa,
            ("E0", "Beta"): beta_after,
            ("E0", "Gama"): gama_after,
            ("E0", "Delta"): delta,
        }
    )
    probs = {prediction.match_index: prediction.probs for prediction in result.predictions}
    assert probs[2] == pytest.approx(_elo_probs(beta, 1500.0, CONFIG, 0.26))


def _sha_pick(seed: int, league: str, day: date, home: str, away: str) -> str:
    """Sözleşmedeki tohumun testteki bağımsız yazımı (14l)."""
    digest = hashlib.sha256(f"{seed}|{league}|{day.isoformat()}|{home}|{away}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big")).choice(RESULTS)


def test_placebo_bets_its_seeded_pick_at_the_books_pre_closing_price() -> None:
    strategy = Placebo(devig=_normalise, seed=7)

    prediction = strategy.predict(_context(AVG_PRE, index=3))

    pick = _sha_pick(7, "E0", date(2024, 8, 10), "Alfa", "Beta")
    assert prediction is not None and prediction.bet is not None
    assert prediction.bet.outcome == pick
    assert prediction.bet.price == dict(zip(RESULTS, (2.6, 3.3, 2.8), strict=True))[pick]
    assert prediction.bet.book == "Avg"
    assert prediction.probs == pytest.approx(_normalise((2.6, 3.3, 2.8)))
    assert prediction.strategy == "placebo"
    assert strategy.predict(_context(AVG_PRE, index=3)) == prediction


def test_placebo_picks_follow_the_match_identity_seed_over_a_grid() -> None:
    """Tek örnek yanlış bir tohum biçimini (ör. ev adı atlanmış) şans eseri geçirebilir."""
    grid = [(seed, index) for seed in (1, 7, 20260922) for index in range(6)]

    picks = [_pick(Placebo(devig=_normalise, seed=seed), index) for seed, index in grid]

    assert picks == [
        _sha_pick(seed, "E0", date(2024, 8, 10), f"Ev {index}", "Beta") for seed, index in grid
    ]


def test_placebo_pick_ignores_the_replay_position() -> None:
    """14l: aynı maç, oynatmadaki sırası değişince aynı sonucu seçer."""
    strategy = Placebo(devig=_normalise)

    picks = {strategy.predict(_context(AVG_PRE, index=index)) for index in range(20)}

    assert (
        len({prediction.bet.outcome for prediction in picks if prediction and prediction.bet}) == 1
    )


def test_placebo_picks_vary_across_matches() -> None:
    strategy = Placebo(devig=_normalise)

    assert {_pick(strategy, index) for index in range(60)} == set(RESULTS)


def test_placebo_picks_depend_on_the_seed() -> None:
    assert {_pick(Placebo(devig=_normalise, seed=seed), 0) for seed in range(30)} == set(RESULTS)


def test_placebo_bets_at_the_configured_books_price() -> None:
    pre = {**AVG_PRE, **quote("Max", PRE_CLOSING, (2.8, 3.6, 3.1))}

    prediction = Placebo(devig=_normalise, book="Max").predict(_context(pre, index=5))

    assert prediction is not None and prediction.bet is not None
    assert prediction.bet.book == "Max"
    maximum = dict(zip(RESULTS, (2.8, 3.6, 3.1), strict=True))
    assert prediction.bet.price == maximum[prediction.bet.outcome]


def test_placebo_predicts_nothing_without_a_complete_pre_closing_quote() -> None:
    pre = {**quote("Avg", CLOSING, (2.6, 3.3, 2.8)), **quote("Max", PRE_CLOSING, (2.7, 3.4, 2.9))}

    assert Placebo(devig=_normalise).predict(_context(pre)) is None


def test_placebo_predicts_nothing_when_devig_refuses_the_prices() -> None:
    assert Placebo(devig=_refusing).predict(_context(AVG_PRE)) is None


@pytest.mark.parametrize(
    "strategy",
    [MarketPre(devig=_normalise), EloPointInTime(), Placebo(devig=_normalise)],
    ids=["market_pre", "elo", "placebo"],
)
def test_every_strategy_replays_through_the_harness(strategy: Strategy) -> None:
    days = [date(2024, 8, 3) + timedelta(weeks=week) for week in range(3)]
    matches = tuple(
        hist_match(
            day=day,
            kickoff=datetime.combine(day, time(14), tzinfo=UTC),
            odds=AVG_PRE,
            line=index + 1,
        )
        for index, day in enumerate(days)
    )

    result = replay(matches, strategy)

    assert result.strategy == strategy.name
    assert len(result.predictions) == 3
    assert all(sum(prediction.probs) == pytest.approx(1.0) for prediction in result.predictions)
