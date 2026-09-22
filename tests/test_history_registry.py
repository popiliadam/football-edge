"""`config/sources.yaml`daki `football-data` kaydı katalogdan türer (tasarım D20, R7, R59).

`declared_paths` gerçekten çekilen yollardır; `sync` beyan edilmemiş yolu istemez. Bu test iki
listenin EŞİT olduğunu zorlar: fetched ⊆ declared bağı yapıdan gelir, `sources.py` değişmez.
"""

from __future__ import annotations

from pathlib import Path

from football_edge.history.catalog import declared_paths, load_catalog
from football_edge.history.sync import SOURCE_ID
from football_edge.sources import Source, audit_offline, load_sources

REPO = Path(__file__).resolve().parent.parent
ROBOTS = REPO / "config/robots"


def _entry() -> Source:
    (entry,) = [s for s in load_sources(REPO / "config/sources.yaml") if s.id == SOURCE_ID]
    return entry


def test_declared_paths_are_exactly_the_catalog_expansion() -> None:
    declared = _entry().declared_paths
    expected = set(declared_paths(load_catalog(REPO / "config/history_leagues.yaml")))

    missing, extra = sorted(expected - set(declared)), sorted(set(declared) - expected)
    assert (missing, extra) == ([], []), (
        f"eksik {missing[:3]}…, fazla {extra[:3]}… — declared_paths'i katalogdan yeniden üret"
    )
    assert len(declared) == len(expected), "declared_paths'te yinelenen yol var"


def test_the_source_is_honest_polite_and_robots_based() -> None:
    entry = _entry()

    assert entry.base_url == "https://football-data.co.uk"
    assert entry.user_agent == "football-edge/0.1 (+https://github.com/popiliadam/football-edge)"
    assert entry.crawl_delay_seconds == 3.0
    assert (entry.enabled, entry.access_basis, entry.terms_url) == (True, "robots", "")


def test_the_committed_snapshot_is_the_measured_open_policy() -> None:
    text = (ROBOTS / f"{SOURCE_ID}.txt").read_text(encoding="utf-8")

    rules = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    assert rules == ["User-agent: *", "Disallow:"]


def test_every_declared_path_passes_the_offline_source_audit() -> None:
    entry = _entry()

    assert audit_offline((entry,), ROBOTS, entry.robots_verified_at) == ()
