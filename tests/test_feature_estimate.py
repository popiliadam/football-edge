"""Jev'siz kuru koşu (Plan 2 R184; I-10): sayım, aylık dolar, 900'e varış, kullanıcı durakları."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.features import __main__ as cli
from football_edge.features.estimate import (
    STOP_DATE,
    STOP_MONTHLY_USD,
    candidate_sides,
    estimate,
    stops_for,
)
from football_edge.features.live_config import LiveConfig, load_live_config
from football_edge.features.news import NewsDraft, news_hash, write_news
from football_edge.features.slice import TARGET
from football_edge.features.tier2 import ASKED, ITEM_LOOKBACK, Decision, status_question
from football_edge.features.types import HOME, OBSERVED, StoredNews
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


def item(item_id: int, title: str, lang: str = "tr", at: datetime | None = None) -> StoredNews:
    url, at = f"https://ajansspor.com/haber/{item_id}", at or NOW - timedelta(days=3)
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
        # Sınırlar (R184 "> 20 $", "> 2027-06-30"): tam eşik durak DEĞİL; bir kuruş ya da bir
        # gün fazlası durak.
        (STOP_MONTHLY_USD, date(2027, 5, 1), 0),
        (STOP_MONTHLY_USD + 0.01, date(2027, 5, 1), 1),
        (19.0, STOP_DATE, 0),
    ],
)
def test_the_user_stops_are_twenty_dollars_and_the_end_of_june_2027(
    monthly: float, eta: date | None, stops: int
) -> None:
    assert len(stops_for(monthly, eta)) == stops


TS_FIXTURE = LiveMatch(
    "m-ts", "soccer_turkey_super_league", NOW - timedelta(days=1), "Trabzonspor", "Rizespor"
)


def test_each_tier_is_priced_with_its_own_unit() -> None:
    """Eşit olmayan sayılar ve birimler: 2 kademe 1 çağrısı × 0,01 + 1 taraf × 0,05 (E1)."""
    config = replace(CONFIG, estimate_usd=MappingProxyType({"tier1": 0.01, "tier2": 0.05}))
    items = (*ITEMS, item(4, "Trabzonspor'da transfer"))

    found = estimate(
        items, (FIXTURE, TS_FIXTURE), (DECISION,), config=config, slice_count=0, now=NOW
    )

    assert (found.tier1_calls, found.tier2_sides) == (2, 1)
    assert found.monthly_usd == pytest.approx(30.4 * (2 * 0.01 + 1 * 0.05) / 28)


def test_the_eta_runs_at_the_weekly_rate_of_news_decisions() -> None:
    """1 haberli karar / 4 hafta = haftada 0,25: kalan TEK karar 28 gün sürer (inceleme E4)."""
    found = estimate(ITEMS, (FIXTURE,), (DECISION,), config=CONFIG, slice_count=TARGET - 1, now=NOW)

    assert found.eta == NOW.date() + timedelta(days=28)


def test_the_tier2_bound_reaches_back_as_far_as_tier2_itself() -> None:
    """Kademe 2'nin haber penceresi `ITEM_LOOKBACK` (8 gün + 72 sa): 10 gün önceki haber tarafı
    açar, pencerenin dışındaki açmaz — üst sınır kademe 2'den dar olamaz (inceleme 5)."""
    at = DECISION.decided_at

    inside = item(5, "Fenerbahce'de kriz", at=at - timedelta(days=10))
    outside = item(6, "Fenerbahce'de kriz", at=at - ITEM_LOOKBACK - timedelta(seconds=1))

    assert candidate_sides(DECISION, (inside,)) == 1
    assert candidate_sides(DECISION, (outside,)) == 0


def _explode(*_a: object, **_k: object) -> Any:
    raise AssertionError("kuru koşu Jev kurmamalı")


def _db(items: tuple[StoredNews, ...] = ITEMS) -> FakeTier2Db:
    db = FakeTier2Db(now=NOW - timedelta(days=60))
    drafts = [
        NewsDraft(
            i.source_id, i.lang, i.title, None, i.url, i.available_at, OBSERVED, i.content_hash
        )
        for i in items
    ]
    write_news(db, drafts)  # type: ignore[arg-type]
    db.fixtures = [
        (FIXTURE.match_id, FIXTURE.league_id, FIXTURE.kickoff, FIXTURE.home, FIXTURE.away)
    ]
    db.matches = {"m-gs": ("Galatasaray", "Fenerbahce", NOW - timedelta(days=1))}
    db.predictions = [("m-gs", "market", NOW - timedelta(days=2))]
    return db


def _run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], db: FakeTier2Db
) -> str:
    monkeypatch.setattr(cli, "connect", lambda: db)
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    monkeypatch.setattr(cli, "TypeSafeJev", _explode)
    assert cli.main(["estimate"]) == 0
    return capsys.readouterr().out


def test_the_estimate_command_reads_only_and_never_builds_jev(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = _db()
    monkeypatch.setattr(cli, "connect", lambda: db)
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    monkeypatch.setattr(cli, "TypeSafeJev", _explode)
    start = len(db.statements)

    assert cli.main(["estimate"]) == 0

    out = capsys.readouterr().out
    assert "kademe 1 çağrı (son 28 gün): 1" in out and "KULLANICI DURAĞI" in out
    assert db.read_only and db.statements[start] == "SET TRANSACTION READ ONLY"
    assert db.answers == [] and db.match_answers == []


def _marker(match_id: str, decided_at: datetime, version: str) -> dict[str, Any]:
    return {
        "match_id": match_id,
        "decided_at": decided_at,
        "prompt_version": version,
        "variant": "real",
        "question_id": status_question(HOME, ASKED),
    }


def test_the_estimate_command_counts_only_the_current_set(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """900'e varış geçerli kümenin sayacından: eski kümenin satırları sayılmaz (inceleme E5)."""
    current, old, at = load_live_config().prompt_version, "e" * 64, NOW - timedelta(days=40)
    db = _db()
    db.predictions = [*db.predictions, *((f"m-{n}", "market", at) for n in range(3))]
    db.match_answers = [
        _marker("m-0", at, current),
        _marker("m-1", at, old),
        _marker("m-2", at, old),
    ]

    out = _run(monkeypatch, capsys, db)

    # 1 haberli karar / 4 hafta; geçerli kümede 1 karar → kalan 899 × 28 gün.
    assert f"{TARGET}'e varış: {NOW.date() + timedelta(days=(TARGET - 1) * 28)}" in out


def test_the_estimate_command_loads_news_as_far_back_as_tier2_looks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """28 gün önceki kararın tarafı, karardan 10 gün önceki haberle açılır: haber `WINDOW +
    ITEM_LOOKBACK` geriden yüklenir (inceleme 5)."""
    decided = NOW - timedelta(days=27)
    db = _db((*ITEMS, item(7, "Rizespor'da kriz", at=decided - timedelta(days=10))))
    db.matches = {**db.matches, "m-rz": ("Rizespor", "Sivasspor", decided + timedelta(days=1))}
    db.predictions = [*db.predictions, ("m-rz", "market", decided)]

    out = _run(monkeypatch, capsys, db)

    assert "kademe 2 üst sınır taraf (son 28 gün): 2" in out
