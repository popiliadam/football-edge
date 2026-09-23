"""Defterden canlı kurucunun ve gölge raporunun okuduğu satırlar (salt okuma). Yazan yol yok."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

import psycopg

from football_edge.backtest.walkforward import DC, ELO, MARKET
from football_edge.history.types import H2H, PRE_CLOSING, RESULTS, OddsKey
from football_edge.live.context import LIVE_H2H, REFERENCE_BOOK, LiveMatch, Quote, pre_prices

_MATCHES = """
    SELECT id, league_id, commence_time, home_team, away_team
    FROM matches
    WHERE commence_time >= %s AND commence_time < %s
    ORDER BY commence_time, id
"""
_QUOTES = """
    SELECT match_id, observed_at, bookmaker, market, outcome, price
    FROM odds_snapshots
    WHERE match_id = ANY(%s) AND market = %s AND observed_at <= %s
    ORDER BY match_id, observed_at, bookmaker, outcome
"""


def load_live_matches(
    conn: psycopg.Connection[Any], *, since: datetime, until: datetime
) -> tuple[LiveMatch, ...]:
    with conn.cursor() as cur:
        cur.execute(_MATCHES, (since, until))
        rows = cur.fetchall()
    return tuple(
        LiveMatch(str(row[0]), str(row[1]), row[2], str(row[3]), str(row[4])) for row in rows
    )


def load_quotes(
    conn: psycopg.Connection[Any], match_ids: tuple[str, ...], *, until: datetime
) -> tuple[Quote, ...]:
    """`until`e kadar gözlenen 1X2 satırları; fiyat `numeric` → float."""
    if not match_ids:
        return ()
    with conn.cursor() as cur:
        cur.execute(_QUOTES, (list(match_ids), LIVE_H2H, until))
        rows = cur.fetchall()
    return tuple(
        Quote(str(row[0]), row[1], str(row[2]), str(row[3]), str(row[4]), float(row[5]))
        for row in rows
    )


# Gölge raporunun okuyabildiği TEK strateji kümesi (Faz 4 tasarımı §5/5): Jev'li stratejiyle
# baz arasındaki fark yalnız ön kayıtlı kapanış komutunda hesaplanır — burada adı bile geçmez.
BASE_STRATEGIES: frozenset[str] = frozenset({MARKET, ELO, DC})
_PREDICTIONS = """
    SELECT match_id, match_key, strategy, p_home, p_draw, p_away, pre_home, pre_draw, pre_away,
           decided_at, model_config_sha256
    FROM model_predictions
    WHERE decided_at >= %s AND model_config_sha256 = %s AND strategy = ANY(%s)
    ORDER BY decided_at, match_id, strategy
"""
_CLOSING = """
    SELECT o.match_id, o.observed_at, o.bookmaker, o.outcome, o.price, m.home_team, m.away_team
    FROM odds_snapshots o JOIN matches m ON m.id = o.match_id
    WHERE o.match_id = ANY(%s) AND o.market = %s AND o.is_closing
    ORDER BY o.match_id, o.observed_at, o.bookmaker, o.outcome
"""


@dataclass(frozen=True)
class PredictionRow:
    match_id: str
    match_key: str
    league: str  # football-data kodu (`match_key`in ilk alanı)
    strategy: str
    probs: tuple[float, float, float]
    pre: tuple[float, float, float]
    decided_at: datetime
    model_config_sha256: str


def _triple(values: Sequence[Any]) -> tuple[float, float, float]:
    home, draw, away = (float(value) for value in values)
    return home, draw, away


def load_predictions(
    conn: psycopg.Connection[Any],
    *,
    since: datetime,
    strategies: frozenset[str],
    model_config_sha256: str,
) -> tuple[PredictionRow, ...]:
    """`since`ten beri karar verilmiş gölge satırları, yalnız `BASE_STRATEGIES`ten — mühür iki
    katlıdır: istenen küme sorguya gitmeden, dönen satırlar da okunduktan sonra denetlenir."""
    if not strategies or not strategies <= BASE_STRATEGIES:
        raise ValueError(f"mühür: gölge raporu yalnız {sorted(BASE_STRATEGIES)} okur")
    with conn.cursor() as cur:
        cur.execute(_PREDICTIONS, (since, model_config_sha256, sorted(strategies)))
        rows = cur.fetchall()
    found = tuple(
        PredictionRow(
            match_id=str(row[0]),
            match_key=str(row[1]),
            league=str(row[1]).split("|", 1)[0],
            strategy=str(row[2]),
            probs=_triple(row[3:6]),
            pre=_triple(row[6:9]),
            decided_at=row[9],
            model_config_sha256=str(row[10]),
        )
        for row in rows
    )
    strays = sorted({row.strategy for row in found} - strategies)
    if strays:
        raise ValueError(f"mühür: sorgu istenmeyen strateji döndürdü: {strays}")
    return found


def load_closing(
    conn: psycopg.Connection[Any], match_ids: tuple[str, ...]
) -> Mapping[str, tuple[float, float, float]]:
    """Maç → mühürlü kapanışın (H, D, A) ham fiyatı: son kapanış turunun tam kitap ortalaması —
    karar fiyatıyla (`pre_prices`) aynı kural. Tam kitabı olmayan maç eşlemde yoktur."""
    if not match_ids:
        return MappingProxyType({})
    with conn.cursor() as cur:
        cur.execute(_CLOSING, (list(match_ids), LIVE_H2H))
        rows = cur.fetchall()
    quotes: dict[str, list[Quote]] = {}
    teams: dict[str, tuple[str, str]] = {}
    for row in rows:
        match_id = str(row[0])
        quotes.setdefault(match_id, []).append(
            Quote(match_id, row[1], str(row[2]), LIVE_H2H, str(row[3]), float(row[4]))
        )
        teams[match_id] = (str(row[5]), str(row[6]))
    found: dict[str, tuple[float, float, float]] = {}
    for match_id, usable in quotes.items():
        latest = max(quote.observed_at for quote in usable)
        home, away = teams[match_id]
        prices = pre_prices(usable, LiveMatch(match_id, "", latest, home, away), latest)
        if prices is not None:
            found[match_id] = _triple(
                [prices[OddsKey(REFERENCE_BOOK, H2H, outcome, PRE_CLOSING)] for outcome in RESULTS]
            )
    return MappingProxyType(found)
