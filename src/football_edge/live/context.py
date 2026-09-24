"""Canlı bağlam kurucusu (Faz 3 tasarımı §7.2–7.3; R128, R132, R133).

Kaynak: defterdeki maç ve snapshot satırları (`live/store.py`) + tarihsel tabanın anahtarsız
dönüşü (DEV + POST — R128: holdout yılı canlıda da yoktur). Son adım tarihsel kurucuyla ORTAKTIR
(`backtest/context.py`): canlı kurucu yalnız kaynağı `MatchRecord`a çevirir. Karar ve sonuç anları
`timeline`ın kuralıyla hesaplanır; gerçek varış anı KULLANILMAZ. Tarihsel kuralın "bilinir" saydığı
bir sonuç tabanda yoksa maç için bağlam kurulmaz (bayat durum). Defterde fikstürü olan ligde bu
kesindir; defterde olmayan grup liglerinde (E1–E3 …) football-data'nın tarih yoğunluğundan
sezgiseldir (R141) — orada gecikme erken fark edilmezse akış tarihsel akıştan ayrışabilir.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import MappingProxyType

from football_edge.backtest.context import MatchRecord, context_of, record_of, result_of
from football_edge.backtest.records import DecisionContext, MatchKey, ResultRecord
from football_edge.backtest.timeline import LONDON, RESULT_LAG, decision_at, result_known_at
from football_edge.history.catalog import MAIN
from football_edge.history.types import H2H, PRE_CLOSING, RESULTS, HistMatch, OddsKey
from football_edge.market.consensus import LIVE_DRAW as LIVE_DRAW
from football_edge.market.consensus import LIVE_H2H as LIVE_H2H
from football_edge.market.consensus import Quote as Quote
from football_edge.market.consensus import round_consensus
from football_edge.naming import normalise_team

REFERENCE_BOOK = "Avg"  # canlı kitap ortalaması, football-data'nın `Avg`'sinin yapısal karşılığı
STALE_LOOKBACK = timedelta(days=10)
# R141: defterde fikstürü olmayan grup ligleri (E1–E3, D2, I2, SP2, F2 …) için bayatlık
# football-data'nın KENDİ tarihlerinden okunur. Eşik ligin DÜZENLİ maç aralığıdır (≤ 10 gün;
# milli ara ve sezon arası dışarıda) — %90'lık + 1 gün. Ara boyunca grubun başka bir ligi oynadıysa
# lig geride sayılır; grup bütünüyle durduysa (milli ara) yargılanmaz. 21 günü aşan ara yargılanmaz.
IN_SEASON_GAP = 21
REGULAR_GAP = 10
MIN_HISTORY_DATES = 10
LAG_QUANTILE = 0.9


@dataclass(frozen=True)
class LiveMatch:
    match_id: str
    league_id: str
    kickoff: datetime  # UTC, saat dilimli
    home: str  # The Odds API adı
    away: str


@dataclass(frozen=True)
class Naming:
    codes: Mapping[str, str]  # canlı lig kimliği → football-data kodu
    aliases: Mapping[str, str]  # The Odds API adı → football-data adı
    known: Mapping[str, Mapping[str, str]]  # kod → normalize ad → football-data adı


@dataclass(frozen=True)
class LiveDecision:
    match_id: str
    record: MatchRecord
    context: DecisionContext
    results: tuple[ResultRecord, ...]


@dataclass(frozen=True)
class LiveBatch:
    decisions: tuple[LiveDecision, ...]
    unmapped: tuple[str, ...]  # lig ya da ad eşlenemedi
    stale: tuple[str, ...]  # grubun bilinmesi gereken bir sonucu tabanda yok
    no_quote: tuple[str, ...]  # karar anından önce tam 1X2 snapshot'ı yok


def naming_from(
    history: Mapping[str, Sequence[HistMatch]], codes: Mapping[str, str], aliases: Mapping[str, str]
) -> Naming:
    known = {
        code: MappingProxyType(
            {normalise_team(name): name for match in matches for name in (match.home, match.away)}
        )
        for code, matches in history.items()
    }
    return Naming(MappingProxyType(dict(codes)), aliases, MappingProxyType(known))


def canonical(naming: Naming, code: str, live_name: str) -> str | None:
    """Takma ad varsa O (football-data adı), yoksa tabanda normalize adı tutan ad."""
    if live_name in naming.aliases:
        return naming.aliases[live_name]
    return naming.known.get(code, {}).get(normalise_team(live_name))


def match_key_text(key: MatchKey) -> str:
    """`model_predictions.match_key` biçimi: gölge satırı bununla yazılır, gölge raporu tarihsel
    sonucu bununla bulur — biçim tek yerde."""
    return f"{key.league}|{key.date.isoformat()}|{key.home}|{key.away}"


def live_key(match: LiveMatch, naming: Naming) -> MatchKey | None:
    code = naming.codes.get(match.league_id)
    if code is None:
        return None
    home, away = canonical(naming, code, match.home), canonical(naming, code, match.away)
    if home is None or away is None:
        return None
    # football-data'nın `Date`i İngiltere tarihidir (R102; köprüyle aynı kural).
    return MatchKey(code, match.kickoff.astimezone(LONDON).date(), home, away)


def season_of(history: Sequence[HistMatch], day: date, kind: str) -> str | None:
    """Ana lig: temmuzda başlayan sezon kodu (`2627`); ek lig: tabandaki son maçın sezonu."""
    if kind == MAIN:
        start = day.year if day.month >= 7 else day.year - 1
        return f"{start % 100:02d}{(start + 1) % 100:02d}"
    earlier = [match for match in history if match.date <= day]
    return max(earlier, key=lambda match: match.date).season if earlier else None


def pre_prices(
    quotes: Sequence[Quote], match: LiveMatch, decided: datetime
) -> Mapping[OddsKey, float] | None:
    """Karar anında ya da önce gözlenen SON snapshot turunun 1X2'si, üç sonucu tam kitapların
    ortalaması (`market.consensus.round_consensus`); tam kitap yoksa None."""
    usable = [q for q in quotes if q.market == LIVE_H2H and q.observed_at <= decided]
    if not usable:
        return None
    latest = max(q.observed_at for q in usable)
    found = round_consensus(usable, latest, match.home, match.away)
    if found is None:
        return None
    return MappingProxyType(
        {
            OddsKey(REFERENCE_BOOK, H2H, outcome, PRE_CLOSING): mean
            for outcome, mean in zip(RESULTS, found.means, strict=True)
        }
    )


def observe_stream(group: Sequence[HistMatch], decided: datetime) -> tuple[ResultRecord, ...]:
    """Harness'ın `decided` anındaki karardan önce `observe`a verdiği sonuçlar, AYNI sırayla:
    (bilinme anı, gruptaki sıra) — `build_events`in sonuç olaylarının düzeni."""
    known = sorted(
        (result_known_at(match.date, match.kickoff), index)
        for index, match in enumerate(group)
        if result_known_at(match.date, match.kickoff) < decided
    )
    return tuple(result_of(record_of(group[index]), at) for at, index in known)


def is_stale(
    match: LiveMatch,
    group_live: Sequence[LiveMatch],
    naming: Naming,
    history_keys: frozenset[MatchKey],
    decided: datetime,
) -> bool:
    """Grubun, karar anından önce bitmiş sayılan (başlama + 3 sa) son 10 gündeki bir canlı maçı
    tabanda yoksa True — eşlenemeyen maç da doğrulanamadığı için bayat sayılır."""
    for other in group_live:
        if other.match_id == match.match_id:
            continue
        finished = other.kickoff + RESULT_LAG < decided
        recent = other.kickoff >= decided - STALE_LOOKBACK
        if finished and recent and live_key(other, naming) not in history_keys:
            return True
    return False


def league_lagging(dates: Sequence[date], decided_on: date) -> bool:
    """Ligin son sonucu, geçen yılın DÜZENLİ maç aralığına (%90'lık + 1 gün) göre fazla eski mi.

    Düzenli aralık ≤ `REGULAR_GAP`: milli aralar (~13–14 gün) eşiğe girmez — girseydi haftada iki
    maç oynayan bir ligin kaçan hafta sonu görünmezdi (yeniden inceleme n2).
    """
    past = sorted({day for day in dates if day < decided_on})
    if len(past) < MIN_HISTORY_DATES:
        return False
    gap = (decided_on - past[-1]).days
    if gap > IN_SEASON_GAP:
        return False
    usual = sorted(
        (later - earlier).days
        for earlier, later in zip(past, past[1:], strict=False)
        if (decided_on - later).days <= 365 and (later - earlier).days <= REGULAR_GAP
    )
    if not usual:
        return False
    return gap > usual[int(LAG_QUANTILE * (len(usual) - 1))] + 1


def lagging_leagues(
    group: Sequence[HistMatch], decided: datetime, ledger: frozenset[str] = frozenset()
) -> tuple[str, ...]:
    """Grubun, defterde fikstürü OLMAYAN ve geride kalan ligleri, karar gününe (Londra) göre
    (R141, R153). `ledger`deki ligler yargılanmaz — onları katman (a) `is_stale` doğrular — ama
    tarihleri öteki liglerin "grup bu arada oynadı mı" sorusunda sayılır."""
    decided_on = decided.astimezone(LONDON).date()
    dates: dict[str, list[date]] = {}
    for match in group:
        dates.setdefault(match.league, []).append(match.date)
    return tuple(
        code
        for code in sorted(dates)
        if code not in ledger
        and league_lagging(dates[code], decided_on)
        and _group_played_since(dates, code, decided_on)
    )


def _group_played_since(dates: Mapping[str, Sequence[date]], code: str, decided_on: date) -> bool:
    """Grubun BAŞKA bir ligi bu ligin son maçından sonra (karar gününden önce) oynadı mı — milli ara
    ayrımı: grup bütünüyle durduysa gecikme değil aradır."""
    last = max(day for day in dates[code] if day < decided_on)
    return any(
        last < day < decided_on for other, days in dates.items() if other != code for day in days
    )


def build_batch(
    live: Sequence[LiveMatch],
    quotes: Sequence[Quote],
    groups: Mapping[str, Sequence[HistMatch]],
    *,
    now: datetime,
    naming: Naming,
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
) -> LiveBatch:
    """`now`da kararı verilmiş ama başlamamış maçların bağlamları. `groups`: grup → tarihsel
    maçlar (`backtest.walkforward.group_matches` sırasıyla, DEV + POST)."""
    decisions: list[LiveDecision] = []
    unmapped: list[str] = []
    stale: list[str] = []
    no_quote: list[str] = []
    keys = frozenset(record_of(m).key for matches in groups.values() for m in matches)
    for match in sorted(live, key=lambda m: (m.kickoff, m.match_id)):
        key = live_key(match, naming)
        if key is None:
            unmapped.append(match.match_id)
            continue
        decided = decision_at(key.date, match.kickoff)
        if decided is None or not decided <= now < match.kickoff:
            continue
        group_name = rating_groups.get(key.league, key.league)
        group = groups.get(group_name, ())
        same_group = [
            m
            for m in live
            if rating_groups.get(naming.codes.get(m.league_id, ""), "") == group_name
        ]
        if is_stale(match, same_group, naming, keys, decided) or lagging_leagues(
            group, decided, ledger=frozenset(naming.codes.values())
        ):
            stale.append(match.match_id)
            continue
        prices = pre_prices([q for q in quotes if q.match_id == match.match_id], match, decided)
        season = season_of(
            [m for m in group if m.league == key.league], key.date, kinds.get(key.league, MAIN)
        )
        if prices is None or season is None:
            no_quote.append(match.match_id)
            continue
        record = MatchRecord(key, season, match.kickoff, prices, None)
        decisions.append(
            LiveDecision(
                match.match_id,
                record,
                context_of(0, record, decided),
                observe_stream(group, decided),
            )
        )
    return LiveBatch(tuple(decisions), tuple(unmapped), tuple(stale), tuple(no_quote))
