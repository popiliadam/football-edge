"""Modüller arası sızıntı senaryosu (Plan 2 son inceleme): RSS → `source_observations` →
`sync-news` → kademe 1 → kademe 2, CLI yolundan uçtan uca.

Kademe 2'nin karar anındaki haber kümesine kararDAN SONRA bilinen hiçbir şey girmez:

- `ai-input=no` diyen kaynağın haberi (F) ne kademe 1'e ne kademe 2'ye gider (`load_news` süzgeci);
- karardan önce yayımlanmış ama kademe 1'de karardan SONRA sorulmuş haber (B, R) kümeye girmez
  (`derive._usable` canlı `asked_at` denetimi + `tier2.gates_as_of`);
- yayın tarihini geriye atan ama karardan sonra ilk görülen haber (L) girmez (`available_at`);
- karardan önce sorulmuş haberin kümesi (C → R) sonradan sorulmuş köke bağlanır: C yine girer, kök
  R girmez.

Veri tamamen sentetiktir (`.test` alan adları, uydurma başlıklar); ağ yok, Jev sahte.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from typing import Any

import pytest

from football_edge.collectors.news import RssAdapter, news_observation
from football_edge.features import __main__ as cli
from football_edge.features import news as news_mod
from football_edge.features.questions import (
    CLUSTER_QUESTION,
    MATCH_QUESTION,
    NEW_EVENT,
    RELIABILITY_QUESTION,
    load_questions,
)
from football_edge.features.tier2 import SHADOW_STRATEGIES
from football_edge.jev import COST_REPORTED, BatteryAnswer, ChoiceAnswer, Question
from tests.fake_tier2_db import FakeTier2Db

REPO = Path(__file__).resolve().parent.parent
T1_VERSION = load_questions(REPO / "config" / "jev_questions.yaml").prompt_version
DECIDED = datetime(2026, 10, 6, 11, 0, tzinfo=UTC)
KICKOFF = DECIDED + timedelta(days=4)

EARLY = "Galatasaray'da sakatlik haberi"  # A: karardan önce görüldü ve soruldu
BLOCKED = "Galatasaray'da transfer bombasi"  # F: kaynağı ai-input=no
ROOT = "Galatasaray'da sakatlik soku"  # R: küme kökü, karardan SONRA soruldu
CHILD = "Galatasaray'da sakatlik suruyor"  # C: karardan önce soruldu, küme ebeveyni = R
AWAY_LATE = "Fenerbahce'de ceza karari"  # B: karardan önce görüldü, SONRA soruldu
SEEN_LATE = "Galatasaray'da kriz patladi"  # L: karardan sonra görüldü, yayın tarihi geriye atılmış


def _rss(source: str, title: str, published: datetime, number: int) -> str:
    return (
        '<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>'
        f"<item><title>{title}</title><link>https://{source}.test/h/{number}</link>"
        f"<pubDate>{format_datetime(published)}</pubDate></item></channel></rss>"
    )


@dataclass
class ScenarioJev:
    """Maç: Fenerbahçe haberi deplasman, kalanı ev. Küme: yalnız C, R'yi seçer. Kaynak resmî."""

    seen: list[dict[str, Any]] = field(default_factory=list)

    def ask_choice(
        self, state: dict[str, Any], instructions: str, criteria: dict[str, str]
    ) -> ChoiceAnswer:
        raise AssertionError("senaryo yalnız batarya sorar")

    def ask_battery(self, state: Mapping[str, Any], questions: Sequence[Question]) -> BatteryAnswer:
        self.seen = [*self.seen, dict(state)]
        news = state.get("news")
        title = news["title"] if isinstance(news, Mapping) else ""
        return BatteryAnswer(
            answers={q.question_id: self._answer(q, title) for q in questions},
            jev_model="jev-fake",
            cost_usd=0.002,
            cost_basis=COST_REPORTED,
        )

    def _answer(self, question: Question, title: str) -> ChoiceAnswer:
        keys = list(question.criteria)
        if question.question_id == MATCH_QUESTION:
            side = ":away" if "Fenerbahce" in title else ":home"
            choice = next(key for key in keys if key.endswith(side))
        elif question.question_id == CLUSTER_QUESTION:
            root = next((k for k, v in question.criteria.items() if v.endswith(ROOT)), None)
            choice = root if title == CHILD and root else NEW_EVENT
        elif question.question_id == RELIABILITY_QUESTION:
            choice = "official"
        else:
            choice = keys[0]
        rest = [key for key in keys if key != choice]
        top = 0.9 if rest else 1.0
        probabilities = {choice: top, **{key: 0.1 / len(rest) for key in rest}}
        return ChoiceAnswer(choice=choice, confidence=0.9, probabilities=probabilities)


def _titles(state: Mapping[str, Any]) -> set[str]:
    """Bir Jev çağrısının gördüğü bütün başlıklar (haber, haber listesi, önceki haberler)."""
    news = state.get("news")
    found = {news["title"]} if isinstance(news, Mapping) else set()
    if isinstance(news, list):
        found |= {entry["title"] for entry in news}
    return found | {entry["title"] for entry in state.get("earlier_news", [])}


