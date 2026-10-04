"""Kademe 2 koşucusu (Plan 2 R180, R185; I-1…I-3, M-1…M-4): sahte Jev, ağ yok, para yok."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.features import __main__ as cli
from football_edge.features.derive import item_set_hash
from football_edge.features.live_config import EXIT_FROZEN_SET, LiveConfig
from football_edge.features.news import NewsDraft, news_hash, write_news
from football_edge.features.questions import (
    CLUSTER_QUESTION,
    MATCH_QUESTION,
    NEW_EVENT,
    RELIABILITY_QUESTION,
    load_questions,
)
from football_edge.features.tier1 import OUTAGE_STREAK, ItemAnswerRow, write_item_answers
from football_edge.features.tier2 import (
    ASKED,
    BUDGET,
    DECISIONS_SQL,
    ERROR,
    INSERT_MATCH_ANSWERS,
    ITEM_LOOKBACK,
    MODEL_DRIFT,
    NO_NEWS,
    OUTAGE,
    SHADOW_STRATEGIES,
    STALE,
    STATUS_PREFIX,
    VARIANT_REAL,
    Decision,
    MatchAnswerRow,
    SideTask,
    answered_sides,
    final_status,
    gates_as_of,
    is_status,
    load_decisions,
    run_tier2,
    side_battery,
    side_tasks,
    write_match_answers,
)
from football_edge.features.types import AWAY, BOTH, HOME, OBSERVED, StoredNews
from football_edge.jev import NO_MATCH, BatteryAnswer, Question
from football_edge.jev_budget import BudgetExceeded
from football_edge.live.store import BASE_STRATEGIES
from tests.fake_jev import FakeBatteryJev
from tests.fake_tier2_db import FakeTier2Db

REPO = Path(__file__).resolve().parent.parent
QUESTIONS = load_questions(REPO / "config" / "jev_questions.yaml")
T1_PV = QUESTIONS.prompt_version
DECIDED = datetime(2026, 10, 6, 11, 0, tzinfo=UTC)  # salı 12:00 Londra (BST)
NOW = DECIDED + timedelta(minutes=40)
DECISION = Decision("m-gs", DECIDED, "Galatasaray", "Fenerbahce", DECIDED + timedelta(days=4))
CONFIG = LiveConfig(
    tier1_prompt_version=T1_PV,
    jev_model="jev-fake",
    min_belongs=0.5,
    min_reliability=0.5,
    estimate_usd=MappingProxyType({"tier1": 0.01, "tier2": 0.01}),
    max_sides_per_run=80,
    max_decision_age=timedelta(hours=6),
    prompt_version="b" * 64,
)
TR = frozenset({"tr"})


def item(
    item_id: int, title: str, at: datetime = DECIDED - timedelta(days=1), lang: str = "tr"
) -> StoredNews:
    url = f"https://ajansspor.com/haber/{item_id}"
    digest = news_hash("ajansspor", url, title, None)
    return StoredNews(item_id, "ajansspor", lang, title, None, url, at, at, OBSERVED, digest)


def gate_rows(
    item_id: int,
    side: str,
    *,
    asked_at: datetime = DECIDED - timedelta(hours=20),
    belongs: float = 0.9,
    reliable: float = 0.9,
) -> tuple[ItemAnswerRow, ItemAnswerRow]:
    chosen = f"m-gs:{side}"
    match = MappingProxyType({chosen: belongs, NO_MATCH: 1 - belongs})
    trust = MappingProxyType({"official": reliable, "rumour": 1 - reliable})
    return (
        ItemAnswerRow(
            item_id, T1_PV, MATCH_QUESTION, chosen, match, 0.9, "m-gs", "jev-fake", asked_at, 0.001
        ),
        ItemAnswerRow(
            item_id,
            T1_PV,
            RELIABILITY_QUESTION,
            "official",
            trust,
            0.9,
            "m-gs",
            "jev-fake",
            asked_at,
            0.001,
        ),
    )


def tasks(
    items: Sequence[StoredNews], rows: Sequence[ItemAnswerRow], languages: frozenset[str] = TR
) -> tuple[SideTask, ...]:
    return side_tasks(DECISION, items, rows, config=CONFIG, languages=languages)


HOME_NEWS = item(1, "Galatasaray'da sakatlık")
AWAY_NEWS = item(2, "Fenerbahçe'de ceza", DECIDED - timedelta(hours=5))


def _home_and_away() -> tuple[SideTask, ...]:
    return tasks([HOME_NEWS, AWAY_NEWS], [*gate_rows(1, HOME), *gate_rows(2, AWAY)])


def answers(rows: Sequence[MatchAnswerRow]) -> list[MatchAnswerRow]:
    return [row for row in rows if not is_status(row.question_id)]


def statuses(rows: Sequence[MatchAnswerRow]) -> list[tuple[str, str]]:
    """(taraf, sonuç) — işaret satırlarının yazıldığı sırayla."""
    return [
        (row.question_id.split(":")[1], row.choice) for row in rows if is_status(row.question_id)
    ]


def run(
    task_list: Sequence[SideTask],
    client: Any,
    *,
    config: LiveConfig = CONFIG,
    at: datetime = NOW,
    answered: frozenset[Any] = frozenset(),
    sink: Any = None,
) -> Any:
    extra = {} if sink is None else {"sink": sink}
    return run_tier2(
        task_list, client, QUESTIONS, config=config, clock=lambda: at, answered=answered, **extra
    )


# ── Küme (sızıntı) ─────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_gates_use_only_tier1_answers_asked_before_the_decision() -> None:
    """I-3 / Review Focus 2: karar anında ya da sonra sorulan cevap kapıya girmez (eşit an da)."""
    rows = [
        *gate_rows(1, HOME, asked_at=DECIDED - timedelta(seconds=1)),
        *gate_rows(2, HOME, asked_at=DECIDED),
        *gate_rows(3, HOME, asked_at=DECIDED + timedelta(minutes=5)),
    ]

    assert set(gates_as_of(rows, DECIDED)) == {1}


def _chained(item_id: int, asked_at: datetime, parent: str) -> tuple[ItemAnswerRow, ...]:
    link = ItemAnswerRow(
        item_id,
        T1_PV,
        CLUSTER_QUESTION,
        parent,
        MappingProxyType({parent: 1.0}),
        0.9,
        "m-gs",
        "jev-fake",
        asked_at,
        0.0,
    )
    return (*gate_rows(item_id, HOME, asked_at=asked_at), link)


@pytest.mark.leakage
def test_a_cluster_link_answered_after_the_decision_does_not_merge_side_news() -> None:
    """I-3 uçtan uca: C ← A ← B zincirinde A'nın kademe 1 cevabı karardan SONRA sorulmuş. Karar
    anında A yoktu: B kendi kümesidir ve C ile birlikte sorulur. Tüm satırlardan kurulan kapı (A
    dâhil) B'yi C'nin kümesine katar ve B kümenin tekrarı diye düşerdi."""
    c = item(3, "Galatasaray'da sakatlık", DECIDED - timedelta(hours=30))
    a = item(4, "Galatasaray'da sakatlık sürüyor", DECIDED - timedelta(hours=20))
    b = item(5, "Galatasaray'da yeni gelişme", DECIDED - timedelta(hours=10))
    rows = [
        *_chained(3, DECIDED - timedelta(hours=29), NEW_EVENT),
        *_chained(4, DECIDED + timedelta(minutes=5), "item:3"),
        *_chained(5, DECIDED - timedelta(hours=9), "item:4"),
    ]

    home, _ = tasks([c, a, b], rows)

    assert [i.item_id for i in home.items] == [3, 5]


@pytest.mark.leakage
def test_a_side_set_holds_only_news_available_before_the_decision() -> None:
    exact = item(2, "Galatasaray'da ikinci haber", DECIDED)
    rows = [*gate_rows(1, HOME), *gate_rows(2, HOME, asked_at=DECIDED - timedelta(hours=1))]

    home, _ = tasks([HOME_NEWS, exact], rows)

    assert [i.item_id for i in home.items] == [1]


def test_the_news_window_is_fixed_to_the_decision() -> None:
    """M2: pencere karar anına göre sabit (`ITEM_LOOKBACK`): kenar dahil, 1 sn öncesi dışarıda."""
    edge = item(1, "Galatasaray'da kenar", DECIDED - ITEM_LOOKBACK)
    older = item(2, "Galatasaray'da eski", DECIDED - ITEM_LOOKBACK - timedelta(seconds=1))
    rows = [*gate_rows(1, HOME), *gate_rows(2, HOME)]

    home, _ = tasks([edge, older], rows)

    assert [i.item_id for i in home.items] == [1]


@pytest.mark.leakage
def test_the_decision_query_reads_shadow_existence_not_probabilities_or_results() -> None:
    """I-2, M-1: gölge satırından yalnız (maç, karar anı) VARLIĞI; olasılık/fiyat/sonuç okunmaz."""
    text = DECISIONS_SQL.lower()
    for forbidden in ("p_home", "p_draw", "p_away", "pre_", "odds_snapshots", "closing", "result"):
        assert forbidden not in text, forbidden
    assert "from model_predictions" in text
    assert "p.decided_at >= %s" in text, "M1: 6 saatlik sınır dahil (`_skip` ile aynı)"


@pytest.mark.leakage
def test_the_shadow_strategies_are_the_reports_base_strategies() -> None:
    """`features/` `live.store`u import edemez (spec §5/4): ad listesi burada eşitlenir."""
    assert set(SHADOW_STRATEGIES) == BASE_STRATEGIES


# ── Taraf kümeleri ve batarya ──────────────────────────────────────────────────────────────


def test_each_side_set_is_its_own_news_plus_news_about_both() -> None:
    both = item(3, "Derbi öncesi iki takım", DECIDED - timedelta(hours=10))
    rows = [*gate_rows(1, HOME), *gate_rows(2, AWAY), *gate_rows(3, BOTH)]

    home, away = tasks([HOME_NEWS, AWAY_NEWS, both], rows)

    assert (home.side, [i.item_id for i in home.items]) == (HOME, [1, 3])
    assert (away.side, [i.item_id for i in away.items]) == (AWAY, [3, 2])
    assert home.item_set_hash == item_set_hash(home.items) != away.item_set_hash


def test_a_side_without_news_gets_an_empty_set() -> None:
    home, away = tasks([HOME_NEWS], gate_rows(1, HOME))

    assert ([i.item_id for i in home.items], away.items) == ([1], ())


def test_news_below_the_frozen_gate_thresholds_is_not_in_a_side_set() -> None:
    rows = [*gate_rows(1, HOME, belongs=0.4), *gate_rows(2, AWAY, reliable=0.4)]

    assert [task.items for task in tasks([HOME_NEWS, AWAY_NEWS], rows)] == [(), ()]


def test_news_in_a_non_production_language_is_not_in_a_side_set() -> None:
    english = item(1, "Galatasaray injury update", lang="en")

    assert [task.items for task in tasks([english], gate_rows(1, HOME))] == [(), ()]


def test_one_side_battery_is_tiers_two_to_four_bound_to_the_team() -> None:
    battery = side_battery(QUESTIONS, side=AWAY, team="Fenerbahce")

    assert len(battery) == 30
    assert all(q.question_id.endswith(":away") and "Fenerbahce" in q.instructions for q in battery)


# ── Koşucu ve durum işaretleri ─────────────────────────────────────────────────────────────


def test_each_side_is_asked_once_home_first_and_written_as_real_rows_with_a_marker() -> None:
    client = FakeBatteryJev()

    result = run(_home_and_away(), client)

    assert [call["state"]["team"] for call in client.seen] == ["Galatasaray", "Fenerbahce"]
    assert [n["title"] for n in client.seen[0]["state"]["news"]] == ["Galatasaray'da sakatlık"]
    assert (result.asked_sides, len(answers(result.rows))) == (2, 60)
    assert statuses(result.rows) == [(HOME, ASKED), (AWAY, ASKED)]
    assert {(r.variant, r.prompt_version, r.asked_at) for r in result.rows} == {
        (VARIANT_REAL, CONFIG.prompt_version, NOW)
    }


def test_a_side_without_news_is_not_asked_and_is_marked_no_news() -> None:
    """I-1/I5: "yok" ataması `no_news` işaretinden türetilir; dil kümesi yeniden kurulmaz."""
    client = FakeBatteryJev()

    result = run(tasks([HOME_NEWS], gate_rows(1, HOME)), client)

    assert len(client.seen) == 1
    assert statuses(result.rows) == [(HOME, ASKED), (AWAY, NO_NEWS)]


def test_markers_are_never_answers_and_answers_never_markers() -> None:
    rows = run(_home_and_away(), FakeBatteryJev()).rows

    assert all(
        row.question_id.startswith(STATUS_PREFIX) == (row.choice in (ASKED,)) for row in rows
    )
    marker = next(row for row in rows if is_status(row.question_id))
    assert (marker.probabilities, marker.confidence, marker.cost_usd) == ({ASKED: 1.0}, 1.0, 0.0)


def test_the_final_status_lets_asked_override_an_earlier_stop() -> None:
    assert final_status([BUDGET, ASKED]) == ASKED
    assert final_status([ERROR, OUTAGE]) == ERROR
    assert final_status([NO_NEWS]) == NO_NEWS


def test_an_answered_side_is_not_asked_again_nor_marked_again() -> None:
    home, away = _home_and_away()
    client = FakeBatteryJev()

    result = run((home, away), client, answered=frozenset({home.key}))

    assert [call["state"]["team"] for call in client.seen] == ["Fenerbahce"]
    assert (result.count("answered_before"), statuses(result.rows)) == (1, [(AWAY, ASKED)])


@pytest.mark.parametrize(
    ("late", "asked"), [(timedelta(hours=6), 2), (timedelta(hours=6, seconds=1), 0)]
)
def test_a_decision_older_than_six_hours_is_not_asked(late: timedelta, asked: int) -> None:
    client = FakeBatteryJev()

    result = run(_home_and_away(), client, at=DECIDED + late)

    assert (len(client.seen), result.count(STALE)) == (asked, 2 - asked)


def test_the_side_cap_defers_the_rest_of_the_run() -> None:
    result = run(_home_and_away(), FakeBatteryJev(), config=replace(CONFIG, max_sides_per_run=1))

    assert statuses(result.rows) == [(HOME, ASKED), (AWAY, "deferred")]


def test_a_model_other_than_the_frozen_one_is_not_written_and_stops_the_run() -> None:
    handed: list[Any] = []

    result = run(_home_and_away(), FakeBatteryJev(jev_model="jev-yeni"), sink=handed.extend)

    assert (answers(handed), result.model_drift) == ([], "jev-yeni")
    assert statuses(handed) == [(HOME, MODEL_DRIFT), (AWAY, MODEL_DRIFT)]
    assert handed[0].jev_model == "jev-yeni"


def test_each_side_is_handed_to_the_sink_before_the_next_is_asked() -> None:
    client = FakeBatteryJev()
    handed: list[tuple[int, int]] = []

    run(_home_and_away(), client, sink=lambda rows: handed.append((len(rows), len(client.seen))))

    assert handed == [(31, 1), (31, 2)]


def test_a_missing_answer_leaves_its_question_out_and_counts_it_failed() -> None:
    home, _ = _home_and_away()

    result = run((home,), FakeBatteryJev(missing=frozenset({"t2_kaleci_eksik:home"})))

    assert (len(answers(result.rows)), result.failed) == (29, 1)


def test_consecutive_jev_errors_stop_the_run_as_an_outage() -> None:
    many = tuple(
        SideTask(replace(DECISION, match_id=f"m{n}"), HOME, "Galatasaray", (HOME_NEWS,), "c" * 64)
        for n in range(OUTAGE_STREAK + 1)
    )
    client = FakeBatteryJev(error=ConnectionError("jev kapalı"))

    result = run(many, client)

    assert result.outage and len(client.seen) == OUTAGE_STREAK and answers(result.rows) == []
    assert [s for _, s in statuses(result.rows)] == [ERROR] * OUTAGE_STREAK + [OUTAGE]


def test_the_budget_stops_the_run_and_keeps_the_side_already_paid_for() -> None:
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

    result = run(_home_and_away(), BudgetAfterOne())

    assert result.budget_hit and len(answers(result.rows)) == 30
    assert statuses(result.rows) == [(HOME, ASKED), (AWAY, BUDGET)]


# ── Veritabanı ve CLI ──────────────────────────────────────────────────────────────────────


def _db() -> FakeTier2Db:
    db = FakeTier2Db(now=DECIDED - timedelta(days=30))
    drafts = [
        NewsDraft(
            n.source_id, n.lang, n.title, None, n.url, n.available_at, OBSERVED, n.content_hash
        )
        for n in (HOME_NEWS, AWAY_NEWS)
    ]
    write_news(db, drafts)  # type: ignore[arg-type]
    write_item_answers(db, [*gate_rows(1, HOME), *gate_rows(2, AWAY)])  # type: ignore[arg-type]
    db.matches = {
        "m-gs": ("Galatasaray", "Fenerbahce", DECIDED + timedelta(days=4)),
        "m-eski": ("Besiktas JK", "Trabzonspor", DECIDED + timedelta(days=2)),
    }
    db.predictions = [
        *(("m-gs", strategy, DECIDED) for strategy in SHADOW_STRATEGIES),
        ("m-eski", "market", DECIDED - timedelta(days=3)),
        ("m-eski", "harman_jev", DECIDED),
    ]
    return db


def test_load_decisions_reads_this_rounds_base_shadow_rows_once_per_match() -> None:
    found = load_decisions(_db(), now=NOW, max_age=timedelta(hours=6))  # type: ignore[arg-type]

    assert found == (DECISION,)


@pytest.mark.parametrize(
    ("age", "found"), [(timedelta(hours=6), 1), (timedelta(hours=6, seconds=1), 0)]
)
def test_a_decision_exactly_six_hours_old_is_still_loaded(age: timedelta, found: int) -> None:
    """M1: yükleme sınırı `_skip` ile aynı — 6 saat dahil."""
    loaded = load_decisions(_db(), now=DECIDED + age, max_age=timedelta(hours=6))  # type: ignore[arg-type]

    assert len(loaded) == found


def test_the_insert_is_idempotent_on_the_unique_key() -> None:
    """I3: tekil anahtar SQL metninde; taklit uygulasa da asıl koruma bu cümledir."""
    assert (
        "ON CONFLICT (match_id, decided_at, prompt_version, question_id, variant) DO NOTHING"
        in INSERT_MATCH_ANSWERS
    )


def test_match_answers_are_written_once_and_only_asked_markers_close_a_side() -> None:
    db = _db()
    home, away = _home_and_away()
    rows = run((home,), FakeBatteryJev()).rows
    stopped = run((away,), FakeBatteryJev(error=ConnectionError("x"))).rows

    assert write_match_answers(db, [*rows, *stopped]) == 32  # type: ignore[arg-type]
    assert write_match_answers(db, rows) == 0  # type: ignore[arg-type]
    found = answered_sides(db, CONFIG.prompt_version, ["m-gs"])  # type: ignore[arg-type]
    assert found == {("m-gs", DECIDED, HOME)}, "hata işareti tarafı kapatmamalı (yeniden sorulur)"


def _config_files(tmp_path: Path, model: str = "jev-fake") -> list[str]:
    live, ops = tmp_path / "faz4_live.yaml", tmp_path / "faz4_ops.yaml"
    live.write_text(
        f"tier1_prompt_version: {T1_PV}\njev_model: {model}\nmin_belongs: 0.5\n"
        "min_reliability: 0.5\n",
        encoding="utf-8",
    )
    ops.write_text(
        "estimate_usd:\n  tier1: 0.01\n  tier2: 0.01\nmax_sides_per_run: 80\n"
        "max_decision_age_hours: 6\n",
        encoding="utf-8",
    )
    return ["--live-config", str(live), "--ops-config", str(ops)]


def _cli(monkeypatch: pytest.MonkeyPatch, db: Any, client: Any) -> None:
    monkeypatch.setattr(cli, "connect", lambda: db)
    monkeypatch.setattr(cli, "TypeSafeJev", lambda **_: client)
    monkeypatch.setattr(cli, "budgeted_jev", lambda jev, spend_conn, **_: jev)
    monkeypatch.setattr(cli, "production_languages", lambda path: TR)
    monkeypatch.setattr(cli, "_now", lambda: NOW)


def _explode(*_a: object, **_k: object) -> Any:
    raise AssertionError("veritabanına bağlanılmamalı")


def test_tier2_command_writes_each_side_and_commits_per_side(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db = _db()
    _cli(monkeypatch, db, FakeBatteryJev())

    with caplog.at_level(logging.INFO):
        code = cli.main(["tier2", *_config_files(tmp_path)])

    assert code == 0
    assert (len(db.match_answers), db.commits) == (62, 2)
    assert "haberi olmayan taraf 0" in caplog.text


def test_a_second_tier2_run_buys_nothing_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Review Focus 3 (M-3): aynı gün yeniden koşulan gölge turu cevaplanmış tarafı satın almaz."""
    db, client = _db(), FakeBatteryJev()
    _cli(monkeypatch, db, client)
    argv = ["tier2", *_config_files(tmp_path)]

    cli.main(argv)
    cli.main(argv)

    assert (len(client.seen), len(db.match_answers)) == (2, 62)


