"""Kademe 1 koşucusu (spec §6, §9; R164): sahte Jev, ağ yok, para yok."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from football_edge.features import __main__ as cli
from football_edge.features.news import NewsDraft, news_hash, write_news
from football_edge.features.questions import (
    CLUSTER_QUESTION,
    CONFLICT_QUESTION,
    MATCH_QUESTION,
    NEW_EVENT,
    RELIABILITY_QUESTION,
    QuestionSet,
    load_questions,
)
from football_edge.features.tier1 import (
    FAILED_PREFIX,
    HORIZON,
    MAX_ATTEMPTS,
    MAX_FIXTURES,
    ItemAnswerRow,
    asked_item_ids,
    candidate_fixtures,
    gates_from,
    load_fixtures,
    run_tier1,
    write_item_answers,
)
from football_edge.features.types import AWAY, BOTH, HOME, OBSERVED, StoredNews
from football_edge.jev import NO_MATCH, BatteryAnswer, ChoiceAnswer, Question
from football_edge.jev_budget import EXIT_BUDGET, BudgetExceeded
from football_edge.live.context import LiveMatch
from tests.fake_jev import FakeBatteryJev
from tests.fake_news_db import FakeNewsDb

REPO = Path(__file__).resolve().parent.parent
QUESTIONS = load_questions(REPO / "config" / "jev_questions.yaml")
T0 = datetime(2026, 9, 20, 9, 30, tzinfo=UTC)
ASKED = T0 + timedelta(minutes=5)
LEAGUE = "soccer_turkey_super_league"
DERBY = LiveMatch("m-gs", LEAGUE, T0 + timedelta(days=2), "Galatasaray", "Fenerbahce")
BJK = LiveMatch("m-bjk", LEAGUE, T0 + timedelta(days=3), "Besiktas JK", "Trabzonspor")
FIXTURES = (DERBY, BJK)


def news(item_id: int, title: str, available_at: datetime = T0) -> StoredNews:
    url = f"https://ajansspor.com/haber/{item_id}"
    return StoredNews(
        item_id=item_id,
        source_id="ajansspor",
        lang="tr",
        title=title,
        body=None,
        url=url,
        published_at_claimed=available_at,
        available_at=available_at,
        availability_basis=OBSERVED,
        content_hash=news_hash("ajansspor", url, title, None),
    )


def run(
    items: Sequence[StoredNews],
    client: Any,
    *,
    history: Sequence[StoredNews] = (),
    fixtures: Sequence[LiveMatch] = FIXTURES,
    questions: QuestionSet = QUESTIONS,
    attempts: Mapping[int, int] | None = None,
) -> Any:
    return run_tier1(
        items,
        client,
        questions,
        fixtures=fixtures,
        clock=lambda: ASKED,
        history=history,
        attempts=attempts or {},
    )


# ── Adaylar ────────────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_candidates_start_after_the_news_and_within_eight_days() -> None:
    item = news(1, "Galatasaray'da son durum")
    fixtures = [
        LiveMatch("at-news", LEAGUE, T0, "Galatasaray", "Kasimpasa SK"),
        LiveMatch("past", LEAGUE, T0 - timedelta(hours=1), "Galatasaray", "Rizespor"),
        LiveMatch("edge", LEAGUE, T0 + HORIZON, "Galatasaray", "Goztepe"),
        LiveMatch("late", LEAGUE, T0 + HORIZON + timedelta(seconds=1), "Galatasaray", "Konyaspor"),
    ]

    assert [f.match_id for f in candidate_fixtures(item, fixtures)] == ["edge"]


def test_only_fixtures_whose_team_is_named_are_candidates() -> None:
    assert candidate_fixtures(news(1, "Trabzonspor'da kriz"), FIXTURES) == (BJK,)
    assert candidate_fixtures(news(2, "Hava durumu"), FIXTURES) == ()


def test_fixtures_naming_both_teams_come_first_then_by_kickoff() -> None:
    later_derby = LiveMatch("m-2", LEAGUE, T0 + timedelta(days=4), "Fenerbahce", "Galatasaray")
    item = news(1, "Galatasaray ve Fenerbahçe derbiye hazır")
    many = [*FIXTURES, later_derby] + [
        LiveMatch(f"x{n}", LEAGUE, T0 + timedelta(hours=n), "Galatasaray", f"Rakip{n}")
        for n in range(1, 10)
    ]

    found = candidate_fixtures(item, many)

    assert [f.match_id for f in found[:2]] == ["m-gs", "m-2"]
    assert len(found) == MAX_FIXTURES


def test_a_generic_word_alone_does_not_make_a_candidate() -> None:
    fixture = LiveMatch(
        "m-ibfk", LEAGUE, T0 + timedelta(days=1), "Istanbul Basaksehir", "Alanyaspor"
    )

    assert candidate_fixtures(news(1, "İstanbul'da yağmur bekleniyor"), [fixture]) == ()
    assert candidate_fixtures(news(2, "Başakşehir'de sakatlık"), [fixture]) == (fixture,)


# ── Koşucu ─────────────────────────────────────────────────────────────────────────────────


def test_an_item_gets_one_battery_with_code_built_options() -> None:
    client = FakeBatteryJev(
        choices={MATCH_QUESTION: "m-gs:home", RELIABILITY_QUESTION: "official"}, cost_usd=0.002
    )

    result = run([news(1, "Galatasaray'da sakatlık şoku")], client)

    (call,) = client.seen
    assert call["question_ids"] == (MATCH_QUESTION, RELIABILITY_QUESTION)
    assert call["state"]["news"]["title"] == "Galatasaray'da sakatlık şoku"
    assert [f["home"] for f in call["state"]["fixtures"]] == ["Galatasaray"]
    assert [(r.question_id, r.choice, r.match_id) for r in result.rows] == [
        (MATCH_QUESTION, "m-gs:home", "m-gs"),
        (RELIABILITY_QUESTION, "official", "m-gs"),
    ]
    assert {r.asked_at for r in result.rows} == {ASKED}
    assert {r.prompt_version for r in result.rows} == {QUESTIONS.prompt_version}
    assert sum(r.cost_usd for r in result.rows) == pytest.approx(0.002)
    assert (result.asked, result.failed, result.no_candidate, result.budget_hit) == (2, 0, 0, False)


def test_the_match_question_offers_three_sides_per_fixture_and_no_match() -> None:
    captured: list[Question] = []

    @dataclass
    class Capturing(FakeBatteryJev):
        def ask_battery(
            self, state: Mapping[str, Any], questions: Sequence[Question]
        ) -> BatteryAnswer:
            captured.extend(questions)
            return super().ask_battery(state, questions)

    run([news(1, "Galatasaray - Fenerbahçe derbisi öncesi")], Capturing())

    assert list(captured[0].criteria) == [
        "m-gs:home",
        "m-gs:away",
        "m-gs:both",
        NO_MATCH,
    ]


def test_news_without_a_candidate_is_not_asked() -> None:
    client = FakeBatteryJev()

    result = run([news(1, "Transfer döneminde son gün")], client)

    assert client.seen == []
    assert (result.rows, result.asked, result.no_candidate) == ((), 0, 1)


def test_earlier_news_about_the_same_teams_adds_cluster_and_conflict_questions() -> None:
    earlier = news(1, "Galatasaray'da Icardi sakat", T0 - timedelta(hours=5))
    stale = news(2, "Galatasaray'da eski haber", T0 - timedelta(hours=80))
    unrelated = news(3, "Konyaspor'da hoca değişti", T0 - timedelta(hours=1))
    client = FakeBatteryJev(choices={CLUSTER_QUESTION: "item:1"})

    result = run(
        [news(4, "Galatasaray'da Icardi derbide yok")], client, history=[earlier, stale, unrelated]
    )

    (call,) = client.seen
    assert call["question_ids"] == (
        MATCH_QUESTION,
        CLUSTER_QUESTION,
        CONFLICT_QUESTION,
        RELIABILITY_QUESTION,
    )
    assert [e["id"] for e in call["state"]["earlier_news"]] == ["item:1"]
    assert {r.question_id: r.choice for r in result.rows}[CLUSTER_QUESTION] == "item:1"


def test_items_of_the_same_run_are_asked_in_time_order_and_can_cluster() -> None:
    first = news(1, "Galatasaray'da sakatlık", T0)
    second = news(2, "Galatasaray'da sakatlık sürüyor", T0 + timedelta(hours=1))
    client = FakeBatteryJev()

    run([second, first], client)

    assert [len(call["state"]["earlier_news"]) for call in client.seen] == [0, 1]


def test_a_choice_outside_the_offered_options_is_a_failure_not_a_row() -> None:
    """Maç cevabı geçersizse haber HİÇ satır almaz: öbür satırlar onu "sorulmuş" gösterirdi."""
    client = FakeBatteryJev(choices={MATCH_QUESTION: "m-baska:home"})

    result = run([news(1, "Galatasaray'da sakatlık")], client)

    assert result.rows == ()
    assert (result.asked, result.failed) == (2, 2)


def test_a_missing_answer_is_counted_as_failed() -> None:
    client = FakeBatteryJev(missing=frozenset({RELIABILITY_QUESTION}))

    result = run([news(1, "Galatasaray'da sakatlık")], client)

    assert [r.question_id for r in result.rows] == [MATCH_QUESTION]
    assert (result.asked, result.failed) == (2, 1)


def test_cost_is_shared_per_asked_question_not_per_valid_answer() -> None:
    """Satır maliyeti soru başınadır; cevapsız sorunun payı satırsız kalır, toplam `jev_spend`te."""
    item = news(1, "Galatasaray'da sakatlık")
    full = run([item], FakeBatteryJev(cost_usd=0.004))
    partial = run([item], FakeBatteryJev(cost_usd=0.004, missing=frozenset({RELIABILITY_QUESTION})))

    assert sum(r.cost_usd for r in full.rows) == pytest.approx(0.004)
    assert [r.cost_usd for r in partial.rows] == [pytest.approx(0.002)]


def test_a_jev_error_drops_that_item_only(caplog: pytest.LogCaptureFixture) -> None:
    @dataclass
    class FailsFirst(FakeBatteryJev):
        calls: int = 0

        def ask_battery(
            self, state: Mapping[str, Any], questions: Sequence[Question]
        ) -> BatteryAnswer:
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("jev zaman aşımı")
            return super().ask_battery(state, questions)

    items = [
        news(1, "Galatasaray'da sakatlık", T0),
        news(2, "Trabzonspor'da kriz", T0 + timedelta(minutes=1)),
    ]

    result = run(items, FailsFirst())

    assert {r.item_id for r in result.rows} == {2}
    assert (result.asked, result.failed, result.budget_hit) == (4, 2, False)
    assert "haber 1 sorulamadı" in caplog.text


def test_the_budget_stops_the_run_and_keeps_the_answers_already_paid_for() -> None:
    @dataclass
    class BudgetAfterOne(FakeBatteryJev):
        calls: int = 0

        def ask_battery(
            self, state: Mapping[str, Any], questions: Sequence[Question]
        ) -> BatteryAnswer:
            self.calls += 1
            if self.calls > 1:
                raise BudgetExceeded("tavan")
            return super().ask_battery(state, questions)

    items = [
        news(1, "Galatasaray'da sakatlık", T0),
        news(2, "Trabzonspor'da kriz", T0 + timedelta(minutes=1)),
    ]

    result = run(items, BudgetAfterOne())

    assert {r.item_id for r in result.rows} == {1}
    assert (result.asked, result.budget_hit) == (2, True)


# ── Yeniden deneme sınırı (son inceleme I-3) ─────────────────────────────────────────────────


@dataclass
class FailsFor(FakeBatteryJev):
    """Başlığı `failing`de olan haberin çağrısı `raises` ile patlar; öbürleri cevap alır."""

    failing: frozenset[str] = frozenset()
    raises: Exception = field(default_factory=lambda: RuntimeError("jev hatası"))

    def ask_battery(self, state: Mapping[str, Any], questions: Sequence[Question]) -> BatteryAnswer:
        if state["news"]["title"] in self.failing:
            self.seen = [*self.seen, {"state": dict(state), "question_ids": ()}]
            raise self.raises
        return super().ask_battery(state, questions)


def test_a_failed_battery_leaves_a_numbered_failure_marker_not_an_answer() -> None:
    """Deneme sayısı koşular arasında `jev_item_answers`teki numaralı işaretlerden okunur.

    Koşuda cevap alan bir haber daha vardır: hepsi hatayla düşen koşu kesintidir, işaret bırakmaz.
    """
    client = FailsFor(
        failing=frozenset({"Galatasaray'da sakatlık"}), raises=RuntimeError("400 bad request")
    )
    items = [news(1, "Galatasaray'da sakatlık"), news(2, "Trabzonspor'da kriz")]

    result = run(items, client, attempts={1: 1})

    assert {r.item_id for r in result.rows} == {2}
    (marker,) = result.failures
    assert (marker.item_id, marker.question_id, marker.choice, marker.match_id) == (
        1,
        f"{FAILED_PREFIX}2",
        "jev_error:RuntimeError",
        None,
    )
    assert (dict(marker.probabilities), marker.confidence, marker.cost_usd) == ({}, 0.0, 0.0)
    assert marker.prompt_version == QUESTIONS.prompt_version


def test_an_invalid_match_answer_leaves_a_failure_marker() -> None:
    client = FakeBatteryJev(choices={MATCH_QUESTION: "m-baska:home"})

    result = run([news(1, "Galatasaray'da sakatlık")], client)

    assert result.rows == ()
    assert [(m.question_id, m.choice, m.jev_model) for m in result.failures] == [
        (f"{FAILED_PREFIX}1", "match_invalid", "jev-fake")
    ]


def test_an_item_that_failed_max_attempts_times_is_not_bought_again() -> None:
    client = FakeBatteryJev()
    items = [
        news(1, "Galatasaray'da sakatlık", T0),
        news(2, "Trabzonspor'da kriz", T0 + timedelta(minutes=1)),
    ]

    result = run(items, client, attempts={1: MAX_ATTEMPTS, 2: MAX_ATTEMPTS - 1})

    assert [call["state"]["news"]["title"] for call in client.seen] == ["Trabzonspor'da kriz"]
    assert (result.given_up, result.failures) == (1, ())
    assert {r.item_id for r in result.rows} == {2}


# ── Kesinti (DEFERRED 17b) ────────────────────────────────────────────────────────────────────


TWO = (
    news(1, "Galatasaray'da sakatlık", T0),
    news(2, "Trabzonspor'da kriz", T0 + timedelta(minutes=1)),
)


def test_a_run_where_every_asked_item_hits_a_jev_error_is_an_outage_without_markers() -> None:
    """Jev çökükse düşüş haberin değil kesintinin sonucudur: işaret üç koşuda kapsamı yakardı."""
    result = run(TWO, FakeBatteryJev(error=ConnectionError("jev kapalı")))

    assert result.outage is True
    assert (result.rows, result.failures) == ((), ())
    assert (result.asked, result.failed, result.budget_hit) == (4, 4, False)


def test_a_mixed_run_marks_the_errored_item_as_before() -> None:
    client = FailsFor(failing=frozenset({TWO[0].title}), raises=TimeoutError("zaman aşımı"))

    result = run(TWO, client)

    assert result.outage is False
    assert {r.item_id for r in result.rows} == {2}
    assert [(m.item_id, m.choice) for m in result.failures] == [(1, "jev_error:TimeoutError")]


def test_an_all_invalid_run_is_not_an_outage() -> None:
    """Geçersiz cevap Jev'in çalıştığını gösterir: işaret bugünkü gibi yazılır."""
    result = run(TWO, FakeBatteryJev(choices={MATCH_QUESTION: "m-baska:home"}))

    assert result.outage is False
    assert [(m.item_id, m.choice) for m in result.failures] == [
        (1, "match_invalid"),
        (2, "match_invalid"),
    ]