@pytest.fixture
def blocked_robots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`fotomac` anlık görüntüsü `ai-input=no` der (geri kalan robots aynen)."""
    robots = tmp_path / "robots"
    shutil.copytree(REPO / "config" / "robots", robots)
    snapshot = robots / "fotomac.txt"
    text = snapshot.read_text(encoding="utf-8")
    assert "ai-input=yes" in text
    snapshot.write_text(text.replace("ai-input=yes", "ai-input=no"), encoding="utf-8")
    original = news_mod.jev_blocked_sources
    monkeypatch.setattr(news_mod, "jev_blocked_sources", lambda _dir=None: original(robots))


def _config(tmp_path: Path) -> list[str]:
    live, ops = tmp_path / "live.yaml", tmp_path / "ops.yaml"
    live.write_text(
        f"tier1_prompt_version: {T1_VERSION}\njev_model: jev-fake\nmin_belongs: 0.5\n"
        "min_reliability: 0.5\n",
        encoding="utf-8",
    )
    ops.write_text(
        "estimate_usd:\n  tier1: 0.01\n  tier2: 0.01\nmax_sides_per_run: 80\n"
        "max_decision_age_hours: 6\n",
        encoding="utf-8",
    )
    return ["--live-config", str(live), "--ops-config", str(ops)]


class Timeline:
    """Saat + sahte veritabanı + sahte Jev: haber yayımlar, senkronlar ve kademeleri koşar."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, config: list[str]) -> None:
        self.db = FakeTier2Db(now=DECIDED - timedelta(days=1))
        self.db.fixtures = [("m-gs", "tur.1", KICKOFF, "Galatasaray", "Fenerbahce")]
        self.db.matches = {"m-gs": ("Galatasaray", "Fenerbahce", KICKOFF)}
        self.db.predictions = [("m-gs", strategy, DECIDED) for strategy in SHADOW_STRATEGIES]
        self.jev = ScenarioJev()
        self.now = DECIDED
        self.config = config
        self.published = 0
        monkeypatch.setattr(cli, "connect", lambda: self.db)
        monkeypatch.setattr(cli, "TypeSafeJev", lambda **_: self.jev)
        monkeypatch.setattr(cli, "budgeted_jev", lambda jev, spend_conn, **_: jev)
        monkeypatch.setattr(cli, "production_languages", lambda _path: frozenset({"tr"}))
        monkeypatch.setattr(cli, "_now", lambda: self.now)

    def publish(self, source: str, title: str, *, synced: datetime, claimed: datetime) -> None:
        self.published += 1
        body = _rss(source, title, claimed, self.published)
        for item in RssAdapter(source).parse(body, now=synced):
            observation = news_observation(item)
            self.db.observe(observation.source_id, observation.observed_at, observation.payload)
        self.db.now = self.now = synced
        assert cli.main(["sync-news"]) == 0

    def tier1(self, at: datetime, *extra: str) -> None:
        self.now = at
        assert cli.main(["tier1", *self.config, *extra]) == 0

    def tier2(self, at: datetime) -> None:
        self.now = at
        assert cli.main(["tier2", *self.config]) == 0


@pytest.mark.leakage
def test_the_tier2_news_set_excludes_every_post_decision_and_blocked_item(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blocked_robots: None
) -> None:
    line = Timeline(monkeypatch, _config(tmp_path))
    hours = timedelta(hours=1)

    line.publish("aspor", EARLY, synced=DECIDED - 20 * hours, claimed=DECIDED - 21 * hours)
    line.publish("fotomac", BLOCKED, synced=DECIDED - 20 * hours, claimed=DECIDED - 21 * hours)
    line.tier1(DECIDED - 19 * hours)
    line.publish("aspor", ROOT, synced=DECIDED - 5 * hours, claimed=DECIDED - 6 * hours)
    line.publish("aspor", AWAY_LATE, synced=DECIDED - 4.5 * hours, claimed=DECIDED - 5 * hours)
    line.publish("aspor", CHILD, synced=DECIDED - 4 * hours, claimed=DECIDED - 5 * hours)
    line.tier1(DECIDED - hours, "--max-calls", "1")  # en yeni C sorulur; R ve B ertelenir
    line.publish("aspor", SEEN_LATE, synced=DECIDED + timedelta(minutes=5), claimed=DECIDED - hours)
    line.tier1(DECIDED + timedelta(minutes=10))  # R, B, L karardan SONRA sorulur

    tier1_states = tuple(line.jev.seen)
    assert [s["news"]["title"] for s in tier1_states] == [EARLY, CHILD, ROOT, AWAY_LATE, SEEN_LATE]
    assert all(BLOCKED not in _titles(s) for s in tier1_states), "ai-input=no kademe 1'e gitti"
    ids = {row["title"]: row["id"] for row in line.db.news}
    clusters = {
        (a["item_id"], a["choice"]) for a in line.db.answers if a["question_id"] == CLUSTER_QUESTION
    }
    assert (ids[CHILD], f"item:{ids[ROOT]}") in clusters
    late = next(row for row in line.db.news if row["title"] == SEEN_LATE)
    assert late["available_at"] > DECIDED > late["published_at_claimed"]

    line.tier2(DECIDED + timedelta(minutes=40))

    tier2_states = line.jev.seen[len(tier1_states) :]
    assert len(tier2_states) == 1, "yalnız ev tarafının karardan önce haberi var"
    assert tier2_states[0]["team"] == "Galatasaray"
    assert [entry["title"] for entry in tier2_states[0]["news"]] == [EARLY, CHILD]
    for leak in (BLOCKED, ROOT, AWAY_LATE, SEEN_LATE):
        assert all(leak not in _titles(s) for s in tier2_states), leak
    markers = sorted(
        row["question_id"]
        for row in line.db.match_answers
        if row["question_id"].startswith("side_status:")
    )
    assert markers == ["side_status:away:no_news", "side_status:home:asked"]
