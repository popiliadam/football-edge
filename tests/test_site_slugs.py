"""Site slug'ları (§8.2): dondurulmuş vektörler. Bir vektör değişirse yayımlanmış URL değişir."""

from __future__ import annotations

from pathlib import Path

import pytest

from football_edge.leagues import load_leagues
from football_edge.site.contract import SITE_LEAGUES_PATH
from football_edge.site.slugs import load_league_slugs, match_slug, slugify

REPO = Path(__file__).resolve().parent.parent
# Yayımlanmış lig URL'leri: bir değeri değiştirmek o ligin bütün URL'lerini değiştirir (AK20 b).
FROZEN_LEAGUE_SLUGS = {
    "eng.1": "premier-league",
    "esp.1": "la-liga",
    "ita.1": "serie-a",
    "ger.1": "bundesliga",
    "fra.1": "ligue-1",
    "tur.1": "super-lig",
    "ned.1": "eredivisie",
    "bel.1": "first-division-a",
    "aut.1": "austrian-bundesliga",
}

FROZEN = [
    ("Beşiktaş JK", "besiktas-jk"),
    ("İstanbul Başakşehir", "istanbul-basaksehir"),
    ("Kasımpaşa", "kasimpasa"),
    ("IRAN", "iran"),
    ("Çaykur Rizespor", "caykur-rizespor"),
    ("Fenerbahçe", "fenerbahce"),
    ("Göztepe", "goztepe"),
    ("Atlético Madrid", "atletico-madrid"),
    ("Borussia Mönchengladbach", "borussia-monchengladbach"),
    ("Deportivo Alavés", "deportivo-alaves"),
    ("Śląsk Wrocław", "slask-wroclaw"),
    ("Bodø/Glimt", "bodo-glimt"),
    ("Straße", "strasse"),
    ("Gaziantep F.K.", "gaziantep-f-k"),
    ("Fatih Karagümrük A.Ş.", "fatih-karagumruk-a-s"),
    ("1. FC Köln", "1-fc-koln"),
    ("Brighton & Hove Albion", "brighton-hove-albion"),
    ("Paris Saint-Germain", "paris-saint-germain"),
    ("Newell's Old Boys", "newells-old-boys"),
    ("  --Real  Madrid--  ", "real-madrid"),
]


@pytest.mark.parametrize(("name", "slug"), FROZEN)
def test_frozen_vectors(name: str, slug: str) -> None:
    assert slugify(name) == slug


@pytest.mark.parametrize("name", ["", "   ", "---", "‘’"])
def test_a_name_without_letters_or_digits_has_no_slug(name: str) -> None:
    with pytest.raises(ValueError, match="slug üretilemedi"):
        slugify(name)


def test_the_match_segment_joins_the_two_team_slugs() -> None:
    assert match_slug("Beşiktaş JK", "Fenerbahçe") == "besiktas-jk-vs-fenerbahce"


def test_slugs_do_not_follow_the_matching_key() -> None:
    """`naming.normalise_team` ekleri atar; URL'ler eşleşme düzeltmesiyle sessizce değişmemeli."""
    assert slugify("Gaziantep FK") != slugify("Gaziantep")


def test_every_configured_league_has_a_frozen_site_slug() -> None:
    """I3: pasif dâhil HER lig (`config/leagues.yaml`) kalıcı bir slug taşır; addan türetilmez."""
    ids = {league.id for league in load_leagues(REPO / "config/leagues.yaml")}
    slugs = load_league_slugs(REPO / SITE_LEAGUES_PATH)

    assert set(slugs) == ids
    assert dict(slugs) == FROZEN_LEAGUE_SLUGS
    assert slugs["ger.1"] != slugs["aut.1"], "ikisi de 'Bundesliga'"


@pytest.mark.parametrize(
    ("body", "needle"),
    [
        ("version: 1\nleague_slugs:\n  a.1: bundesliga\n  b.1: bundesliga\n", "aynı slug"),
        ("version: 1\nleague_slugs:\n  a.1: data\n", "ayrılmış"),
        ("version: 1\nleague_slugs:\n  a.1: track-record\n", "ayrılmış"),
        ("version: 1\nleague_slugs:\n  a.1: Bundesliga\n", "biçim dışı"),
        ("version: 1\nleague_slugs:\n  a.1: _next\n", "biçim dışı"),
        ("version: 2\nleague_slugs:\n  a.1: x\n", "version: 1"),
        ("version: 1\nleague_slugs: {}\n", "boş olmayan"),
    ],
)
def test_a_bad_site_league_config_is_refused(tmp_path: Path, body: str, needle: str) -> None:
    path = tmp_path / "site_leagues.yaml"
    path.write_text(body, encoding="utf-8")

    with pytest.raises(ValueError, match=needle):
        load_league_slugs(path)
