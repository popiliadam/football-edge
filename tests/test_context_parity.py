"""Canlı ↔ tarihsel eşitlik (Faz 3 tasarımı §7.4 E1–E2, R98): aynı maç için iki kurucu aynı
`DecisionContext`i ve aynı `observe` akışını üretir. Veri SENTETİK; canlı taraf aynı maçı defter
satırı biçiminde taşır (The Odds API adları, kitap başına fiyat, birden çok snapshot turu)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.backtest.harness import DecisionContext, Prediction, ResultRecord, replay
from football_edge.backtest.timeline import decision_at
from football_edge.backtest.walkforward import group_matches
from football_edge.history.catalog import EXTRA, MAIN
from football_edge.history.types import H2H, PRE_CLOSING, RESULTS, HistMatch
from football_edge.live.context import (
    LiveMatch,
    Quote,
    build_batch,
    canonical,
    lagging_leagues,
    league_lagging,
    naming_from,
    observe_stream,
    pre_prices,
    season_of,
)
from football_edge.live.store import load_live_matches, load_quotes
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModel
from football_edge.model.strategies import DixonColesStrategy
from tests.backtest_builders import hist_match, quote
from tests.model_builders import season

LEAGUE_ID = "tst.1"
GROUPS = MappingProxyType({"E0": "Ülke"})
KINDS = MappingProxyType({"E0": MAIN})
ALIASES = MappingProxyType({"Alfa FC": "Alfa", "Birinci Takım": "Beta"})
# Cumartesi 23:30 UTC (BST): Londra'da pazar 00:30 — football-data'nın Date'i pazar.
LATE = hist_match(
    day=date(2026, 9, 13),
    kickoff=datetime(2026, 9, 12, 23, 30, tzinfo=UTC),
    season="2627",
    home="Gece",
    away="Yarasa",
    odds=quote("Avg", PRE_CLOSING, (2.4, 3.3, 3.1)),
    line=999,
)
# Cuma 08:00 UTC başlama: sonucu 11:00 UTC'de, cumartesi maçlarının karar anında TAM bilinir —
# harness eşzamanlılıkta kararı önce koyar; canlı akış onu da dışarıda bırakmalı (m1).
EARLY = hist_match(
    day=date(2026, 9, 11),
    kickoff=datetime(2026, 9, 11, 8, tzinfo=UTC),
    season="2627",
    home="Sabah",
    away="Erken",
    odds=quote("Avg", PRE_CLOSING, (2.2, 3.4, 3.3)),
    line=998,
)
HISTORY = (
    *season("2526", date(2025, 8, 2), seed=4),
    *season("2627", date(2026, 8, 1), seed=5),
    LATE,
    EARLY,
)
GROUP = group_matches({"E0": HISTORY}, GROUPS)["Ülke"]
NAMING = naming_from({"E0": HISTORY}, {LEAGUE_ID: "E0"}, ALIASES)


def _live_name(name: str) -> str:
    return "Alfa FC" if name == "Alfa" else name.upper()  # normalize eşitliği + takma ad


def _live(match: HistMatch) -> LiveMatch:
    assert match.kickoff is not None
    return LiveMatch(
        f"id-{match.source_line}",
        LEAGUE_ID,
        match.kickoff,
        _live_name(match.home),
        _live_name(match.away),
    )


def _quotes(match: HistMatch, live: LiveMatch) -> list[Quote]:
    """Karar anında TAM olarak gözlenen tur (iki tam kitap = Avg, bir eksik kitap), ondan önce iki
    farklı fiyatlı tur ve karar SONRASI bir tur (I3: `≤` → `<` kırmızı olsun)."""
    decided = decision_at(match.date, match.kickoff)
    assert decided is not None
    prices = match.prices("Avg", H2H, PRE_CLOSING)
    assert prices is not None
    names = (live.home, "Draw", live.away)
    found: list[Quote] = []
    for at, book, values in (
        (decided - timedelta(days=1), "eski", (9.0, 9.0, 9.0)),
        (decided - timedelta(hours=5), "önce", (8.0, 8.0, 8.0)),
        (decided, "b1", prices),
        (decided, "b2", prices),
        (decided + timedelta(hours=1), "sonra", (1.5, 5.0, 7.0)),
    ):
        found.extend(
            Quote(live.match_id, at, book, "h2h", name, value)
            for name, value in zip(names, values, strict=True)
        )
    found.append(Quote(live.match_id, decided, "eksik", "h2h", live.home, 1.01))
    return found


@dataclass(frozen=True)
class Recorder:
    """Her kararda gördüğü bağlamı ve o ana dek gözlediği sonuçları ortak sözlüklere yazar."""

    contexts: dict[int, DecisionContext]
    streams: dict[int, tuple[ResultRecord, ...]]
    seen: tuple[ResultRecord, ...] = ()

    @property
    def name(self) -> str:
        return "recorder"

    def observe(self, result: ResultRecord) -> Recorder:
        return replace(self, seen=(*self.seen, result))

    def predict(self, context: DecisionContext) -> Prediction | None:
        self.contexts[context.match_index] = context
        self.streams[context.match_index] = self.seen
        return None


@pytest.fixture(scope="module")
def historical() -> Recorder:
    recorder = Recorder(contexts={}, streams={})
    replay(GROUP, recorder)
    return recorder


def _targets() -> list[int]:
    """2026/27'nin kararı olan bütün maçları (yaz saati bitişi 2026-10-25, gece maçı dahil)."""
    return [
        index
        for index, match in enumerate(GROUP)
        if match.season == "2627" and decision_at(match.date, match.kickoff) is not None
    ]


