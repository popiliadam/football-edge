from __future__ import annotations

import dataclasses
import datetime as dt
from types import MappingProxyType

import pytest

from football_edge.history.types import (
    CLOSING,
    H2H,
    MARKET_OUTCOMES,
    PRE_CLOSING,
    RESULTS,
    TOTALS_25,
    HistMatch,
    OddsKey,
)


def _match(odds: dict[OddsKey, float]) -> HistMatch:
    return HistMatch(
        league="E0",
        season="2526",
        date=dt.date(2025, 8, 16),
        kickoff=dt.datetime(2025, 8, 16, 14, 0, tzinfo=dt.UTC),
        home="Ev",
        away="Deplasman",
        home_goals=2,
        away_goals=1,
        result="H",
        odds=MappingProxyType(odds),
        stats=MappingProxyType({}),
        source_line=1,
    )


def test_outcome_order_is_fixed_per_market() -> None:
    assert MARKET_OUTCOMES[H2H] == ("H", "D", "A")
    assert MARKET_OUTCOMES[TOTALS_25] == ("over", "under")
    assert RESULTS == ("H", "D", "A")


def test_prices_follow_market_outcome_order_not_insertion_order() -> None:
    odds = {
        OddsKey("Avg", H2H, "A", PRE_CLOSING): 4.0,
        OddsKey("Avg", H2H, "H", PRE_CLOSING): 2.0,
        OddsKey("Avg", H2H, "D", PRE_CLOSING): 3.5,
    }
    assert _match(odds).prices("Avg", H2H, PRE_CLOSING) == (2.0, 3.5, 4.0)


def test_prices_is_none_when_one_outcome_is_missing() -> None:
    odds = {
        OddsKey("Avg", H2H, "H", CLOSING): 2.0,
        OddsKey("Avg", H2H, "D", CLOSING): 3.5,
    }
    assert _match(odds).prices("Avg", H2H, CLOSING) is None


def test_prices_does_not_mix_phases() -> None:
    odds = {OddsKey("Avg", H2H, outcome, PRE_CLOSING): 3.0 for outcome in RESULTS}
    assert _match(odds).prices("Avg", H2H, CLOSING) is None


def test_totals_prices_are_over_then_under() -> None:
    odds = {
        OddsKey("PS", TOTALS_25, "under", CLOSING): 1.9,
        OddsKey("PS", TOTALS_25, "over", CLOSING): 2.0,
    }
    assert _match(odds).prices("PS", TOTALS_25, CLOSING) == (2.0, 1.9)


def test_odds_keys_sort_deterministically() -> None:
    keys = [OddsKey("PS", H2H, "H", CLOSING), OddsKey("Avg", H2H, "H", PRE_CLOSING)]
    assert sorted(keys)[0].book == "Avg"


def test_match_is_immutable() -> None:
    match = _match({})
    with pytest.raises(dataclasses.FrozenInstanceError):
        match.home = "başka"  # type: ignore[misc]


def test_market_outcomes_cannot_be_modified() -> None:
    with pytest.raises(TypeError):
        MARKET_OUTCOMES["yeni"] = ("x",)  # type: ignore[index]
