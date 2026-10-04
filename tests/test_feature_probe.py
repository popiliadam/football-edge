"""Tek gerçek çağrı ölçümü (Plan 2 R184, Task 5): tek batarya, gecikme + model; yazım yok (M-8)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from football_edge.features import __main__ as cli
from football_edge.features.news import NewsDraft, news_hash, write_news
from football_edge.features.probe import TimingJev, probe_task, probe_tier1, probe_tier2
from football_edge.features.questions import load_questions
from football_edge.features.tier2 import Decision
from football_edge.features.types import AWAY, OBSERVED, StoredNews
from football_edge.jev import Question
from football_edge.live.context import LiveMatch
from tests.fake_jev import FakeBatteryJev
from tests.fake_tier2_db import FakeTier2Db

QUESTIONS = load_questions(Path(__file__).resolve().parent.parent / "config" / "jev_questions.yaml")
NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
FIXTURE = LiveMatch(
    "m-gs", "soccer_turkey_super_league", NOW + timedelta(days=2), "Galatasaray", "Fenerbahce"
)


def item(item_id: int, title: str, at: datetime) -> StoredNews:
    url = f"https://ajansspor.com/haber/{item_id}"
    digest = news_hash("ajansspor", url, title, None)
    return StoredNews(item_id, "ajansspor", "tr", title, None, url, at, at, OBSERVED, digest)


ITEMS = (
    item(1, "Galatasaray'da sakatlık", NOW - timedelta(hours=3)),
    item(2, "Galatasaray'da ikinci haber", NOW - timedelta(hours=2)),
)


def test_timing_records_the_seconds_and_the_returned_model() -> None:
    ticks = iter([10.0, 12.5])
    timing = TimingJev(FakeBatteryJev(jev_model="jev-2026-10"), timer=lambda: next(ticks))

    timing.ask_battery({}, [Question("q", "soru", {"a": "b"})])

    assert timing.timings == ((2.5, "jev-2026-10"),)


def test_the_tier1_probe_asks_exactly_one_battery() -> None:
    client = FakeBatteryJev()

    result = probe_tier1(ITEMS, (FIXTURE,), client, QUESTIONS, clock=lambda: NOW)

    assert len(client.seen) == 1
    assert result is not None and result.jev_model == "jev-fake"


def test_the_tier2_probe_uses_the_latest_decision_with_a_mentioned_side() -> None:
    old = Decision("m-old", NOW - timedelta(days=5), "Galatasaray", "Rizespor", NOW)
    new = Decision("m-new", NOW - timedelta(hours=1), "Trabzonspor", "Galatasaray", NOW)

    task = probe_task((old, new), ITEMS)

    assert task is not None and (task.decision.match_id, task.side) == ("m-new", AWAY)
    result = probe_tier2(task, FakeBatteryJev(), QUESTIONS)
    assert (result.asked, result.answered) == (30, 30)


def test_the_probe_command_prints_the_model_and_writes_no_answer_row(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = FakeTier2Db(now=NOW - timedelta(days=30))
    write_news(  # type: ignore[arg-type]
        db,
        [
            NewsDraft(
                i.source_id, i.lang, i.title, None, i.url, i.available_at, OBSERVED, i.content_hash
            )
            for i in ITEMS
        ],
    )
    db.fixtures = [
        (FIXTURE.match_id, FIXTURE.league_id, FIXTURE.kickoff, FIXTURE.home, FIXTURE.away)
    ]
    monkeypatch.setattr(cli, "connect", lambda: db)
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    monkeypatch.setattr(cli, "TypeSafeJev", lambda **_: FakeBatteryJev(jev_model="jev-2026-10"))
    monkeypatch.setattr(cli, "budgeted_jev", lambda jev, spend_conn, **_: jev)

    assert cli.main(["probe", "--tier", "1"]) == 0

    assert "model jev-2026-10" in capsys.readouterr().out
    assert db.read_only and db.answers == [] and db.match_answers == []
