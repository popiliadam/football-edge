"""Walk-forward satırları (Faz 3 tasarımı §5, R129): grup başına yeniden oynatma → bileşen tablosu.

Yalnız geliştirme dönemi: bölgeler `Window` ile kurulur ve `Window` holdout'a uzanamaz (R89).
Isınma bölgesi durumu ısıtır, satır üretmez. Model bileşenleri (Elo, Dixon-Coles) harness'tan
geçer; piyasa bileşeni maçın KENDİ kapanış öncesi fiyatıdır — `MarketPre`in bağlamdan okuduğunun
aynısı (kapanış ve sonuç satıra yalnız değerlendirme alanı olarak girer, hiçbir bileşene girmez).
Yeniden oynatma ülke grubu başına (R94, R136): gruplar arasında durum etkileşimi yoktur.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import MappingProxyType

from football_edge.backtest.context import record_of
from football_edge.backtest.harness import Strategy, replay
from football_edge.backtest.records import MatchKey
from football_edge.backtest.timeline import decision_at
from football_edge.history.catalog import EXTRA, MAIN
from football_edge.history.holdout import DEV_END, MAIN_WINDOW, Window, in_window
from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, TOTALS_25, HistMatch
from football_edge.market.devig import match_probs
from football_edge.market.metrics import outcome_index

SELECTION = "S"
EVALUATION = "E"
MAIN_SELECTION = Window(date(2012, 7, 1), date(2019, 7, 1))
MAIN_EVALUATION = MAIN_WINDOW
# Ek dosyalar 2012'de başlar: ilk yıl yalnız ısınma.
EXTRA_SELECTION = Window(date(2013, 1, 1), date(2018, 7, 1))
EXTRA_EVALUATION = Window(date(2018, 7, 1), DEV_END)
ZONES: Mapping[str, Mapping[str, Window]] = MappingProxyType(
    {
        MAIN: MappingProxyType({SELECTION: MAIN_SELECTION, EVALUATION: MAIN_EVALUATION}),
        EXTRA: MappingProxyType({SELECTION: EXTRA_SELECTION, EVALUATION: EXTRA_EVALUATION}),
    }
)
# S'de kapanış öncesi ortalama Betbrain'in (`BbAv`), E'de football-data'nın `Avg`'si (ölçüm §2.4).
PRE_BOOK: Mapping[str, str] = MappingProxyType({SELECTION: "BbAv", EVALUATION: "Avg"})
REFERENCE_BOOK = "Avg"
MARKET = "market"
ELO = "elo_fit"
DC = "dixon_coles"
DC_TOTALS = "dixon_coles_ou25"
ELO_SCAFFOLD = "elo_scaffold"  # Faz 2 iskelesi (`EloPointInTime`): kıyas, harmana girmez
BLEND_COMPONENTS: tuple[str, ...] = (MARKET, ELO, DC)
_NO_KICKOFF = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class Row:
    """Bir maçın walk-forward kaydı: bileşenler + yalnız değerlendirmenin okuduğu alanlar."""

    key: MatchKey
    kind: str
    zone: str
    season: str
    outcome: int  # RESULTS sırası
    totals_outcome: int  # 0 üst, 1 alt
    components: Mapping[str, tuple[float, ...]]  # 1X2 (H, D, A)
    totals: Mapping[str, tuple[float, ...]]  # Ü/A 2.5 (üst, alt)
    pre: tuple[float, ...] | None  # bölgenin kitabının kapanış öncesi 1X2 fiyatı (bahis fiyatı)
    closing: tuple[float, ...] | None  # vig'i temizlenmiş AvgC 1X2
    totals_pre: tuple[float, ...] | None
    totals_closing: tuple[float, ...] | None


def zone_of(match: HistMatch, kind: str) -> str | None:
    for zone, window in ZONES[kind].items():
        if in_window(match, window):
            return zone
    return None


def group_matches(
    leagues: Mapping[str, Sequence[HistMatch]], groups: Mapping[str, str]
) -> Mapping[str, tuple[HistMatch, ...]]:
    """Grup (ülke) → maçlar; (tarih, başlama, lig, ev) sırasıyla — `replay` sırayı zaten olaydan
    kurar, bu sıra yalnız `match_index`i belirlenimci yapar."""
    found: dict[str, list[HistMatch]] = {}
    for code in sorted(leagues):
        found.setdefault(groups.get(code, code), []).extend(leagues[code])
    return MappingProxyType(
        {
            group: tuple(
                sorted(
                    matches,
                    key=lambda m: (m.date, m.kickoff or _NO_KICKOFF, m.league, m.home),
                )
            )
            for group, matches in sorted(found.items())
        }
    )


def group_kind(matches: Sequence[HistMatch], kinds: Mapping[str, str]) -> str:
    found = {kinds[match.league] for match in matches}
    if len(found) != 1:
        raise ValueError(f"bir grupta ana ve ek lig birlikte: {sorted(found)}")
    return found.pop()


def model_probs(
    matches: Sequence[HistMatch], strategies: Mapping[str, Strategy]
) -> Mapping[str, Mapping[int, tuple[float, ...]]]:
    """Strateji adı → maç sırası → tahmin olasılıkları (tek grup, strateji başına bir oynatma)."""
    found: dict[str, Mapping[int, tuple[float, ...]]] = {}
    for name, strategy in strategies.items():
        result = replay(matches, strategy)
        found[name] = MappingProxyType(
            {prediction.match_index: prediction.probs for prediction in result.predictions}
        )
    return MappingProxyType(found)


def _market(match: HistMatch, book: str, market: str, method: str) -> tuple[float, ...] | None:
    return match_probs(match, book=book, market=market, phase=PRE_CLOSING, method=method)


def _row(
    index: int,
    match: HistMatch,
    kind: str,
    zone: str,
    probs: Mapping[str, Mapping[int, tuple[float, ...]]],
    method: str,
) -> Row:
    book = PRE_BOOK.get(zone, REFERENCE_BOOK)
    components: dict[str, tuple[float, ...]] = {
        name: found[index] for name, found in probs.items() if name != DC_TOTALS and index in found
    }
    market = _market(match, book, H2H, method)
    if market is not None:
        components[MARKET] = market
    totals: dict[str, tuple[float, ...]] = {}
    if index in probs.get(DC_TOTALS, {}):
        totals[DC] = probs[DC_TOTALS][index][:2]
    market_totals = _market(match, REFERENCE_BOOK, TOTALS_25, method)
    if market_totals is not None and zone != SELECTION:
        totals[MARKET] = market_totals
    return Row(
        key=record_of(match).key,
        kind=kind,
        zone=zone,
        season=match.season,
        outcome=outcome_index(match, H2H),
        totals_outcome=outcome_index(match, TOTALS_25),
        components=MappingProxyType(components),
        totals=MappingProxyType(totals),
        pre=match.prices(book, H2H, PRE_CLOSING),
        closing=match_probs(match, book=REFERENCE_BOOK, market=H2H, phase=CLOSING, method=method),
        totals_pre=match.prices(REFERENCE_BOOK, TOTALS_25, PRE_CLOSING),
        totals_closing=match_probs(
            match, book=REFERENCE_BOOK, market=TOTALS_25, phase=CLOSING, method=method
        ),
    )


def group_rows(
    matches: Sequence[HistMatch],
    kinds: Mapping[str, str],
    strategies: Mapping[str, Strategy],
    *,
    method: str,
    zoning: Callable[[HistMatch, str], str | None] = zone_of,
) -> tuple[Row, ...]:
    """Bir grubun bölge satırları (varsayılan S ve E); kararı olmayan ve bölgesiz maç satır
    üretmez. `final_eval` kendi bölgelemesini (holdout, sonrası) verir."""
    kind = group_kind(matches, kinds)
    probs = model_probs(matches, strategies)
    rows: list[Row] = []
    for index, match in enumerate(matches):
        zone = zoning(match, kind)
        if zone is None or decision_at(match.date, match.kickoff) is None:
            continue
        rows.append(_row(index, match, kind, zone, probs, method))
    return tuple(rows)