def test_an_error_beside_an_invalid_answer_is_not_an_outage() -> None:
    client = FailsFor(
        choices={MATCH_QUESTION: "m-baska:home"},
        failing=frozenset({TWO[0].title}),
        raises=TimeoutError("zaman aşımı"),
    )

    result = run(TWO, client)

    assert result.outage is False
    assert [(m.item_id, m.choice) for m in result.failures] == [
        (1, "jev_error:TimeoutError"),
        (2, "match_invalid"),
    ]


def test_the_budget_stop_keeps_the_markers_of_errored_items() -> None:
    """Tavan koşuyu keser; ondan önceki hata bugünkü gibi işaretlenir, kesinti sayılmaz."""

    @dataclass
    class ErrorThenBudget(FakeBatteryJev):
        calls: int = 0

        def ask_battery(
            self, state: Mapping[str, Any], questions: Sequence[Question]
        ) -> BatteryAnswer:
            self.calls += 1
            raise TimeoutError("zaman aşımı") if self.calls == 1 else BudgetExceeded("tavan")

    result = run(TWO, ErrorThenBudget())

    assert (result.budget_hit, result.outage) == (True, False)
    assert [(m.item_id, m.choice) for m in result.failures] == [(1, "jev_error:TimeoutError")]


def test_a_run_with_nothing_asked_is_not_an_outage() -> None:
    result = run([news(1, "Transfer döneminde son gün")], FakeBatteryJev(error=RuntimeError("x")))

    assert (result.outage, result.no_candidate) == (False, 1)


