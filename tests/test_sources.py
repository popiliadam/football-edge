from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from football_edge.sources import (
    Source,
    SourceBlocked,
    allows,
    audit_offline,
    enabled_sources,
    guard_path,
    load_sources,
    robots_for,
)

UNDERSTAT_ROBOTS = "User-agent: *\nDisallow: /\n"
# NOT "Disallow: /api/club*" / "/*.php" / "/matches?*" (footystats' REAL robots.txt, measured
# 2026-09-19). `urllib.robotparser.RuleLine` runs disallow patterns through `urllib.parse.quote`,
# which percent-encodes `*`/`?` — the stdlib parser has no wildcard support, so those patterns
# become literal (and unmatchable) strings, not globs. Separately, a UA-specific block fully
# REPLACES the `*` block for that agent (RFC 9309 precedence, which stdlib gets right): the real
# `User-agent: ClaudeBot` stanza here carries only `Crawl-delay`, so ClaudeBot is exempt from
# every `*` rule regardless of wildcard support. Both are load-bearing for real collectors (see
# docs/DEFERRED.md) and both would silently swallow this test if `/c-dl.php` were disallowed only
# via the `*` block — so the block that actually governs `footystats`' configured user_agent
# (ClaudeBot) carries its own literal Disallow line.
FOOTYSTATS_ROBOTS = (
    "User-agent: ClaudeBot\nCrawl-delay: 1\nDisallow: /c-dl.php\n\n"
    "User-agent: *\nDisallow: /api/club/\nDisallow: /c-dl.php\nDisallow: /matches\n"
)
AJANSSPOR_ROBOTS = (
    "User-agent: *\n"
    "Content-Signal: ai-train=no, search=yes, ai-input=yes\n"
    "Disallow: /lineup/\nDisallow: /mac/\nDisallow: /oyuncu/\nDisallow: /lig/\n"
)


def source(**overrides: object) -> Source:
    base = {
        "id": "footystats",
        "base_url": "https://footystats.org",
        "user_agent": "ClaudeBot/1.0 (+https://anthropic.com/claudebot)",
        "crawl_delay_seconds": 1.0,
        "robots_verified_at": date(2026, 9, 19),
        "declared_paths": ("/turkey/super-lig/xg",),
        "enabled": True,
        "note": "",
    }
    return Source(**{**base, **overrides})  # type: ignore[arg-type]


def write_robots(directory: Path, source_id: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{source_id}.txt"
    target.write_text(body, encoding="utf-8")
    return target


def test_site_wide_disallow_blocks_every_path(tmp_path: Path) -> None:
    """Understat: `User-agent: * / Disallow: /`. Spec §3.2/1 — taranmaz."""
    write_robots(tmp_path, "understat", UNDERSTAT_ROBOTS)
    understat = source(id="understat", base_url="https://understat.com")
    parser = robots_for(understat, tmp_path)

    assert allows(parser, understat, "/league/EPL") is False
    assert allows(parser, understat, "/") is False


def test_allowed_path_passes_and_disallowed_path_raises(tmp_path: Path) -> None:
    write_robots(tmp_path, "footystats", FOOTYSTATS_ROBOTS)
    footystats = source()
    parser = robots_for(footystats, tmp_path)

    guard_path(parser, footystats, "/turkey/super-lig/xg")  # patlamamalı
    with pytest.raises(SourceBlocked, match="footystats"):
        guard_path(parser, footystats, "/c-dl.php")


def test_ajansspor_structural_paths_are_closed_but_news_is_open(tmp_path: Path) -> None:
    """robots `/lineup/`, `/mac/`, `/oyuncu/`, `/lig/` kapatıyor — muhtemel 11 ALINMAZ."""
    write_robots(tmp_path, "ajansspor", AJANSSPOR_ROBOTS)
    ajansspor = source(id="ajansspor", base_url="https://ajansspor.com", crawl_delay_seconds=1.0)
    parser = robots_for(ajansspor, tmp_path)

    assert allows(parser, ajansspor, "/lineup/galatasaray") is False
    assert allows(parser, ajansspor, "/mac/12345") is False
    assert allows(parser, ajansspor, "/futbol/galatasaray-haberleri") is True


def test_empty_robots_file_allows_everything(tmp_path: Path) -> None:
    """TFF'de robots.txt YOK (404) ve ClubElo'nunki boş. Boş politika = kısıt yok.

    `RobotFileParser.can_fetch` HİÇ parse edilmemişken False döner; boş gövdeyle parse
    edilince True. İkisini karıştırmak, izinli kaynağı sessizce kapatır.
    """
    write_robots(tmp_path, "tff", "")
    tff = source(id="tff", base_url="https://www.tff.org")
    parser = robots_for(tff, tmp_path)

    assert allows(parser, tff, "/Default.aspx?pageID=600") is True


def test_missing_snapshot_is_a_violation_not_a_pass(tmp_path: Path) -> None:
    """Anlık görüntü yoksa kapı YEŞİL VERMEZ. Ölçülmemiş politika, izin değildir."""
    violations = audit_offline((source(),), tmp_path, date(2026, 9, 19))
    assert any("anlık görüntü yok" in text for text in violations)


def test_declared_path_that_robots_forbids_is_a_violation(tmp_path: Path) -> None:
    """Toplayıcının beyan ettiği yol robots'a uymuyorsa, kod yazılmadan kapı kırmızı verir."""
    write_robots(tmp_path, "footystats", FOOTYSTATS_ROBOTS)
    violations = audit_offline(
        (source(declared_paths=("/turkey/super-lig/xg", "/c-dl.php")),),
        tmp_path,
        date(2026, 9, 19),
    )
    assert any("/c-dl.php" in text for text in violations)


def test_stale_verification_is_a_violation(tmp_path: Path) -> None:
    """robots 30 günden eski ölçüldüyse 'izinli' bir iddia değil, bir hatıradır."""
    write_robots(tmp_path, "footystats", FOOTYSTATS_ROBOTS)
    violations = audit_offline((source(),), tmp_path, date(2026, 11, 1))
    assert any("30 günden eski" in text for text in violations)


def test_disabled_sources_are_not_audited(tmp_path: Path) -> None:
    """Kapalı kaynak taranmıyor; anlık görüntüsü eksik diye kapı kırmızı vermez."""
    assert audit_offline((source(enabled=False),), tmp_path, date(2026, 9, 19)) == ()


def test_registry_loads_and_filters(tmp_path: Path) -> None:
    target = tmp_path / "sources.yaml"
    target.write_text(
        "sources:\n"
        "  - id: footystats\n"
        "    base_url: https://footystats.org\n"
        "    user_agent: ClaudeBot/1.0\n"
        "    crawl_delay_seconds: 1.0\n"
        "    robots_verified_at: 2026-09-19\n"
        "    declared_paths: ['/turkey/super-lig/xg']\n"
        "    enabled: true\n"
        "    note: ''\n"
        "  - id: understat\n"
        "    base_url: https://understat.com\n"
        "    user_agent: ClaudeBot/1.0\n"
        "    crawl_delay_seconds: 1.0\n"
        "    robots_verified_at: 2026-09-19\n"
        "    declared_paths: []\n"
        "    enabled: false\n"
        "    note: 'robots.txt Disallow: / — spec §3.2/1'\n",
        encoding="utf-8",
    )
    loaded = load_sources(target)

    assert len(loaded) == 2
    assert tuple(entry.id for entry in enabled_sources(loaded)) == ("footystats",)
    assert loaded[0].robots_verified_at == date(2026, 9, 19)
