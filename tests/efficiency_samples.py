"""Verimlilik testlerinin SENTETİK örnekleri — gerçek maç, takım ya da oran satırı değil."""

from __future__ import annotations

from datetime import date, timedelta

from football_edge.history.catalog import EXTRA, MAIN, HistoryLeague
from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, TOTALS_25, HistMatch
from tests.market_factory import Prices, hist_match, with_prices

MAIN_LEAGUE = HistoryLeague("M1", "m.1", "Ana Lig", "Xland", 1, MAIN, "0506", "soccer_m1")
EXTRA_LEAGUE = HistoryLeague("X1", "x.1", "Ek Lig", "Yland", 1, EXTRA, "", "")
# Dört AvgC kümesi (ilki adil: Σ 1/o = 1) ve yedi skor. 4 ile 7 aralarında asal: her fiyat
# kümesi her sonucu görür, kalibrasyon fiti hiçbir yeniden örneklemde ayrışmaz.
CLOSE_SETS = ((2.0, 4.0, 4.0), (1.6, 4.2, 6.0), (2.6, 3.3, 2.9), (3.4, 3.5, 2.2))
SCORES = ((2, 0), (1, 1), (0, 1), (3, 1), (0, 0), (1, 2), (2, 1))
TOTAL_SETS = ((1.8, 2.1), (2.2, 1.7), (1.95, 1.95))


def synthetic(
    count: int,
    *,
    start: date = date(2023, 8, 5),
    league: str = "M1",
    season: str = "2324",
    first: int = 0,
) -> tuple[HistMatch, ...]:
    """Haftada sekiz maç, sentetik takım adları, yalnız AvgC 1X2 fiyatı."""
    return tuple(
        hist_match(
            league=league,
            season=season,
            day=start + timedelta(days=7 * (index // 8)),
            home=f"Team {2 * (first + index):03d}",
            away=f"Team {2 * (first + index) + 1:03d}",
            goals=SCORES[index % 7],
            prices={("Avg", H2H, CLOSING): CLOSE_SETS[index % 4]},
            line=first + index + 1,
        )
        for index in range(count)
    )


def added(matches: tuple[HistMatch, ...], prices: Prices) -> tuple[HistMatch, ...]:
    return tuple(with_prices(match, prices) for match in matches)


def rich(matches: tuple[HistMatch, ...]) -> tuple[HistMatch, ...]:
    """Her ölçütün girdisi dolu: kapanış öncesi Avg/Max, PSC, BFEC, Ü/A 2.5 kapanışı."""
    return tuple(
        with_prices(
            match,
            {
                ("Avg", H2H, PRE_CLOSING): (3.0, 3.0, 3.0),
                ("Max", H2H, PRE_CLOSING): CLOSE_SETS[(index + 1) % 4],
                ("PS", H2H, CLOSING): CLOSE_SETS[(index + 2) % 4],
                ("BFE", H2H, CLOSING): CLOSE_SETS[(index + 3) % 4],
                ("Avg", TOTALS_25, CLOSING): TOTAL_SETS[index % 3],
            },
        )
        for index, match in enumerate(matches)
    )


BASE = synthetic(56)
