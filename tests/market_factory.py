"""Piyasa testlerinin SENTETİK `HistMatch` kurucusu — gerçek maç, takım ya da oran satırı değil.

Fiyatlar `{(kitap, market, evre): (fiyatlar…)}` biçiminde verilir; sıra MARKET_OUTCOMES'unkidir.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import date, datetime
from types import MappingProxyType

from football_edge.history.types import MARKET_OUTCOMES, HistMatch, OddsKey

Prices = Mapping[tuple[str, str, str], tuple[float, ...]]


def odds_from(prices: Prices) -> MappingProxyType[OddsKey, float]:
    table = {
        OddsKey(book=book, market=market, outcome=outcome, phase=phase): value
        for (book, market, phase), values in prices.items()
        for outcome, value in zip(MARKET_OUTCOMES[market], values, strict=True)
    }
    return MappingProxyType(table)


def result_of(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "H"
    return "A" if home_goals < away_goals else "D"


def hist_match(
    *,
    league: str = "M1",
    season: str = "2324",
    day: date = date(2024, 1, 6),
    kickoff: datetime | None = None,
    home: str = "Alpha Town",
    away: str = "Beta City",
    goals: tuple[int, int] = (1, 0),
    prices: Prices | None = None,
    line: int = 1,
) -> HistMatch:
    home_goals, away_goals = goals
    return HistMatch(
        league=league,
        season=season,
        date=day,
        kickoff=kickoff,
        home=home,
        away=away,
        home_goals=home_goals,
        away_goals=away_goals,
        result=result_of(home_goals, away_goals),
        odds=odds_from(prices or {}),
        stats=MappingProxyType({}),
        source_line=line,
    )


def with_prices(match: HistMatch, prices: Prices) -> HistMatch:
    """Aynı maç, eklenmiş (ya da değiştirilmiş) fiyatlarla — yeni değer; girdi değişmez."""
    merged = {**match.odds, **odds_from(prices)}
    return replace(match, odds=MappingProxyType(merged))