def test_gates_ignore_failure_markers() -> None:
    """İşaret cevap değildir: kapıyı da `asked_at`i de (sonra yazılmış olsa bile) etkilemez."""
    answers = run([news(7, "Trabzonspor'da kriz")], FakeBatteryJev()).rows
    failed = run(
        [news(7, "Trabzonspor'da kriz")], FakeBatteryJev(choices={MATCH_QUESTION: "m-baska:home"})
    ).failures
    later = tuple(replace(m, asked_at=ASKED + timedelta(hours=1)) for m in failed)

    assert [m.item_id for m in later] == [7], "aynı haberin işareti olmalı (boş işaret sınamaz)"
    assert gates_from([*later, *answers]) == gates_from(answers)
    assert gates_from(later) == {}


@pytest.mark.leakage
def test_asked_at_is_read_after_the_answer_returns() -> None:
    """Canlıda `asked_at < decided_at` bu ana bakar: çağrıdan önceki an cevabı erken gösterirdi."""
    now = [T0]

    @dataclass
    class Slow(FakeBatteryJev):
        def ask_battery(
            self, state: Mapping[str, Any], questions: Sequence[Question]
        ) -> BatteryAnswer:
            now[0] = now[0] + timedelta(minutes=3)
            return super().ask_battery(state, questions)

    result = run_tier1(
        [news(1, "Galatasaray'da sakatlık")],
        Slow(),
        QUESTIONS,
        fixtures=FIXTURES,
        clock=lambda: now[0],
    )

    assert {r.asked_at for r in result.rows} == {T0 + timedelta(minutes=3)}


