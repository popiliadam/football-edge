"""Tarihsel tabanın ortak tipleri.

Ayrıştırıcı, kilit ve harness aynı dalgada paralel yazılır ve üçü de bu tiplere karşı yazar; bu
yüzden tipler dalga 0'da, tek bir controller commit'inde gelir. `datetime` modül adıyla alınır:
`date` bir alan adıdır ve sınıf gövdesinde tip adını gölgelerdi.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

PRE_CLOSING = "pre"
CLOSING = "close"
# football-data'nın piyasa ortalaması: (REFERENCE_BOOK, CLOSING) = AvgC, referans kapanış (D3);
# (REFERENCE_BOOK, PRE_CLOSING) = Avg. Tarihsel tabanın her okuyucusu kitabı buradan alır.
REFERENCE_BOOK = "Avg"
H2H = "1x2"
TOTALS_25 = "ou25"
MARKET_OUTCOMES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {H2H: ("H", "D", "A"), TOTALS_25: ("over", "under")}
)
RESULTS: tuple[str, ...] = MARKET_OUTCOMES[H2H]


@dataclass(frozen=True, order=True)
class OddsKey:
    book: str
    market: str
    outcome: str
    phase: str


@dataclass(frozen=True)
class HistMatch:
    """Tek tarihsel maç. Eşlemeler değiştirilemez ama hash'lenemez (küme anahtarı olamaz)."""

    league: str
    season: str
    date: dt.date
    kickoff: dt.datetime | None
    home: str
    away: str
    home_goals: int
    away_goals: int
    result: str
    odds: Mapping[OddsKey, float]
    stats: Mapping[str, int]
    source_line: int

    def prices(self, book: str, market: str, phase: str) -> tuple[float, ...] | None:
        """Marketin bütün sonuçlarının fiyatı MARKET_OUTCOMES sırasıyla; biri eksikse None.

        Vig temizleme sonuç kümesinin tamamını ister: eksik bir sonucu atlamak kalan olasılıkları
        yanlış normalize eder.
        """
        found: list[float] = []
        for outcome in MARKET_OUTCOMES[market]:
            price = self.odds.get(OddsKey(book, market, outcome, phase))
            if price is None:
                return None
            found.append(price)
        return tuple(found)
