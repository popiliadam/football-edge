"""TFF baş hakemi eşlemesi (spec 2026-10-02 §4): takım adı yapılandırması.

Canlı ad doğrulaması (`test_every_mapped_api_name_was_seen_in_tur1`) yalnız veritabanı adresi varken
koşar ve YALNIZ OKUR (işlem geri alınır); kapıda ve CI'da adıyla SKIP'tir.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import yaml

from football_edge.collector import ContractViolation
from football_edge.collectors.tff import parse_referees
from football_edge.db import connect
from football_edge.naming import normalise_team
from football_edge.officials import (
    Assignment,
    Candidate,
    TeamMap,
    assignment_of,
    load_team_map,
    pending_writes,
    plan_links,
)

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


LABEL = "Trendyol Süper Lig Adnan Süvari Sezonu"
MAP = TeamMap(
    "Süper Lig",
    "tur.1",
    {
        "trabzonspor": "Trabzonspor",
        "galatasaray": "Galatasaray",
        "beşiktaş": "Besiktas JK",
        "kasimpaşa": None,
    },
)
TS_GS = ("TRABZONSPOR A.Ş.", "GALATASARAY A.Ş.")


def _assign(
    home: str, away: str, day: str, *, referee: str = "ALİ HAKEM", league: str = LABEL
) -> Assignment:
    return Assignment(league, home, away, referee, date.fromisoformat(day))


def _game(match_id: str, home: str, away: str, kickoff: str) -> Candidate:
    return Candidate(match_id, home, away, datetime.fromisoformat(kickoff))


def test_an_observation_becomes_an_assignment_with_its_istanbul_date() -> None:
    parsed = parse_referees(TFF_FIXTURE.read_text(encoding="utf-8"), observed_at=NOW)
    (entry,) = [e for e in parsed if e.payload["home_team"] == "KASIMPAŞA A.Ş."]

    assert assignment_of(entry) == Assignment(
        LABEL, "KASIMPAŞA A.Ş.", "TÜMOSAN KONYASPOR", "DAVUT DAKUL ÇELİK", date(2026, 9, 18)
    )


def test_a_tff_name_missing_from_the_yaml_is_red_by_name() -> None:
    with pytest.raises(ContractViolation, match="YENİ KULÜP A.Ş."):
        plan_links([_assign("YENİ KULÜP A.Ş.", "GALATASARAY A.Ş.", "2026-09-19")], [], MAP)


def test_a_block_outside_the_label_is_counted_not_processed() -> None:
    plan = plan_links(
        [_assign("YENİ KULÜP", "BAŞKA KULÜP", "2026-09-19", league="Trendyol 1. Lig")], [], MAP
    )

    assert (plan.links, plan.other_league) == ((), 1)


def test_a_null_alias_is_awaiting_not_red() -> None:
    games = [_game("m1", "Kasimpasa", "Besiktas JK", "2026-09-19T17:00:00+00:00")]
    plan = plan_links([_assign("KASIMPAŞA A.Ş.", "BEŞİKTAŞ A.Ş.", "2026-09-19")], games, MAP)

    assert (plan.links, plan.awaiting_alias, plan.not_in_db) == ((), 1, 0)


@pytest.mark.parametrize(
    ("day", "kickoff"),
    [
        ("2026-09-19", "2026-09-18T22:00:00+00:00"),  # 01:00 İstanbul: UTC'de önceki gün
        ("2026-09-18", "2026-09-18T20:30:00+00:00"),  # 23:30 İstanbul: UTC'de aynı gün
    ],
)
def test_the_match_day_is_the_istanbul_calendar_day(day: str, kickoff: str) -> None:
    games = [_game("m1", "Trabzonspor", "Galatasaray", kickoff)]

    assert plan_links([_assign(*TS_GS, day)], games, MAP).links == (("m1", "ALİ HAKEM"),)


def test_the_utc_day_is_not_the_match_day() -> None:
    games = [_game("m1", "Trabzonspor", "Galatasaray", "2026-09-18T22:00:00+00:00")]
    plan = plan_links([_assign(*TS_GS, "2026-09-18")], games, MAP)

    assert (plan.links, plan.not_in_db) == ((), 1)


def test_no_match_in_the_db_is_counted_not_red() -> None:
    plan = plan_links([_assign(*TS_GS, "2026-09-19")], [], MAP)

    assert (plan.links, plan.not_in_db) == ((), 1)


def test_two_db_matches_on_the_same_istanbul_day_are_red() -> None:
    games = [
        _game("m1", "Trabzonspor", "Galatasaray", "2026-09-19T12:00:00+00:00"),
        _game("m2", "Trabzonspor", "Galatasaray", "2026-09-19T17:00:00+00:00"),
    ]
    with pytest.raises(ContractViolation, match="2 maç"):
        plan_links([_assign(*TS_GS, "2026-09-19")], games, MAP)


def test_only_a_changed_or_first_referee_is_written() -> None:
    now = datetime(2026, 9, 17, 9, 0, tzinfo=UTC)
    links = (("m1", "ALİ"), ("m2", "VELİ"), ("m3", "CAN"))

    assert pending_writes(links, {"m1": "ALİ", "m2": "ESKİ"}, now) == (
        ("m2", "VELİ", now),
        ("m3", "CAN", now),
    )


def test_the_fixture_round_with_the_committed_yaml_is_red_nowhere() -> None:
    """Ölçülen tur: 62 satır, 9'u Süper Lig; KASIMPAŞA–KONYASPOR alias bekler, 8'i DB'siz."""
    parsed = parse_referees(TFF_FIXTURE.read_text(encoding="utf-8"), observed_at=NOW)
    plan = plan_links([assignment_of(e) for e in parsed], [], load_team_map(TEAMS_YAML))

    assert (plan.links, plan.not_in_db, plan.awaiting_alias, plan.other_league) == ((), 8, 1, 53)