def test_unstored_news_cannot_be_asked() -> None:
    unstored = StoredNews(None, "s", "tr", "Galatasaray", None, "u", None, T0, OBSERVED, "h")

    with pytest.raises(ValueError, match="yazılmamış"):
        run([unstored], FakeBatteryJev())


# ── Kapı özeti ─────────────────────────────────────────────────────────────────────────────


def row(
    item_id: int, question_id: str, choice: str, probabilities: Mapping[str, float], **kw: Any
) -> ItemAnswerRow:
    values: dict[str, Any] = {
        "prompt_version": "p" * 64,
        "confidence": 0.8,
        "match_id": "m-gs",
        "jev_model": "jev-fake",
        "asked_at": ASKED,
        "cost_usd": 0.001,
    }
    return ItemAnswerRow(
        item_id,
        question_id=question_id,
        choice=choice,
        probabilities=probabilities,
        **{**values, **kw},
    )


def test_gate_belongs_sums_the_sides_of_the_chosen_match() -> None:
    rows = [
        row(
            1,
            MATCH_QUESTION,
            "m-gs:home",
            {"m-gs:home": 0.5, "m-gs:both": 0.2, "m-bjk:home": 0.2, NO_MATCH: 0.1},
        ),
        row(1, RELIABILITY_QUESTION, "reported", {"official": 0.3, "reported": 0.4, "rumour": 0.3}),
    ]

    gate = gates_from(rows)[1]

    assert (gate.match_id, gate.side) == ("m-gs", HOME)
    assert gate.belongs == pytest.approx(0.7)
    assert gate.reliability == pytest.approx(0.7)
    assert gate.cluster_id == "1"


