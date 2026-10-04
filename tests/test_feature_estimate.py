"""Jev'siz kuru koşu (Plan 2 R184; I-10): sayım, aylık dolar, 900'e varış, kullanıcı durakları."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.features import __main__ as cli
from football_edge.features.estimate import STOP_DATE, estimate, stops_for
from football_edge.features.live_config import LiveConfig
from football_edge.features.news import NewsDraft, news_hash, write_news
from football_edge.features.tier2 import Decision
from football_edge.features.types import OBSERVED, StoredNews
from football_edge.live.context import LiveMatch
from tests.fake_tier2_db import FakeTier2Db

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
CONFIG = LiveConfig(
    tier1_prompt_version="a" * 64,
    jev_model=None,
    min_belongs=0.5,
    min_reliability=0.5,
    estimate_usd=MappingProxyType({"tier1": 0.01, "tier2": 0.02}),
    max_sides_per_run=80,
    max_decision_age=timedelta(hours=6),
    prompt_version="b" * 64,
)
DECISION = Decision(
    "m-gs", NOW - timedelta(days=2), "Galatasaray", "Fenerbahce", NOW - timedelta(days=1)
)
FIXTURE = LiveMatch(
    "m-gs", "soccer_turkey_super_league", NOW - timedelta(days=1), "Galatasaray", "Fenerbahce"
)


def item(item_id: int, title: str, lang: str = "tr") -> StoredNews:
    url, at = f"https://ajansspor.com/haber/{item_id}", NOW - timedelta(days=3)
    digest = news_hash("ajansspor", url, title, None)
    return StoredNews(item_id, "ajansspor", lang, title, None, url, at, at, OBSERVED, digest)


ITEMS = (
    item(1, "Galatasaray'da sakatlık"),
    item(2, "Hava durumu"),
    item(3, "Galatasaray injury update", lang="en"),
)


def test_the_dry_run_counts_tier1_calls_and_tier2_sides_in_the_assumed_language() -> None:
    found = estimate(ITEMS, (FIXTURE,), (DECISION,), config=CONFIG, slice_count=0, now=NOW)

    assert (found.tier1_calls, found.tier2_sides, found.news_decisions) == (1, 1, 1)
    assert found.monthly_usd == pytest.approx(30.4 * (0.01 + 0.02) / 28)


@pytest.mark.parametrize(
    ("monthly", "eta", "stops"),
    [
        (19.0, date(2027, 5, 1), 0),
        (21.0, date(2027, 5, 1), 1),
        (19.0, STOP_DATE + timedelta(days=1), 1),
        (19.0, None, 1),
        (21.0, None, 2),
    ],
)
def test_the_user_stops_are_twenty_dollars_and_the_end_of_june_2027(
    monthly: float, eta: date | None, stops: int
) -> None:
    assert len(stops_for(monthly, eta)) == stops


def _explode(*_a: object, **_k: object) -> Any:
    raise AssertionError("kuru koşu Jev kurmamalı")


def test_the_estimate_command_reads_only_and_never_builds_jev(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = FakeTier2Db(now=NOW - timedelta(days=30))
    drafts = [
        NewsDraft(
            i.source_id, i.lang, i.title, None, i.url, i.available_at, OBSERVED, i.content_hash
        )
        for i in ITEMS
    ]
    write_news(db, drafts)  # type: ignore[arg-type]
    db.fixtures = [
        (FIXTURE.match_id, FIXTURE.league_id, FIXTURE.kickoff, FIXTURE.home, FIXTURE.away)
    ]
    db.matches = {"m-gs": ("Galatasaray", "Fenerbahce", NOW - timedelta(days=1))}
    db.predictions = [("m-gs", "market", NOW - timedelta(days=2))]
    monkeypatch.setattr(cli, "connect", lambda: db)
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    monkeypatch.setattr(cli, "TypeSafeJev", _explode)
    start = len(db.statements)

    assert cli.main(["estimate"]) == 0

    out = capsys.readouterr().out
    assert "kademe 1 çağrı (son 28 gün): 1" in out and "KULLANICI DURAĞI" in out
    assert db.read_only and db.statements[start] == "SET TRANSACTION READ ONLY"
    assert db.answers == [] and db.match_answers == []
