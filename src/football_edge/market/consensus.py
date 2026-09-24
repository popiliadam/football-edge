"""Tur konsensüsü: bir snapshot turunun 1X2'sinde üç sonucu da fiyatlayan kitapların ortalaması.

Tanım TEKTİR (Faz 6 İz B tasarımı §4.3): canlı karar fiyatı (`live.context.pre_prices`), mühürlü
kapanış (`live.store.load_closing`, `pre_prices` üzerinden) ve sitenin dışa aktarımı
(`football_edge.site`) bu fonksiyonu çağırır. Yaprak modüldür, yalnız `history.types`i import
eder: `live.context` `backtest.*` ve `history.catalog` taşıdığı için site onu import edemez (H1f).
Referans kitap anahtarını (`OddsKey(REFERENCE_BOOK, …)`) burada kimse kurmaz; o `pre_prices`in
işidir.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from football_edge.history.types import RESULTS

LIVE_H2H = "h2h"
LIVE_DRAW = "Draw"


@dataclass(frozen=True)
class Quote:
    match_id: str
    observed_at: datetime
    bookmaker: str
    market: str
    outcome: str
    price: float


@dataclass(frozen=True)
class RoundConsensus:
    means: tuple[float, float, float]  # RESULTS sırasıyla (H, D, A), ham ortalama fiyat
    books: int  # üç sonucu da fiyatlayan kitap sayısı


def round_consensus(
    quotes: Sequence[Quote], observed_at: datetime, home: str, away: str
) -> RoundConsensus | None:
    """`observed_at` turunun 1X2'si: üç sonucu tam kitapların ortalama fiyatı; tam kitap yoksa None.

    Sonuç adı The Odds API'nin yazımıdır: ev takımının adı, `Draw`, deplasman takımının adı.
    """
    names = {home: "H", LIVE_DRAW: "D", away: "A"}
    books: dict[str, dict[str, float]] = {}
    for quote in quotes:
        if quote.market == LIVE_H2H and quote.observed_at == observed_at and quote.outcome in names:
            books.setdefault(quote.bookmaker, {})[names[quote.outcome]] = quote.price
    full = [book for book in books.values() if set(book) == set(RESULTS)]
    if not full:
        return None
    home_mean, draw_mean, away_mean = (
        math.fsum(book[outcome] for book in full) / len(full) for outcome in RESULTS
    )
    return RoundConsensus((home_mean, draw_mean, away_mean), len(full))
