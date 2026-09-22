"""Verimlilik testlerinin SENTETİK örnekleri — gerçek maç, takım ya da oran satırı değil."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

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


# Kalibrasyonu BİLİNEN örnek: fiyatlar adil (Σ 1/o = 1, her yöntem aynı p'yi verir), sonuçlar
# p^γ / Σ p^γ'dan sabit tohumla çekilir. logit(q) ≈ γ · logit(p): havuzlanmış eğim ≈ γ.
FAIR_HOMES = tuple(0.15 + 0.05 * step for step in range(12))  # 0.15 … 0.70, beraberlik 0.25
OUTCOME_GOALS = ((1, 0), (0, 0), (0, 1))


def calibrated(count: int, *, gamma: float, seed: int) -> tuple[HistMatch, ...]:
    """Ek lig (X1) maçları; gerçek sonuç olasılığı piyasanın p'sinin γ kuvvetiyle bozulmuşu."""
    rng = np.random.default_rng(seed)
    matches = []
    for index in range(count):
        home = FAIR_HOMES[index % len(FAIR_HOMES)]
        fair = np.array((home, 0.25, 0.75 - home))
        true = fair**gamma / np.sum(fair**gamma)
        outcome = int(rng.choice(3, p=true))
        matches.append(
            hist_match(
                league="X1",
                season="2023",
                day=date(2022, 8, 6) + timedelta(days=7 * (index // 10)),
                home=f"Team {2 * index:04d}",
                away=f"Team {2 * index + 1:04d}",
                goals=OUTCOME_GOALS[outcome],
                prices={("Avg", H2H, CLOSING): tuple(float(1.0 / p) for p in fair)},
                line=index + 1,
            )
        )
    return tuple(matches)


RESULT_GOALS = {"H": (1, 0), "D": (0, 0), "A": (0, 1)}
MARGINED = (1.5, 4.0, 7.0)  # Σ 1/o ≈ 1.06: üç yöntem ayrışır


def patterned(
    pattern: str, *, league: str, season: str, start: date, repeats: int, first: int
) -> tuple[HistMatch, ...]:
    """Hep aynı marjlı AvgC (1.5, 4.0, 7.0); sonuçlar `pattern`in (H/D/A) tekrarı."""
    return tuple(
        hist_match(
            league=league,
            season=season,
            day=start + timedelta(days=7 * (index // 8)),
            home=f"Team {2 * (first + index):03d}",
            away=f"Team {2 * (first + index) + 1:03d}",
            goals=RESULT_GOALS[pattern[index % len(pattern)]],
            prices={("Avg", H2H, CLOSING): MARGINED},
            line=first + index + 1,
        )
        for index in range(len(pattern) * repeats)
    )