def test_tier2_without_a_key_exits_17_before_the_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("TYPESAFE" + "_API_KEY", raising=False)
    monkeypatch.setattr(cli, "connect", _explode)

    assert cli.main(["tier2", *_config_files(tmp_path, "null")]) == 17


def test_an_unpinned_model_with_a_key_exits_25_before_the_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _cli(monkeypatch, None, FakeBatteryJev())
    monkeypatch.setattr(cli, "connect", _explode)

    code = cli.main(["tier2", *_config_files(tmp_path, "null")])

    assert code == EXIT_FROZEN_SET == 25


def test_tier2_without_a_production_language_asks_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _cli(monkeypatch, None, FakeBatteryJev())
    monkeypatch.setattr(cli, "connect", _explode)
    monkeypatch.setattr(cli, "production_languages", lambda path: frozenset())

    assert cli.main(["tier2", *_config_files(tmp_path)]) == 0


@pytest.mark.parametrize(
    ("client", "code"),
    [(FakeBatteryJev(jev_model="jev-yeni"), 25), (FakeBatteryJev(error=ConnectionError("x")), 7)],
    ids=["model-drift", "no-side-answered"],
)
def test_tier2_exit_codes_by_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, client: Any, code: int
) -> None:
    """I4: iki hatalı taraf `OUTAGE_STREAK` (3) altında ama HİÇBİR taraf cevaplanmadı: kesinti (7).
    Her iki durumda cevap satırı yazılmaz; yalnız durum işaretleri."""
    db = _db()
    _cli(monkeypatch, db, client)

    assert cli.main(["tier2", *_config_files(tmp_path)]) == code
    assert [row for row in db.match_answers if not is_status(row["question_id"])] == []
