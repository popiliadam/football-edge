"""Harness: bağlam/sonuç ayrımı, olay sırası, sızıntı savunması, sayımlar."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import UTC, date, datetime, time, timedelta
from types import MappingProxyType

import pytest

from football_edge.backtest import harness
from football_edge.backtest.context import DuplicateMatch
from football_edge.backtest.events import DECISION, RESULT, Event
from football_edge.backtest.harness import (
    DecisionContext,
    LeakageError,
    MatchKey,
    Outcome,
    Prediction,
    ResultRecord,
    replay,
)
from football_edge.backtest.timeline import result_known_at
from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, RESULTS, TOTALS_25, HistMatch
from tests.backtest_builders import hist_match, quote

FRIDAY_NOON_BST = datetime(2024, 8, 9, 11, tzinfo=UTC)
FULL_ODDS = {
    **quote("Avg", PRE_CLOSING, (2.6, 3.3, 2.8)),
    **quote("Avg", CLOSING, (1.9, 3.6, 4.2)),
    **quote("PS", CLOSING, (1.8, 3.7, 4.6)),
    **quote("Avg", PRE_CLOSING, (1.9, 1.95), market=TOTALS_25),
    **quote("Avg", CLOSING, (1.8, 2.05), market=TOTALS_25),
    # Uydurma üçüncü evre: iki evreyle "== evre" süzgeci "!= öbür evre"den ayırt edilemezdi.
    **quote("Avg", "live", (2.2, 3.4, 3.5)),
}


@dataclass(frozen=True)
class Recorder:
    """Her kararda o ana kadar gördüğü sonuçları ve aldığı bağlamı kaydeder.

    `known`, gözlenen her sonucun `known_at`ını (ev, deplasman) çiftiyle tutar.
    """

    seen: dict[int, tuple[tuple[str, str], ...]]
    contexts: dict[int, DecisionContext]
    known: dict[tuple[str, str], datetime]
    predict_for: frozenset[int] | None = None
    observed: tuple[tuple[str, str], ...] = ()

    @property
    def name(self) -> str:
        return "recorder"

    def observe(self, result: ResultRecord) -> Recorder:
        self.known[(result.home, result.away)] = result.known_at
        return replace(self, observed=(*self.observed, (result.home, result.away)))

    def predict(self, context: DecisionContext) -> Prediction | None:
        self.seen[context.match_index] = self.observed
        self.contexts[context.match_index] = context
        if self.predict_for is not None and context.match_index not in self.predict_for:
            return None
        return Prediction(context.match_index, self.name, (0.5, 0.3, 0.2))


@dataclass(frozen=True)
class Counter:
    """Gördüğü sonuç sayısını tahmininin ilk olasılığına yazar."""

    count: int = 0

    @property
    def name(self) -> str:
        return "counter"

    def observe(self, result: ResultRecord) -> Counter:
        return Counter(self.count + 1)

    def predict(self, context: DecisionContext) -> Prediction:
        return Prediction(context.match_index, self.name, (float(self.count), 0.0, 0.0))


@dataclass(frozen=True)
class Logged:
    """Her çağrıyı ortak bir günlüğe yazar."""

    log: list[str]

    @property
    def name(self) -> str:
        return "logged"

    def observe(self, result: ResultRecord) -> Logged:
        self.log.append("observe")
        return self

    def predict(self, context: DecisionContext) -> Prediction:
        self.log.append("predict")
        return Prediction(context.match_index, self.name, (0.4, 0.3, 0.3))


@dataclass(frozen=True)
class Stray:
    """Her kararda 0. maç için tahmin döndüren bozuk strateji.

    Tahmin VAR OLAN bir maça gider: koruma kalksa hata çıkmaz, değerlendirme o tahmini sessizce
    yanlış maçın sonucuyla eşlerdi.
    """

    @property
    def name(self) -> str:
        return "stray"

    def observe(self, result: ResultRecord) -> Stray:
        return self

    def predict(self, context: DecisionContext) -> Prediction:
        return Prediction(0, self.name, (0.4, 0.3, 0.3))


def _recorder(predict_for: frozenset[int] | None = None) -> Recorder:
    return Recorder(seen={}, contexts={}, known={}, predict_for=predict_for)


def _weekly(count: int) -> tuple[HistMatch, ...]:
    """Ardışık cumartesiler 14:00 UTC: her cuma kararı bir önceki haftanın sonucunu görür."""
    days = [date(2024, 8, 3) + timedelta(weeks=week) for week in range(count)]
    return tuple(
        hist_match(
            day=day,
            kickoff=datetime.combine(day, time(14), tzinfo=UTC),
            home=f"Ev {index}",
            away=f"Konuk {index}",
            line=index + 1,
        )
        for index, day in enumerate(days)
    )


@pytest.mark.leakage
def test_the_context_type_has_no_field_for_closing_prices_or_the_result() -> None:
    assert {field.name for field in fields(DecisionContext)} == {
        "match_index",
        "league",
        "season",
        "date",
        "home",
        "away",
        "decision_at",
        "pre_prices",
    }


@pytest.mark.leakage
def test_results_and_outcomes_are_separate_records() -> None:
    assert {field.name for field in fields(ResultRecord)} == {
        "league",
        "date",
        "home",
        "away",
        "home_goals",
        "away_goals",
        "known_at",
    }
    assert {field.name for field in fields(Outcome)} == {
        "match_index",
        "result",
        "home_goals",
        "away_goals",
        "closing",
    }


@pytest.mark.leakage
def test_a_decision_context_carries_only_pre_closing_prices() -> None:
    match = hist_match(
        day=date(2024, 8, 10),
        kickoff=datetime(2024, 8, 10, 14, tzinfo=UTC),
        season="2425",
        home="Alfa",
        away="Beta",
        odds=FULL_ODDS,
    )
    recorder = _recorder()

    replay((match,), recorder)

    context = recorder.contexts[0]
    # Faz 3 (R98 eşitliği): yalnız canlı defterin de üretebildiği `Avg` 1X2 kapanış öncesi fiyatı.
    assert dict(context.pre_prices) == {
        key: price
        for key, price in FULL_ODDS.items()
        if key.phase == PRE_CLOSING and key.book == "Avg" and key.market == H2H
    }
    assert len(context.pre_prices) == 3
    assert isinstance(context.pre_prices, MappingProxyType)
    assert (context.league, context.season, context.date) == ("E0", "2425", date(2024, 8, 10))
    assert (context.home, context.away, context.decision_at) == ("Alfa", "Beta", FRIDAY_NOON_BST)


@pytest.mark.leakage
def test_outcomes_hold_only_closing_prices_and_only_for_predicted_matches() -> None:
    kickoff = datetime(2024, 8, 10, 14, tzinfo=UTC)
    matches = (
        hist_match(day=date(2024, 8, 10), kickoff=kickoff, goals=(2, 1), odds=FULL_ODDS),
        hist_match(
            day=date(2024, 8, 10),
            kickoff=kickoff,
            home="Gama",
            away="Delta",
            goals=(0, 0),
            odds=FULL_ODDS,
            line=2,
        ),
    )

    result = replay(matches, _recorder(predict_for=frozenset({0})))

    assert set(result.outcomes) == {0}
    outcome = result.outcomes[0]
    assert dict(outcome.closing) == {
        key: price for key, price in FULL_ODDS.items() if key.phase == CLOSING
    }
    assert (outcome.match_index, outcome.result, outcome.home_goals, outcome.away_goals) == (
        0,
        "H",
        2,
        1,
    )
    assert isinstance(result.outcomes, MappingProxyType)
    assert isinstance(outcome.closing, MappingProxyType)


@pytest.mark.leakage
def test_outcomes_are_built_only_after_every_prediction_is_frozen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[str] = []
    real = harness._outcome

    def spy(index: int, match: HistMatch) -> Outcome:
        log.append("outcome")
        return real(index, match)

    monkeypatch.setattr(harness, "_outcome", spy)

    replay(_weekly(3), Logged(log))

    assert log.count("predict") == 3
    assert log[-3:] == ["outcome"] * 3
    assert "outcome" not in log[:-3]


@pytest.mark.leakage
def test_a_result_known_exactly_at_a_decision_is_not_seen_by_that_decision() -> None:
    matches = (
        # cuma 09:00 BST başlıyor: sonucu tam cuma 12:00 BST'de bilinir
        hist_match(
            day=date(2024, 8, 9),
            kickoff=datetime(2024, 8, 9, 8, tzinfo=UTC),
            home="Gama",
            away="Delta",
        ),
        # cumartesi maçı: kararı tam cuma 12:00 BST
        hist_match(
            day=date(2024, 8, 10),
            kickoff=datetime(2024, 8, 10, 14, tzinfo=UTC),
            home="Alfa",
            away="Beta",
            line=2,
        ),
        # salı maçı: kararı ikisinin sonucundan da sonra
        hist_match(
            day=date(2024, 8, 13),
            kickoff=datetime(2024, 8, 13, 18, 45, tzinfo=UTC),
            home="Beta",
            away="Gama",
            line=3,
        ),
    )
    recorder = _recorder()

    replay(matches, recorder)

    assert recorder.seen[1] == ()
    assert recorder.seen[2] == (("Gama", "Delta"), ("Alfa", "Beta"))
    assert recorder.known == {
        (match.home, match.away): result_known_at(match.date, match.kickoff) for match in matches
    }


@pytest.mark.leakage
@pytest.mark.parametrize(
    "delay",
    [timedelta(0), timedelta(seconds=1), timedelta(days=1)],
    ids=["same-instant", "one-second-later", "one-day-later"],
)
def test_the_walk_refuses_a_result_that_was_not_known_before_the_decision(
    delay: timedelta,
) -> None:
    matches = (hist_match(day=date(2024, 8, 9)), hist_match(day=date(2024, 8, 10), line=2))
    events = (Event(FRIDAY_NOON_BST + delay, RESULT, 0), Event(FRIDAY_NOON_BST, DECISION, 1))

    with pytest.raises(LeakageError):
        harness._walk(matches, events, _recorder())


@pytest.mark.leakage
def test_the_walk_lets_a_decision_see_a_result_known_strictly_before_it() -> None:
    matches = (hist_match(day=date(2024, 8, 9)), hist_match(day=date(2024, 8, 10), line=2))
    events = (
        Event(FRIDAY_NOON_BST - timedelta(microseconds=1), RESULT, 0),
        Event(FRIDAY_NOON_BST, DECISION, 1),
    )
    recorder = _recorder()

    predictions, skipped = harness._walk(matches, events, recorder)

    assert recorder.seen[1] == (("Alfa", "Beta"),)
    assert ([prediction.match_index for prediction in predictions], skipped) == ([1], 0)


@pytest.mark.leakage
def test_the_walk_remembers_the_latest_result_not_the_last_one_seen() -> None:
    matches = tuple(hist_match(day=date(2024, 8, 9), line=line) for line in (1, 2, 3))
    events = (
        Event(FRIDAY_NOON_BST + timedelta(days=1), RESULT, 0),
        Event(FRIDAY_NOON_BST - timedelta(hours=1), RESULT, 1),
        Event(FRIDAY_NOON_BST, DECISION, 2),
    )

    with pytest.raises(LeakageError):
        harness._walk(matches, events, _recorder())


def test_replay_threads_the_strategy_value_that_observe_returns() -> None:
    result = replay(_weekly(4), Counter())

    assert [prediction.probs[0] for prediction in result.predictions] == [0.0, 1.0, 2.0, 3.0]


def test_replay_counts_matches_without_a_decision_and_decisions_without_a_prediction() -> None:
    matches = (
        hist_match(day=date(2024, 8, 9), kickoff=datetime(2024, 8, 9, 10, tzinfo=UTC)),
        hist_match(day=date(2024, 8, 10), kickoff=datetime(2024, 8, 10, 14, tzinfo=UTC), line=2),
        hist_match(day=date(2024, 8, 11), kickoff=datetime(2024, 8, 11, 15, tzinfo=UTC), line=3),
    )

    result = replay(matches, _recorder(predict_for=frozenset({1})))

    assert (result.strategy, result.no_decision, result.no_prediction) == ("recorder", 1, 1)
    assert [prediction.match_index for prediction in result.predictions] == [1]


def test_a_prediction_for_another_match_is_refused() -> None:
    with pytest.raises(ValueError, match="başka bir"):
        replay(_weekly(2), Stray())


def test_predictions_follow_decision_order_not_input_order() -> None:
    result = replay(tuple(reversed(_weekly(3))), _recorder())

    assert [prediction.match_index for prediction in result.predictions] == [2, 1, 0]


def test_an_empty_history_replays_to_nothing() -> None:
    result = replay((), _recorder())

    assert (result.predictions, dict(result.outcomes)) == ((), {})
    assert (result.no_decision, result.no_prediction) == (0, 0)


# ── Harness kanaryası (R120): sonuç kullanan strateji dürüst harness'ta hiç tahmin üretmez ──


@dataclass(frozen=True)
class Oracle:
    """Gördüğü sonuçları kullanır: karar verdiği maçın sonucunu gördüyse kazananı tahmin eder.

    Yalnız o durumda tahmin döner; her tahmini harness'ın karar anından ÖNCE açtığı bir sonuca
    dayanır. K4 (Placebo, CLV) bu sızıntıyı göremez: Placebo sonucu yok sayar, CLV sonuçtan
    bağımsızdır (T11 F2).
    """

    seen: tuple[ResultRecord, ...] = ()

    @property
    def name(self) -> str:
        return "oracle"

    def observe(self, result: ResultRecord) -> Oracle:
        return replace(self, seen=(*self.seen, result))

    def predict(self, context: DecisionContext) -> Prediction | None:
        own = (context.league, context.date, context.home, context.away)
        leaked = next((r for r in self.seen if (r.league, r.date, r.home, r.away) == own), None)
        if leaked is None:
            return None
        diff = leaked.home_goals - leaked.away_goals
        winner = "H" if diff > 0 else "A" if diff < 0 else "D"
        probs = tuple(0.9 if outcome == winner else 0.05 for outcome in RESULTS)
        return Prediction(context.match_index, self.name, (probs[0], probs[1], probs[2]))


# Haftanın maç anları (cumartesiden gün farkı, UTC başlama; None = saatsiz). Hafta sonu kararı
# cuma, hafta içi kararı salı 12:00 Londra; gece yarısı çevresi ve saatsiz maçlar sonucu
# kararlara en yakın taşıyan anlardır.
_SLOTS: tuple[tuple[int, time | None], ...] = (
    (-1, time(19, 45)),  # cuma akşamı
    (0, time(14)),
    (0, time(23, 45)),  # cumartesi gece yarısına 15 dk
    (1, None),  # pazar, saatsiz: ertesi gün 03:00'te bilinir
    (2, time(0, 30)),  # pazartesi 00:30
    (3, time(18, 45)),  # salı akşamı
    (4, time(23, 30)),  # çarşamba gece
    # 14k: karar anına (11:00 UTC, BST) 1 sa 15 dk kala başlayan cuma ve salı maçları; sonucu
    # 4 sa erken sızdıran bir harness'ı yalnız bu iki yuva yakalar.
    (-1, time(12, 15)),  # cuma öğlen
    (3, time(12, 15)),  # salı öğlen
)
_CANARY_LEAGUES = ("E0", "SP1", "BRA")


def _canary_schedule(weeks: int = 12) -> tuple[HistMatch, ...]:
    """Üç lig × `weeks` hafta × yedi an; giriş sırası lig lig (olay sırası değil)."""
    first = date(2024, 8, 10)
    return tuple(
        hist_match(
            day=(day := first + timedelta(weeks=week, days=offset)),
            kickoff=None if kick is None else datetime.combine(day, kick, tzinfo=UTC),
            league=league,
            home=f"{league} Ev {week}-{slot}",
            away=f"{league} Konuk {week}-{slot}",
            goals=((1, 0), (1, 1), (0, 2))[(week + slot) % 3],
            line=week * len(_SLOTS) + slot + 1,
        )
        for league in _CANARY_LEAGUES
        for week in range(weeks)
        for slot, (offset, kick) in enumerate(_SLOTS)
    )


@pytest.mark.leakage
def test_the_oracle_predicts_once_it_has_seen_the_match_result() -> None:
    """Kanaryanın kendisi kör değil: sonucu gördüğü maçta tahmin eder, kazananı doğru bilir."""
    match = _canary_schedule(weeks=1)[2]  # deplasman galibiyeti (0-2)
    context = harness._context(0, match, FRIDAY_NOON_BST)

    assert Oracle().predict(context) is None
    prediction = Oracle().observe(harness._result_record(match, FRIDAY_NOON_BST)).predict(context)
    assert prediction is not None and prediction.probs == (0.05, 0.05, 0.9)


@pytest.mark.leakage
def test_an_oracle_that_uses_results_gets_no_prediction_from_the_honest_harness() -> None:
    """Harness'ın gerçek kanaryası (R120, judge-selftest ilkesi): bir karardan önce kendi maçının
    sonucu açılırsa Oracle tahmin eder. Dürüst harness'ta tahmin 0; `build_events` sonuçları öne
    alacak biçimde yamalanınca her karar tahmine döner (T11 S8: 1.200 tahmin, log loss 0,105)."""
    schedule = _canary_schedule()

    result = replay(schedule, Oracle())
    earlier = replay(schedule, Counter())

    assert result.predictions == (), f"{len(result.predictions)} karar sonucunu önceden gördü"
    # Boş geçmesin: her maçın kararı var ve Oracle'a ulaştı; başka maçların sonuçları kararlardan
    # önce gerçekten açılıyor — Oracle bir sonucu görmediği için değil, kendi maçınınkini
    # görmediği için susuyor.
    assert (result.no_decision, result.no_prediction) == (0, len(schedule))
    assert sum(prediction.probs[0] > 0 for prediction in earlier.predictions) > len(schedule) // 2


@pytest.mark.leakage
def test_replay_refuses_the_same_match_twice() -> None:
    """14g/14r: aynı (lig, tarih, ev, deplasman) iki kez → iki karar ve çift durum güncellemesi."""
    day = date(2024, 8, 10)
    kickoff = datetime(2024, 8, 10, 14, tzinfo=UTC)
    twice = (hist_match(day=day, kickoff=kickoff), hist_match(day=day, kickoff=kickoff, line=2))

    with pytest.raises(DuplicateMatch, match="yinelenen maç"):
        replay(twice, _recorder())


def test_the_context_key_is_the_match_identity() -> None:
    match = hist_match(day=date(2024, 8, 10), kickoff=datetime(2024, 8, 10, 14, tzinfo=UTC))

    context = harness._context(4, match, FRIDAY_NOON_BST)

    assert context.key == MatchKey("E0", date(2024, 8, 10), "Alfa", "Beta")


@pytest.mark.leakage
def test_the_context_carries_only_prices_the_live_ledger_can_rebuild() -> None:
    """R98 eşitliği (Faz 3): canlı defter yalnız kitap ortalaması 1X2 kurar; başka kitap ya da
    market bağlama girerse canlı bağlam onu taşıyamaz."""
    odds = {
        **quote("Avg", PRE_CLOSING, (2.6, 3.3, 2.8)),
        **quote("Max", PRE_CLOSING, (2.8, 3.6, 3.1)),
        **quote("Avg", PRE_CLOSING, (1.9, 1.95), market=TOTALS_25),
    }
    match = hist_match(
        day=date(2024, 8, 10), kickoff=datetime(2024, 8, 10, 14, tzinfo=UTC), odds=odds
    )

    context = harness._context(0, match, FRIDAY_NOON_BST)

    assert dict(context.pre_prices) == quote("Avg", PRE_CLOSING, (2.6, 3.3, 2.8))
