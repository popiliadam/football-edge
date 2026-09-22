"""Backtest testlerinin SENTETİK maç kurucuları.

Takım adları uydurma, fiyatlar elle seçilmiş: gerçek bir maç, takım ya da oran satırı yok
(spec §3.2/4). Yalnız anahtar biçimi (`OddsKey`) football-data'nın sütun düzenini izler.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from types import MappingProxyType

from football_edge.history.types import H2H, MARKET_OUTCOMES, HistMatch, OddsKey


def quote(
    book: str, phase: str, values: Sequence[float], *, market: str = H2H
) -> dict[OddsKey, float]:
    """Bir kitabın bir evredeki fiyatları, `MARKET_OUTCOMES[market]` sırasıyla."""
    outcomes = MARKET_OUTCOMES[market]
    return {
        OddsKey(book=book, market=market, outcome=outcome, phase=phase): value
        for outcome, value in zip(outcomes, values, strict=True)
    }


def hist_match(
    *,
    day: date,
    kickoff: datetime | None = None,
    league: str = "E0",
    season: str = "2324",
    home: str = "Alfa",
    away: str = "Beta",
    goals: tuple[int, int] = (1, 0),
    odds: Mapping[OddsKey, float] | None = None,
    line: int = 1,
) -> HistMatch:
    home_goals, away_goals = goals
    result = "H" if home_goals > away_goals else "A" if home_goals < away_goals else "D"
    return HistMatch(
        league=league,
        season=season,
        date=day,
        kickoff=kickoff,
        home=home,
        away=away,
        home_goals=home_goals,
        away_goals=away_goals,
        result=result,
        odds=MappingProxyType(dict(odds or {})),
        stats=MappingProxyType({}),
        source_line=line,
    )