def _batch(match: HistMatch, *, extra_live: tuple[LiveMatch, ...] = ()) -> Any:
    live = _live(match)
    decided = decision_at(match.date, match.kickoff)
    assert decided is not None
    return build_batch(
        (live, *extra_live),
        _quotes(match, live),
        {"Ülke": GROUP},
        now=decided + timedelta(minutes=30),
        naming=NAMING,
        kinds=KINDS,
        rating_groups=GROUPS,
    )


@pytest.mark.leakage
def test_the_live_builder_reproduces_the_historical_context_and_stream(
    historical: Recorder,
) -> None:
    """E1: bağlamın `match_index` dışındaki BÜTÜN alanları ve `observe` akışı birebir."""
    targets = _targets()
    assert len(targets) > 50 and GROUP.index(LATE) in targets

    for index in targets:
        batch = _batch(GROUP[index])
        (decision,) = batch.decisions
        assert replace(decision.context, match_index=index) == historical.contexts[index]
        assert decision.results == historical.streams[index]


@pytest.mark.leakage
def test_the_same_strategy_predicts_the_same_from_both_builders() -> None:
    """E2: Elo ve Dixon-Coles'a iki kurucudan gelen girdi aynı tahmini verir."""
    index = _targets()[40]
    strategies = (EloModel(), DixonColesStrategy(config=DCConfig(min_matches=40)))
    for strategy in strategies:
        replayed = {p.match_index: p.probs for p in replay(GROUP, strategy).predictions}
        (decision,) = _batch(GROUP[index]).decisions
        state = strategy
        for result in decision.results:
            state = state.observe(result)  # type: ignore[assignment]
        live = state.predict(replace(decision.context, match_index=index))
        assert live is not None and live.probs == pytest.approx(replayed[index])


def test_snapshots_after_the_decision_and_incomplete_books_are_ignored() -> None:
    match = GROUP[_targets()[3]]
    live = _live(match)
    decided = decision_at(match.date, match.kickoff)
    assert decided is not None

    found = pre_prices(_quotes(match, live), live, decided)

    assert found is not None
    assert tuple(
        found[key] for key in sorted(found, key=lambda k: RESULTS.index(k.outcome))
    ) == match.prices("Avg", H2H, PRE_CLOSING)
    assert pre_prices(_quotes(match, live), live, decided - timedelta(days=2)) is None


def test_a_live_night_kickoff_takes_the_london_date() -> None:
    (decision,) = _batch(LATE).decisions

    assert decision.record.key.date == date(2026, 9, 13)


def test_names_map_through_aliases_then_normalisation() -> None:
    assert canonical(NAMING, "E0", "Alfa FC") == "Alfa"
    assert canonical(NAMING, "E0", "Birinci Takım") == "Beta"  # yalnız takma adla bulunur
    assert canonical(NAMING, "E0", "BETA") == "Beta"
    assert canonical(NAMING, "E0", "Bilinmez") is None


def test_an_unmapped_match_gets_no_context() -> None:
    match = GROUP[_targets()[2]]
    stranger = replace(_live(match), match_id="yabancı", home="Bilinmez")
    decided = decision_at(match.date, match.kickoff)
    assert decided is not None

    batch = build_batch(
        (stranger,),
        [],
        {"Ülke": GROUP},
        now=decided,
        naming=NAMING,
        kinds=KINDS,
        rating_groups=GROUPS,
    )

    assert batch.unmapped == ("yabancı",) and batch.decisions == ()


def test_a_group_result_missing_from_the_base_makes_the_state_stale() -> None:
    """R132: tarihsel kural sonucu bilinir sayıyor, tabanda yok → tahmin yok, adıyla sayılır."""
    match = GROUP[_targets()[30]]
    decided = decision_at(match.date, match.kickoff)
    assert decided is not None
    missing = LiveMatch("kayıp", LEAGUE_ID, decided - timedelta(days=2), "ZETA", "ETA")

    batch = _batch(match, extra_live=(missing,))

    assert batch.decisions == () and batch.stale == (_live(match).match_id,)


