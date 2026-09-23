"""Stratejinin gördüğü kayıtlar (Faz 2 tasarımı §7.2, Faz 3 tasarımı §7.1).

Tipler burada, kurucular `backtest/context.py`de, oynatma `backtest/harness.py`de: harness ve
kurucu bu modülü paylaşır, birbirini import etmez (döngü yok). `harness` bu adları yeniden ihraç
eder; eski `from football_edge.backtest.harness import DecisionContext` çağrıları değişmez.
"""

from __future__ import annotations

import datetime as dt  # `date` bir alan adı: sınıf gövdesinde tip adını gölgelerdi
from collections.abc import Mapping
from dataclasses import dataclass

from football_edge.history.types import OddsKey


@dataclass(frozen=True, order=True)
class MatchKey:
    """Maçın kaynaktan bağımsız kimliği: lig kodu, kaynağın (Londra) tarihi, kanonik adlar.

    `match_index` yeniden oynatmaya özgü bir SIRADIR; canlıda karşılığı yoktur (tasarım §7.5).
    """

    league: str
    date: dt.date
    home: str
    away: str


@dataclass(frozen=True)
class ResultRecord:
    league: str
    date: dt.date
    home: str
    away: str
    home_goals: int
    away_goals: int
    known_at: dt.datetime


@dataclass(frozen=True)
class DecisionContext:
    """Stratejinin gördüğü TEK kayıt: kapanış, sonuç ve durum görüntüsü alanı yoktur (R98).

    Durum stratejinin içindedir (`observe` yeni değer döner); zamanı harness yönetir.
    """

    match_index: int
    league: str
    season: str
    date: dt.date
    home: str
    away: str
    decision_at: dt.datetime
    pre_prices: Mapping[OddsKey, float]  # yalnız PRE_CLOSING anahtarları

    @property
    def key(self) -> MatchKey:
        return MatchKey(league=self.league, date=self.date, home=self.home, away=self.away)
