"""`link_officials` gerçek Postgres'te (spec 2026-10-02 §4, §9/3): değişiklik kaydı, İstanbul günü.

Yalnız atılabilir yerel kapta koşar (`tests/site_db.py`): `scripts/sandbox_db.sh test
tests/test_site_officials_db.py`. Değişken yoksa yerelde SKIP, CI'da FAIL. Her test şablonun kendi
kopyasında (`site_db_each`): append-only tablo temizlenmez, veritabanı atılır.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import psycopg
import pytest

from football_edge.collector import Observation
from football_edge.officials import LinkResult, TeamMap, find_candidates, link_officials
from tests.site_db import site_cluster, site_db_each

pytestmark = pytest.mark.sitedb

LABEL = "Trendyol Süper Lig Adnan Süvari Sezonu"
TEAMS = TeamMap("Süper Lig", "tur.1", {"trabzonspor": "Trabzonspor", "galatasaray": "Galatasaray"})
MATCH = "m-ts-gs"
# İstanbul günleri: MATCH 20:00 İst. 19 Eylül · m-gece 00:00 İst. 19 Eylül (UTC'de 18'i) ·
# m-ertesi 00:00 İst. 20 Eylül (UTC'de 19'u) · m-baska-lig aynı takımlar, başka lig.
MATCHES = (
    (MATCH, "tur.1", "2026-09-19T17:00:00+00:00", "Trabzonspor", "Galatasaray"),
    ("m-gece", "tur.1", "2026-09-18T21:00:00+00:00", "Goztepe", "Samsunspor"),
    ("m-ertesi", "tur.1", "2026-09-19T21:00:00+00:00", "Goztepe", "Samsunspor"),
    ("m-baska-lig", "tst.1", "2026-09-19T17:00:00+00:00", "Trabzonspor", "Galatasaray"),
)


def _seed(url: str) -> None:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO leagues VALUES "
            "('tur.1', 'k-tur', 'Süper Lig', 'Türkiye', 'tr', 'TR', true), "
            "('tst.1', 'k-tst', 'Deneme Ligi', 'Testland', 'tr', 'TR', true)"
        )
        cur.executemany(
            "INSERT INTO matches (id, league_id, commence_time, home_team, away_team) "
            "VALUES (%s, %s, %s, %s, %s)",
            MATCHES,
        )


def _round(referee: str) -> tuple[Observation, ...]:
    return (
        Observation(
            source_id="tff",
            entity_kind="fixture_official",
            entity_key="trabzonspor|galatasaray|2026-09-19",
            observed_at=datetime(2026, 9, 17, 9, 0, tzinfo=UTC),
            payload={
                "home_team": "TRABZONSPOR A.Ş.",
                "away_team": "GALATASARAY A.Ş.",
                "referee": referee,
                "league": LABEL,
                "match_date": "2026-09-19",
                "kickoff_local": "20:00",
            },
        ),
    )


def _at(hour: int) -> datetime:
    return datetime(2026, 9, 17, hour, 0, tzinfo=UTC)


def _link(url: str, referee: str, hour: int) -> LinkResult:
    with psycopg.connect(url) as conn:
        return link_officials(conn, _round(referee), team_map=TEAMS, now=_at(hour))


def _recorded(url: str) -> list[tuple[str, str, datetime]]:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT match_id, referee, seen_at FROM match_officials ORDER BY id")
        return [(str(a), str(b), c) for a, b, c in cur.fetchall()]


def test_the_same_referee_is_not_recorded_twice(site_db_each: str) -> None:
    _seed(site_db_each)
    first = _link(site_db_each, "ALİ HAKEM", 9)
    second = _link(site_db_each, "ALİ HAKEM", 10)

    assert (first.linked, first.written, second.linked, second.written) == (1, 1, 1, 0)
    assert _recorded(site_db_each) == [(MATCH, "ALİ HAKEM", _at(9))]


def test_x_then_y_then_x_is_three_rows(site_db_each: str) -> None:
    """I-5 burada oluşmaz: karşılaştırma maçın SON kayıtlı hakemiyledir, içerik hash'iyle değil."""
    _seed(site_db_each)
    for referee, hour in (("ALİ HAKEM", 9), ("VELİ HAKEM", 10), ("ALİ HAKEM", 11)):
        _link(site_db_each, referee, hour)

    assert _recorded(site_db_each) == [
        (MATCH, "ALİ HAKEM", _at(9)),
        (MATCH, "VELİ HAKEM", _at(10)),
        (MATCH, "ALİ HAKEM", _at(11)),
    ]


def test_candidates_are_the_istanbul_day_of_the_target_league(site_db_each: str) -> None:
    _seed(site_db_each)
    with psycopg.connect(site_db_each) as conn:
        found = find_candidates(conn, "tur.1", [date(2026, 9, 19)])

    assert sorted(candidate.match_id for candidate in found) == ["m-gece", MATCH]