def test_a_match_without_a_pre_decision_quote_is_counted() -> None:
    match = GROUP[_targets()[5]]
    live = _live(match)
    decided = decision_at(match.date, match.kickoff)
    assert decided is not None

    batch = build_batch(
        (live,), [], {"Ülke": GROUP}, now=decided, naming=NAMING, kinds=KINDS, rating_groups=GROUPS
    )

    assert batch.no_quote == (live.match_id,)


def test_matches_not_yet_decided_or_already_started_are_skipped() -> None:
    match = GROUP[_targets()[5]]
    live = _live(match)
    decided = decision_at(match.date, match.kickoff)
    assert decided is not None and match.kickoff is not None

    for now in (decided - timedelta(minutes=1), match.kickoff):
        batch = build_batch(
            (live,),
            _quotes(match, live),
            {"Ülke": GROUP},
            now=now,
            naming=NAMING,
            kinds=KINDS,
            rating_groups=GROUPS,
        )
        assert batch.decisions == ()


def test_season_codes() -> None:
    extra = (hist_match(day=date(2026, 3, 1), league="BRA", season="2026"),)

    assert season_of((), date(2026, 9, 1), MAIN) == "2627"
    assert season_of((), date(2027, 3, 1), MAIN) == "2627"
    assert season_of(extra, date(2026, 9, 1), EXTRA) == "2026"
    assert season_of(extra, date(2026, 2, 1), EXTRA) is None


def test_the_stream_is_ordered_like_the_harness_events() -> None:
    decided = datetime.combine(date(2026, 10, 2), time(11), tzinfo=UTC)

    stream = observe_stream(GROUP, decided)

    assert [r.known_at for r in stream] == sorted(r.known_at for r in stream)
    assert all(r.known_at < decided for r in stream)


class _Cursor:
    def __init__(self, rows: list[tuple[Any, ...]], log: list[tuple[str, tuple[Any, ...]]]) -> None:
        self.rows, self.log = rows, log

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.log.append((sql, params))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows


class _Connection:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows, self.log = rows, []  # type: ignore[var-annotated]

    def cursor(self) -> _Cursor:
        return _Cursor(self.rows, self.log)


def test_the_store_reads_matches_and_numeric_prices() -> None:
    at = datetime(2026, 9, 5, 6, 22, tzinfo=UTC)
    matches = _Connection([("m1", LEAGUE_ID, at, "Alfa FC", "BETA")])
    quotes = _Connection([("m1", at, "b1", "h2h", "Draw", Decimal("3.40"))])

    (live,) = load_live_matches(matches, since=at, until=at + timedelta(days=7))  # type: ignore[arg-type]
    (found,) = load_quotes(quotes, ("m1",), until=at)  # type: ignore[arg-type]

    assert live == LiveMatch("m1", LEAGUE_ID, at, "Alfa FC", "BETA")
    assert found.price == 3.4 and isinstance(found.price, float)
    assert quotes.log[0][1] == (["m1"], "h2h", at)
    assert load_quotes(_Connection([]), (), until=at) == ()  # type: ignore[arg-type]


def test_a_group_league_without_ledger_fixtures_that_falls_behind_makes_the_state_stale() -> None:
    """R141 (plan incelemesi I1): E1'in defterde fikstürü yok; football-data'daki son sonucu,
    lig haftalık oynarken 13 gün eskiyse E0 kararı bayattır; 21 günü aşan ara yargılanmaz."""
    second = (
        *season("2526", date(2025, 8, 2), league="E1", seed=6),
        *season("2627", date(2026, 8, 1), league="E1", seed=7, rounds=6),  # son sonuç 2026-09-05
    )
    groups = MappingProxyType({"E0": "Ülke", "E1": "Ülke"})
    group = group_matches({"E0": HISTORY, "E1": second}, groups)["Ülke"]
    naming = naming_from({"E0": HISTORY, "E1": second}, {LEAGUE_ID: "E0"}, ALIASES)

    def batch(day: date) -> Any:
        match = next(m for m in HISTORY if m.date == day)
        live = _live(match)
        decided = decision_at(match.date, match.kickoff)
        assert decided is not None
        return build_batch(
            (live,),
            _quotes(match, live),
            {"Ülke": group},
            now=decided + timedelta(minutes=30),
            naming=naming,
            kinds=KINDS,
            rating_groups=groups,
        )

    assert len(batch(date(2026, 9, 12)).decisions) == 1  # E1'in son sonucu 6 gün önce: olağan
    assert batch(date(2026, 9, 19)).stale  # 13 gün: E1 geride
    assert len(batch(date(2026, 10, 3)).decisions) == 1  # 27 gün: ara, yargılanmaz