def test_no_match_gives_a_gate_that_belongs_nowhere() -> None:
    gate = gates_from(
        [row(1, MATCH_QUESTION, NO_MATCH, {NO_MATCH: 0.9, "m-gs:away": 0.1}, match_id=None)]
    )[1]

    assert (gate.match_id, gate.side, gate.belongs, gate.reliability) == (None, None, 0.0, 0.0)


def test_an_item_without_a_match_answer_has_no_gate() -> None:
    assert gates_from([row(1, RELIABILITY_QUESTION, "official", {"official": 1.0})]) == {}


def test_clusters_follow_the_chain_to_the_earliest_item() -> None:
    rows = [
        row(1, MATCH_QUESTION, "m-gs:away", {"m-gs:away": 1.0}),
        row(2, MATCH_QUESTION, "m-gs:both", {"m-gs:both": 1.0}),
        row(2, CLUSTER_QUESTION, "item:1", {"item:1": 1.0}),
        row(
            3, MATCH_QUESTION, "m-gs:both", {"m-gs:both": 1.0}, asked_at=ASKED + timedelta(hours=1)
        ),
        row(3, CLUSTER_QUESTION, "item:2", {"item:2": 1.0}),
        row(4, MATCH_QUESTION, "m-gs:home", {"m-gs:home": 1.0}),
        row(4, CLUSTER_QUESTION, NEW_EVENT, {NEW_EVENT: 1.0}),
    ]

    gates = gates_from(rows)

    assert {k: g.cluster_id for k, g in gates.items()} == {1: "1", 2: "1", 3: "1", 4: "4"}
    assert (gates[1].side, gates[2].side) == (AWAY, BOTH)
    assert gates[3].asked_at == ASKED + timedelta(hours=1)


