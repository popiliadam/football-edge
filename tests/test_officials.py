"""TFF baş hakemi eşlemesi (spec 2026-10-02 §4): takım adı yapılandırması.

Canlı ad doğrulaması (`test_every_mapped_api_name_was_seen_in_tur1`) yalnız veritabanı adresi varken
koşar ve YALNIZ OKUR (işlem geri alınır); kapıda ve CI'da adıyla SKIP'tir.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from football_edge.collectors.tff import parse_referees
from football_edge.db import connect
from football_edge.naming import normalise_team
from football_edge.officials import load_team_map

REPO = Path(__file__).resolve().parent.parent
TEAMS_YAML = REPO / "config/tff_teams.yaml"
TFF_FIXTURE = REPO / "tests/fixtures/tff/haftanin-maclari-600.html"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
LIVE_VAR = "DATABASE" + "_URL"
needs_live = pytest.mark.skipif(
    not os.getenv(LIVE_VAR), reason=f"SKIP: canlı ad doğrulaması ({LIVE_VAR} yok)"
)


def test_the_committed_team_map_targets_tur1_with_eighteen_teams() -> None:
    team_map = load_team_map(TEAMS_YAML)

    assert (team_map.league_label_contains, team_map.league_id) == ("Süper Lig", "tur.1")
    assert len(team_map.teams) == 18


def test_every_key_is_its_own_normalise_team_output_and_values_are_null_or_text() -> None:
    raw = yaml.safe_load(TEAMS_YAML.read_text(encoding="utf-8"))

    assert [key for key in raw["teams"] if normalise_team(key) != key] == []
    assert all(
        value is None or (isinstance(value, str) and value.strip())
        for value in raw["teams"].values()
    )


def test_every_super_lig_name_in_the_tff_fixture_has_an_entry() -> None:
    """Ölçülen sayfanın (2026-09-19) 9 Süper Lig maçındaki 18 TFF adı YAML'da anahtar olarak var."""
    team_map = load_team_map(TEAMS_YAML)
    parsed = parse_referees(TFF_FIXTURE.read_text(encoding="utf-8"), observed_at=NOW)
    names = {
        normalise_team(entry.payload[side])
        for entry in parsed
        if team_map.matches_league(entry.payload["league"])
        for side in ("home_team", "away_team")
    }

    assert len(names) == 18
    assert names <= set(team_map.teams), sorted(names - set(team_map.teams))


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Trendyol Süper Lig Adnan Süvari Sezonu", True),
        ("TRENDYOL SÜPER LİG", True),
        ("Kadın Futbol Süper Ligi", False),
        ("Kadın Futbol Süper Lig", False),
        ("KADIN FUTBOL SÜPER LIG", False),
        ("Süper Lig U19 Gelişim Ligi", False),
        ("Süper Ligi Play-off", False),
        ("Trendyol 1. Lig", False),
    ],
)
def test_only_the_mens_top_league_block_is_processed(label: str, expected: bool) -> None:
    """Controller düzeltmesi C1: tam ifade, `İ` katlaması, kadın/genç dışlama."""
    assert load_team_map(TEAMS_YAML).matches_league(label) is expected


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("league_id: tur.1\nteams: {galatasaray: Galatasaray}\n", "üst anahtarlar"),
        (
            'league_label_contains: ""\nleague_id: tur.1\nteams: {galatasaray: Galatasaray}\n',
            "boş olmayan metin olmalı",
        ),
        ('league_label_contains: "Süper Lig"\nleague_id: tur.1\nteams: {}\n', "teams boş olmayan"),
        (
            'league_label_contains: "Süper Lig"\nleague_id: tur.1\n'
            'teams: {"GALATASARAY A.Ş.": Galatasaray}\n',
            "normalise_team çıktısı değil",
        ),
        (
            'league_label_contains: "Süper Lig"\nleague_id: tur.1\nteams: {galatasaray: ""}\n',
            "null ya da boş olmayan metin",
        ),
    ],
)
def test_a_malformed_team_map_is_refused_by_name(tmp_path: Path, text: str, needle: str) -> None:
    path = tmp_path / "tff_teams.yaml"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match=needle):
        load_team_map(path)


@needs_live
def test_every_mapped_api_name_was_seen_in_tur1() -> None:
    """Spec §4: her API adı `tur.1`de GERÇEKTEN görülmüş olmalı. Yalnız okur; işlem geri alınır."""
    team_map = load_team_map(TEAMS_YAML)
    names = sorted({name for name in team_map.teams.values() if name is not None})
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                "SELECT DISTINCT side.name FROM matches m "
                "CROSS JOIN LATERAL (VALUES (m.home_team), (m.away_team)) AS side(name) "
                "WHERE m.league_id = %s AND side.name = ANY(%s)",
                (team_map.league_id, names),
            )
            seen = {str(row[0]) for row in cur.fetchall()}
    finally:
        conn.rollback()
        conn.close()

    assert sorted(set(names) - seen) == []