# ── Review Focus ──────────────────────────────────────────────────────────────────────────────


def test_review_focus_another_super_lig_block_is_counted_not_processed() -> None:
    """Controller düzeltmesi C1: kadın ligi bloğu YAML'da OLAN adlarla aynı gün aynı rakiple
    oynasa bile erkek maçına bağlanmaz — lig dışı sayılır, işlenmez."""
    women = "Turkcell Kadın Futbol Süper Ligi"
    games = [_game("m1", "Trabzonspor", "Galatasaray", "2026-09-19T17:00:00+00:00")]
    plan = plan_links([_assign(*TS_GS, "2026-09-19", league=women)], games, MAP)

    assert (plan.links, plan.other_league) == ((), 1)


def test_review_focus_the_same_match_twice_with_one_referee_links_once() -> None:
    games = [_game("m1", "Trabzonspor", "Galatasaray", "2026-09-19T17:00:00+00:00")]
    rows = [_assign(*TS_GS, "2026-09-19"), _assign(*TS_GS, "2026-09-19")]

    assert plan_links(rows, games, MAP).links == (("m1", "ALİ HAKEM"),)


def test_review_focus_the_same_match_with_two_referees_is_red() -> None:
    games = [_game("m1", "Trabzonspor", "Galatasaray", "2026-09-19T17:00:00+00:00")]
    rows = [_assign(*TS_GS, "2026-09-19"), _assign(*TS_GS, "2026-09-19", referee="VELİ HAKEM")]

    with pytest.raises(ContractViolation, match="iki farklı hakem"):
        plan_links(rows, games, MAP)


@pytest.mark.parametrize("referee", ["", "A" * 81, "<b>ALİ</b>", "ALİ http://x.invalid"])
def test_review_focus_an_unpublishable_referee_text_is_red_before_the_db(referee: str) -> None:
    with pytest.raises(ContractViolation, match="hakem metni sözleşme dışı"):
        plan_links([_assign(*TS_GS, "2026-09-19", referee=referee)], [], MAP)


def test_review_focus_reversed_home_and_away_is_not_linked_but_warned(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="football_edge.officials")
    games = [_game("m1", "Galatasaray", "Trabzonspor", "2026-09-19T17:00:00+00:00")]
    plan = plan_links([_assign(*TS_GS, "2026-09-19")], games, MAP)

    assert (plan.links, plan.not_in_db) == ((), 1)
    assert "ters ev/deplasman" in caplog.text