def test_a_cluster_cycle_terminates() -> None:
    rows = [
        row(1, MATCH_QUESTION, "m-gs:home", {"m-gs:home": 1.0}),
        row(1, CLUSTER_QUESTION, "item:2", {"item:2": 1.0}),
        row(2, MATCH_QUESTION, "m-gs:home", {"m-gs:home": 1.0}),
        row(2, CLUSTER_QUESTION, "item:1", {"item:1": 1.0}),
    ]

    assert {g.cluster_id for g in gates_from(rows).values()} <= {"1", "2"}


def test_gates_refuse_mixed_prompt_versions() -> None:
    rows = [
        row(1, MATCH_QUESTION, "m-gs:home", {"m-gs:home": 1.0}),
        row(2, MATCH_QUESTION, "m-gs:home", {"m-gs:home": 1.0}, prompt_version="q" * 64),
    ]

    with pytest.raises(ValueError, match="prompt_version"):
        gates_from(rows)


def test_run_rows_feed_gates_end_to_end() -> None:
    client = FakeBatteryJev(
        choices={MATCH_QUESTION: "m-bjk:away", RELIABILITY_QUESTION: "reported"}
    )

    gates = gates_from(run([news(7, "Trabzonspor'da kriz")], client).rows)

    assert (gates[7].match_id, gates[7].side, gates[7].asked_at) == ("m-bjk", AWAY, ASKED)
    # Sahte Jev: seçim 0.9, kalan 0.1 öbür üç seçeneğe eşit; maça ait = away + home + both.
    assert gates[7].belongs == pytest.approx(0.9 + 2 * 0.1 / 3)


# ── Veritabanı ve CLI ──────────────────────────────────────────────────────────────────────


# CLI testlerinde `now` = T0 + 1 sa: bu maç haberden sonra ama komuttan ÖNCE başlamıştır.
STARTED = LiveMatch("m-basladi", LEAGUE, T0 + timedelta(minutes=30), "Galatasaray", "Rizespor")


def _db_with(*items: StoredNews) -> FakeNewsDb:
    """Veritabanı saati haberlerden önce: yazılan haberin `available_at`i = iddia = kendi anı."""
    db = FakeNewsDb(now=T0 - timedelta(days=30))
    drafts = [
        NewsDraft(
            i.source_id, i.lang, i.title, i.body, i.url, i.available_at, OBSERVED, i.content_hash
        )
        for i in items
    ]
    write_news(db, drafts)  # type: ignore[arg-type]  # taklit kimlikleri 1'den sırayla verir
    db.fixtures = [
        (f.match_id, f.league_id, f.kickoff, f.home, f.away) for f in (STARTED, *FIXTURES)
    ]
    return db


def test_answers_are_written_once_and_read_back_as_asked() -> None:
    db = _db_with(news(1, "Galatasaray'da sakatlık"))
    rows = run([news(1, "Galatasaray'da sakatlık")], FakeBatteryJev()).rows

    assert write_item_answers(db, rows) == 2  # type: ignore[arg-type]
    assert write_item_answers(db, rows) == 0  # type: ignore[arg-type]
    assert asked_item_ids(db, QUESTIONS.prompt_version, [1, 2]) == {1}  # type: ignore[arg-type]
    assert asked_item_ids(db, "x" * 64, [1]) == frozenset()  # type: ignore[arg-type]


