"""Model ve walk-forward testlerinin SENTETİK sezonları.

Takım adları ve fiyatlar uydurma (spec §3.2/4); goller bilinen güçlerle tohumlu Poisson'dan. Ana
lig sezonlarında 2019/20'den önce kapanış öncesi kitap `BbAv` (kapanış yok), sonra `Avg` + `AvgC`
— football-data'nın sütun tarihçesi gibi (Faz 2 ölçüm §2.4).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta

import numpy as np

from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, TOTALS_25, HistMatch, OddsKey
from tests.backtest_builders import hist_match, quote

TEAMS = ("Alfa", "Beta", "Gama", "Delta", "Epsilon", "Zeta", "Eta", "Teta")
STRENGTH = (0.5, 0.35, 0.2, 0.05, -0.05, -0.2, -0.35, -0.5)
HOME = 0.25
MARGIN = 1.05


def _probs(home: int, away: int) -> tuple[tuple[float, float, float], tuple[float, float]]:
    lam = math.exp(STRENGTH[home] - STRENGTH[away] + HOME)
    mu = math.exp(STRENGTH[away] - STRENGTH[home])
    pmf_h = [math.exp(-lam) * lam**k / math.factorial(k) for k in range(11)]
    pmf_a = [math.exp(-mu) * mu**k / math.factorial(k) for k in range(11)]
    grid = np.outer(pmf_h, pmf_a)
    grid = grid / grid.sum()
    h, d, a = float(np.tril(grid, -1).sum()), float(np.trace(grid)), float(np.triu(grid, 1).sum())
    goals = np.add.outer(np.arange(11), np.arange(11))
    over = float(grid[goals > 2.5].sum())
    return (h, d, a), (over, 1.0 - over)


def _prices(probs: Sequence[float]) -> tuple[float, ...]:
    return tuple(round(1.0 / (p * MARGIN), 2) for p in probs)


def season(
    code: str,
    first: date,
    *,
    league: str = "E0",
    seed: int = 1,
    rounds: int = 14,
    teams: Sequence[str] = TEAMS,
) -> tuple[HistMatch, ...]:
    """Cumartesi 14:00 UTC turları; `code >= "1920"` ise Avg/AvgC, değilse yalnız BbAv."""
    rng = np.random.default_rng(seed)
    count = len(teams)
    found: list[HistMatch] = []
    line = 0
    for week in range(rounds):
        day = first + timedelta(weeks=week)
        order = [(index + week) % count for index in range(count)]
        for pair in range(count // 2):
            home, away = order[pair], order[count - 1 - pair]
            if week % 2:
                home, away = away, home
            h2h, totals = _probs(home, away)
            goals = (
                int(rng.poisson(math.exp(STRENGTH[home] - STRENGTH[away] + HOME))),
                int(rng.poisson(math.exp(STRENGTH[away] - STRENGTH[home]))),
            )
            odds: dict[OddsKey, float] = {}
            if code >= "1920":
                odds |= quote("Avg", PRE_CLOSING, _prices(h2h))
                odds |= quote("Avg", CLOSING, _prices(h2h))
                odds |= quote("Avg", PRE_CLOSING, _prices(totals), market=TOTALS_25)
                odds |= quote("Avg", CLOSING, _prices(totals), market=TOTALS_25)
            else:
                odds |= quote("BbAv", PRE_CLOSING, _prices(h2h))
            line += 1
            found.append(
                hist_match(
                    day=day,
                    kickoff=datetime.combine(day, time(14), tzinfo=UTC),
                    league=league,
                    season=code,
                    home=teams[home],
                    away=teams[away],
                    goals=goals,
                    odds=odds,
                    line=line,
                )
            )
    return tuple(found)


def main_history(
    first_year: int = 2011, last_year: int = 2024, *, league: str = "E0"
) -> tuple[HistMatch, ...]:
    """`first_year` → `last_year` başlangıçlı sezonlar; her biri ağustosun ilk cumartesisi."""
    found: list[HistMatch] = []
    for year in range(first_year, last_year + 1):
        code = f"{year % 100:02d}{(year + 1) % 100:02d}"
        first = date(year, 8, 1)
        first += timedelta(days=(5 - first.weekday()) % 7)
        found.extend(season(code, first, league=league, seed=year))
    return tuple(found)


H2H_KEYS = tuple(OddsKey("Avg", H2H, outcome, PRE_CLOSING) for outcome in ("H", "D", "A"))
