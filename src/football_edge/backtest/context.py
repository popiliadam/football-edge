"""Bağlamın tek son adımı (Faz 3 tasarımı §7.1, R98).

Tarihsel ve canlı kurucu kaynaklarını önce aynı ara kayda (`MatchRecord`) çevirir; bağlam ve
sonuç kaydı YALNIZ buradan kurulur. Eşitlik testi böylece "iki kod aynı şeyi mi yazdı"yı değil
"iki kaynak aynı kaydı mı üretti"yi sınar. Karar ve sonuç anları çağıranın (`timeline`)
kuralından gelir; burada hesaplanmaz.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from football_edge.backtest.records import DecisionContext, MatchKey, ResultRecord
from football_edge.history.types import H2H, PRE_CLOSING, HistMatch, OddsKey


class DuplicateMatch(ValueError):
    """Aynı `MatchKey` iki kez geçti: iki karar ve çift durum güncellemesi olurdu (14g, 14r)."""


@dataclass(frozen=True)
class MatchRecord:
    key: MatchKey
    season: str
    kickoff: dt.datetime | None
    pre_prices: Mapping[OddsKey, float]  # yalnız PRE_CLOSING anahtarları
    goals: tuple[int, int] | None  # sonuç henüz yoksa None


# Bağlam yalnız İKİ kaynağın da üretebildiği fiyatları taşır: canlı defter 1X2'yi kitap kitap
# toplar (snapshot `markets=h2h`); football-data karşılığı kitap ortalaması `Avg`'dir. Başka kitap
# ya da market bağlama girerse canlı bağlam onu taşıyamaz ve eşitlik (R98) sözde kalır.
CONTEXT_BOOK = "Avg"
CONTEXT_MARKETS = frozenset({H2H})


def pre_only(prices: Mapping[OddsKey, float]) -> Mapping[OddsKey, float]:
    """Kapanış öncesi `Avg` 1X2 anahtarları, değiştirilemez görünümde."""
    return MappingProxyType(
        {
            key: price
            for key, price in prices.items()
            if key.phase == PRE_CLOSING
            and key.book == CONTEXT_BOOK
            and key.market in CONTEXT_MARKETS
        }
    )


def record_of(match: HistMatch) -> MatchRecord:
    return MatchRecord(
        key=MatchKey(league=match.league, date=match.date, home=match.home, away=match.away),
        season=match.season,
        kickoff=match.kickoff,
        pre_prices=pre_only(match.odds),
        goals=(match.home_goals, match.away_goals),
    )


def context_of(index: int, record: MatchRecord, decided: dt.datetime) -> DecisionContext:
    return DecisionContext(
        match_index=index,
        league=record.key.league,
        season=record.season,
        date=record.key.date,
        home=record.key.home,
        away=record.key.away,
        decision_at=decided,
        pre_prices=pre_only(record.pre_prices),
    )


def result_of(record: MatchRecord, known_at: dt.datetime) -> ResultRecord:
    if record.goals is None:
        raise ValueError(f"{record.key}: sonucu olmayan maçtan sonuç kaydı kurulamaz")
    home_goals, away_goals = record.goals
    return ResultRecord(
        league=record.key.league,
        date=record.key.date,
        home=record.key.home,
        away=record.key.away,
        home_goals=home_goals,
        away_goals=away_goals,
        known_at=known_at,
    )


def check_unique(keys: Iterable[MatchKey]) -> None:
    seen: set[MatchKey] = set()
    for key in keys:
        if key in seen:
            raise DuplicateMatch(f"yinelenen maç: {key}")
        seen.add(key)