def test_load_fixtures_returns_live_matches_in_the_window() -> None:
    db = _db_with()

    found = load_fixtures(db, since=T0, until=T0 + timedelta(days=2))  # type: ignore[arg-type]

    assert found == (STARTED, DERBY)


def _cli(monkeypatch: pytest.MonkeyPatch, db: FakeNewsDb, client: Any) -> list[Any]:
    budgeted: list[Any] = []

    def _budgeted(jev: Any, spend_conn: Any, *, clock: Any) -> Any:
        budgeted.append(clock())
        return jev

    monkeypatch.setattr(cli, "connect", lambda: db)
    monkeypatch.setattr(cli, "TypeSafeJev", lambda: client)
    monkeypatch.setattr(cli, "budgeted_jev", _budgeted)
    monkeypatch.setattr(cli, "_now", lambda: T0 + timedelta(hours=1))
    return budgeted


def test_tier1_command_asks_unasked_news_writes_and_reports(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    db = _db_with(news(1, "Galatasaray'da sakatlık"), news(2, "Trabzonspor'da kriz"))
    client = FakeBatteryJev()
    budgeted = _cli(monkeypatch, db, client)

    with caplog.at_level(logging.INFO):
        code = cli.main(["tier1"])

    assert code == 0
    # Defterin autocommit'i `budgeted_jev`in kendi testinde; burada: tek sarmalayıcı, komutun saati.
    assert budgeted == [T0 + timedelta(hours=1)], "Jev tavan sarmalayıcısından geçmeli"
    assert {a["item_id"] for a in db.answers} == {1, 2}
    assert db.commits == 1
    assert "jev: soru 4 · başarısız 0" in caplog.text
    offered = [f["away"] for call in client.seen for f in call["state"]["fixtures"]]
    assert "Rizespor" not in offered, "başlamış maç aday olmamalı (cevabı hiçbir karara yetişmez)"


def test_an_invalid_match_answer_is_retried_across_runs_until_the_attempt_cap(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Geçersiz cevaptan sonra haber yeniden sorulur — ama `MAX_ATTEMPTS` koşudan sonra değil:
    her koşuda aynı haberi yeniden satın almak tavanı hayalet başarısızlıkla tüketirdi (I-3)."""
    db = _db_with(news(1, "Galatasaray'da sakatlık"))
    client = FakeBatteryJev(choices={MATCH_QUESTION: "m-baska:home"})
    _cli(monkeypatch, db, client)

    with caplog.at_level(logging.INFO):
        for _ in range(MAX_ATTEMPTS + 2):
            cli.main(["tier1"])

    assert len(client.seen) == MAX_ATTEMPTS
    assert [a["question_id"] for a in db.answers] == [
        f"{FAILED_PREFIX}{n}" for n in range(1, MAX_ATTEMPTS + 1)
    ]
    assert asked_item_ids(db, QUESTIONS.prompt_version, [1]) == frozenset()  # type: ignore[arg-type]
    assert "vazgeçilen haber 1" in caplog.text


def test_unasked_news_just_before_since_is_a_cluster_candidate_not_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`[since − 72 sa, since)` kuyruğu sorulmaz ama sonraki haberin küme adayıdır."""
    tail = news(1, "Galatasaray'da sakatlık", T0 - timedelta(hours=2))
    db = _db_with(tail, news(2, "Galatasaray'da sakatlık sürüyor"))
    client = FakeBatteryJev()
    _cli(monkeypatch, db, client)

    cli.main(["tier1", "--since", T0.isoformat()])

    (call,) = client.seen
    assert call["state"]["news"]["title"] == "Galatasaray'da sakatlık sürüyor"
    assert [e["id"] for e in call["state"]["earlier_news"]] == ["item:1"]


def test_tier1_command_skips_news_already_asked_with_this_prompt_version(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    db = _db_with(news(1, "Galatasaray'da sakatlık"), news(2, "Galatasaray'da ikinci haber"))
    first = run([news(1, "Galatasaray'da sakatlık")], FakeBatteryJev()).rows
    write_item_answers(db, first)  # type: ignore[arg-type]
    client = FakeBatteryJev()
    _cli(monkeypatch, db, client)

    with caplog.at_level(logging.INFO):
        cli.main(["tier1"])

    (call,) = client.seen
    assert call["state"]["news"]["title"] == "Galatasaray'da ikinci haber"
    assert [e["id"] for e in call["state"]["earlier_news"]] == ["item:1"]


def test_tier1_command_without_a_key_exits_by_name_before_touching_the_database(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def _explode() -> Any:
        raise AssertionError("anahtarsız komut veritabanına bağlanmamalı")

    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(cli, "connect", _explode)

    assert cli.main(["tier1"]) == cli.EXIT_NO_JEV_KEY == 17
    assert "TYPESAFE_API_KEY" in caplog.text


def test_tier1_command_on_the_budget_writes_what_was_paid_for_and_exits_by_name(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    @dataclass
    class BudgetAfterOne(FakeBatteryJev):
        calls: list[int] = field(default_factory=list)

        def ask_battery(
            self, state: Mapping[str, Any], questions: Sequence[Question]
        ) -> BatteryAnswer:
            self.calls.append(1)
            if len(self.calls) > 1:
                raise BudgetExceeded("tavan")
            return super().ask_battery(state, questions)

    db = _db_with(
        news(1, "Galatasaray'da sakatlık"),
        news(2, "Trabzonspor'da kriz", T0 + timedelta(minutes=1)),
    )
    _cli(monkeypatch, db, BudgetAfterOne())

    code = cli.main(["tier1"])

    assert code == EXIT_BUDGET == 16
    assert {a["item_id"] for a in db.answers} == {1}
    assert db.commits == 1
    assert "tavan" in caplog.text


def test_tier1_command_on_an_outage_writes_no_markers_and_exits_by_name(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Kesinti koşusu işaret yazmaz: `MAX_ATTEMPTS`i aşan kesintiden sonra da haberler sorulur."""
    db = _db_with(*TWO)
    client = FakeBatteryJev(error=ConnectionError("jev kapalı"))
    _cli(monkeypatch, db, client)

    codes = [cli.main(["tier1"]) for _ in range(MAX_ATTEMPTS + 1)]

    assert codes == [cli.EXIT_SOURCE_FAILED] * (MAX_ATTEMPTS + 1)
    assert cli.EXIT_SOURCE_FAILED == 7
    assert db.answers == [], "kesinti işareti yazılmamalı"
    assert len(client.seen) == 2 * (MAX_ATTEMPTS + 1), "kesinti haberi vazgeçilmiş yapmamalı"
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any("kesinti" in m and "2 haber" in m for m in errors), errors


# ── Review Focus: Türkçe ekler ve modelin liste dışı olasılıkları ─────────────────────────────


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Beşiktaş'ta sakatlık şoku", "m-bjk"),
        ("Galatasaraylı yıldız derbide yok", "m-gs"),
        ("Fenerbahçe'nin kadrosu belli oldu", "m-gs"),
        ("TRABZONSPOR'DA KRİZ", "m-bjk"),
    ],
)
def test_turkish_spelling_and_suffixes_still_find_the_fixture(title: str, expected: str) -> None:
    """Odds API adı ASCII (`Besiktas JK`), haber Türkçe ve ekli; aday kaçarsa Jev hiç sorulmaz."""
    assert [f.match_id for f in candidate_fixtures(news(1, title), FIXTURES)] == [expected]


@pytest.mark.parametrize(
    "probabilities",
    [
        {"m-gs:home": 0.8, "m-baska:home": 0.2},
        {"m-gs:home": 1.2},
        {"m-gs:home": float("nan")},
    ],
)
def test_probabilities_outside_the_offer_or_range_are_a_failure(
    probabilities: dict[str, float],
) -> None:
    """Geçerli seçimin yanında liste dışı ya da [0, 1] dışı olasılık da yazılmaz (0012 kısıtı)."""

    @dataclass
    class Odd(FakeBatteryJev):
        def ask_battery(
            self, state: Mapping[str, Any], questions: Sequence[Question]
        ) -> BatteryAnswer:
            answer = super().ask_battery(state, questions)
            odd = ChoiceAnswer("m-gs:home", 0.8, probabilities)
            return replace(answer, answers={**answer.answers, MATCH_QUESTION: odd})

    result = run([news(1, "Galatasaray'da sakatlık")], Odd())

    assert result.rows == ()
    assert result.failed == 2