@pytest.mark.parametrize(
    ("gap", "lagging"), [(6, False), (8, False), (9, True), (21, True), (22, False)]
)
def test_a_weekly_league_lags_after_its_usual_gap_plus_one_day(gap: int, lagging: bool) -> None:
    last = date(2026, 9, 5)
    weekly = [last - timedelta(weeks=week) for week in range(20)]

    assert league_lagging(weekly, last + timedelta(days=gap)) is lagging


def _twice_weekly(last: date, weeks: int = 40) -> list[date]:
    """Cumartesi + çarşamba; her dört haftada bir iki haftalık milli ara — çarşambadan cumartesiye
    17 günlük aralık, bütün aralıkların ~%11'i: %90'lık bir eşiği aralar belirlerdi."""
    found: list[date] = []
    day = last
    for week in range(weeks):
        found += [day, day - timedelta(days=4)]  # çarşamba, önceki cumartesi
        day -= timedelta(days=7 + (14 if week % 4 == 3 else 0))
    return sorted(found)


def test_a_twice_weekly_league_that_misses_a_weekend_lags() -> None:
    """Yeniden inceleme n2: %95'lik eşik milli araları (14 gün) sayardı ve kaçan bir hafta sonunu
    (çarşambadan salıya 6 gün) görmezdi; düzenli aralık (≤ 10 gün) eşiği 4 + 1 gündür."""
    wednesday = date(2026, 9, 9)
    dates = _twice_weekly(wednesday)

    assert league_lagging(dates, wednesday + timedelta(days=3)) is False  # cumartesi kararı: olağan
    assert league_lagging(dates, wednesday + timedelta(days=6)) is True  # salı: hafta sonu yok


def test_a_league_lags_only_if_the_rest_of_its_group_played_meanwhile() -> None:
    """Milli arada grup bütünüyle durur (gecikme değil ara); başka ligi oynadıysa gecikmedir."""
    wednesday = date(2026, 9, 9)
    decided = datetime.combine(wednesday + timedelta(days=6), time(11), tzinfo=UTC)

    def league(code: str, days: list[date]) -> list[HistMatch]:
        return [
            hist_match(day=day, league=code, home=f"{code} {i}", away=f"{code} k{i}", line=i)
            for i, day in enumerate(days)
        ]

    lower = league("E1", _twice_weekly(wednesday))
    paused = league("E0", _twice_weekly(wednesday))
    played = league("E0", [*_twice_weekly(wednesday), wednesday + timedelta(days=3)])

    assert lagging_leagues([*lower, *paused], decided) == ()
    assert lagging_leagues([*lower, *played], decided) == ("E1",)


def test_a_ledger_league_resting_through_a_break_is_not_judged_lagging() -> None:
    """R153 (R141'in kapsamı): defterdeki lig (E0) milli arada 14 gün dinlenirken defterde olmayan
    E1 oynadı; E0'ı katman (a) `is_stale` doğrular, katman (b) onu yargılamaz."""
    last = date(2026, 9, 5)
    decided_on = last + timedelta(days=14)

    def league(code: str, days: list[date]) -> list[HistMatch]:
        return [
            hist_match(day=day, league=code, home=f"{code} {i}", away=f"{code} k{i}", line=i)
            for i, day in enumerate(days)
        ]

    top = league("E0", [last - timedelta(weeks=week) for week in range(20)])
    lower = league("E1", [last + timedelta(weeks=1) - timedelta(weeks=week) for week in range(20)])
    group = sorted([*top, *lower], key=lambda m: (m.date, m.league))
    kickoff = datetime.combine(decided_on, time(14), tzinfo=UTC)
    live = LiveMatch("dinlenen", LEAGUE_ID, kickoff, "E0 0", "E0 k0")
    decided = decision_at(decided_on, kickoff)
    assert decided is not None
    quotes = [
        Quote(live.match_id, decided, "b1", "h2h", name, price)
        for name, price in (("E0 0", 2.0), ("Draw", 3.4), ("E0 k0", 3.8))
    ]

    batch = build_batch(
        (live,),
        quotes,
        {"Ülke": group},
        now=decided + timedelta(minutes=30),
        naming=naming_from({"E0": top, "E1": lower}, {LEAGUE_ID: "E0"}, {}),
        kinds=KINDS,
        rating_groups=MappingProxyType({"E0": "Ülke", "E1": "Ülke"}),
    )

    assert batch.stale == () and len(batch.decisions) == 1
    assert lagging_leagues(group, decided) == ("E0",)  # defter bilinmeden: eski davranış
    assert lagging_leagues(group, decided, ledger=frozenset({"E0"})) == ()
