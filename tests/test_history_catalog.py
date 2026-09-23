from __future__ import annotations

import re
from pathlib import Path

import pytest

from football_edge.history.catalog import (
    EXTRA,
    MAIN,
    Catalog,
    HistoryLeague,
    declared_paths,
    file_paths,
    kinds_of,
    load_catalog,
    rating_groups,
    season_codes,
    season_of_path,
)
from football_edge.leagues import load_leagues
from tests.history_csv import BRA, E0

REPO = Path(__file__).resolve().parent.parent
CATALOG = REPO / "config/history_leagues.yaml"
SPORT_KEY = re.compile(r"soccer_[a-z0-9_]+")

# kod → (league_id, tier, kind, odds_api_key) — tasarım D19, ölçüm §2.4'teki ek lig dosya adları ve
# R95'in The Odds API ölçümü (`/v4/sports?all=true`, ölçüm §2.5; "" = o lig sunulmuyor).
EXPECTED = {
    "E0": ("eng.1", 1, MAIN, "soccer_epl"),
    "E1": ("eng.2", 2, MAIN, "soccer_efl_champ"),
    "E2": ("eng.3", 3, MAIN, "soccer_england_league1"),
    "E3": ("eng.4", 4, MAIN, "soccer_england_league2"),
    "EC": ("eng.5", 5, MAIN, ""),
    "SC0": ("sco.1", 1, MAIN, "soccer_spl"),
    "SC1": ("sco.2", 2, MAIN, ""),
    "SC2": ("sco.3", 3, MAIN, ""),
    "SC3": ("sco.4", 4, MAIN, ""),
    "D1": ("ger.1", 1, MAIN, "soccer_germany_bundesliga"),
    "D2": ("ger.2", 2, MAIN, "soccer_germany_bundesliga2"),
    "I1": ("ita.1", 1, MAIN, "soccer_italy_serie_a"),
    "I2": ("ita.2", 2, MAIN, "soccer_italy_serie_b"),
    "SP1": ("esp.1", 1, MAIN, "soccer_spain_la_liga"),
    "SP2": ("esp.2", 2, MAIN, "soccer_spain_segunda_division"),
    "F1": ("fra.1", 1, MAIN, "soccer_france_ligue_one"),
    "F2": ("fra.2", 2, MAIN, "soccer_france_ligue_two"),
    "N1": ("ned.1", 1, MAIN, "soccer_netherlands_eredivisie"),
    "B1": ("bel.1", 1, MAIN, "soccer_belgium_first_div"),
    "P1": ("por.1", 1, MAIN, "soccer_portugal_primeira_liga"),
    "T1": ("tur.1", 1, MAIN, "soccer_turkey_super_league"),
    "G1": ("gre.1", 1, MAIN, "soccer_greece_super_league"),
    "ARG": ("arg.1", 1, EXTRA, "soccer_argentina_primera_division"),
    "AUT": ("aut.1", 1, EXTRA, "soccer_austria_bundesliga"),
    "BRA": ("bra.1", 1, EXTRA, "soccer_brazil_campeonato"),
    "CHN": ("chn.1", 1, EXTRA, "soccer_china_superleague"),
    "DNK": ("den.1", 1, EXTRA, "soccer_denmark_superliga"),
    "FIN": ("fin.1", 1, EXTRA, "soccer_finland_veikkausliiga"),
    "IRL": ("irl.1", 1, EXTRA, "soccer_league_of_ireland"),
    "JPN": ("jpn.1", 1, EXTRA, "soccer_japan_j_league"),
    "MEX": ("mex.1", 1, EXTRA, "soccer_mexico_ligamx"),
    "NOR": ("nor.1", 1, EXTRA, "soccer_norway_eliteserien"),
    "POL": ("pol.1", 1, EXTRA, "soccer_poland_ekstraklasa"),
    "ROU": ("rou.1", 1, EXTRA, ""),
    "RUS": ("rus.1", 1, EXTRA, "soccer_russia_premier_league"),
    "SWE": ("swe.1", 1, EXTRA, "soccer_sweden_allsvenskan"),
    "SWZ": ("sui.1", 1, EXTRA, "soccer_switzerland_superleague"),
    "USA": ("usa.1", 1, EXTRA, "soccer_usa_mls"),
}

VALID = """
current_season: "2627"
leagues:
  - {code: E0, league_id: eng.1, name: "Premier League", country: England, tier: 1, kind: main,
     first_season: "2425", odds_api_key: "soccer_epl"}
  - {code: BRA, league_id: bra.1, name: "Serie A", country: Brazil, tier: 1, kind: extra,
     first_season: "", odds_api_key: ""}
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "history_leagues.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_real_catalog_holds_22_main_and_16_extra_leagues_as_designed() -> None:
    catalog = load_catalog(CATALOG)

    assert catalog.current_season == "2627"
    got = {
        league.code: (league.league_id, league.tier, league.kind, league.odds_api_key)
        for league in catalog.leagues
    }
    assert got == EXPECTED
    assert {league.first_season for league in catalog.leagues if league.kind == MAIN} == {"0506"}
    assert {league.first_season for league in catalog.leagues if league.kind == EXTRA} == {""}


def test_the_six_live_leagues_carry_the_key_of_the_live_config() -> None:
    """Canlı defterin anahtarıyla tarihsel katalogunki ayrışırsa köprü ve aday listesi yanlış ligi
    anar (R95)."""
    live = {league.id: league.odds_api_key for league in load_leagues(REPO / "config/leagues.yaml")}
    keys = {league.league_id: league.odds_api_key for league in load_catalog(CATALOG).leagues}

    assert {league_id: keys[league_id] for league_id in live} == live


def test_odds_api_keys_are_unique_and_shaped_like_sport_keys() -> None:
    """Aynı anahtar iki ligde olursa canlı CLV ölçümü iki ligi tek pazar sanar (§8.4)."""
    keys = [league.odds_api_key for league in load_catalog(CATALOG).leagues]
    filled = [key for key in keys if key]

    assert len(filled) == len(set(filled)), f"yinelenen anahtar: {sorted(filled)}"
    assert [key for key in filled if not SPORT_KEY.fullmatch(key)] == []


def test_leagues_the_odds_api_does_not_offer_carry_no_key() -> None:
    keys = {league.code: league.odds_api_key for league in load_catalog(CATALOG).leagues}

    assert {code: keys[code] for code in ("EC", "SC1", "SC2", "SC3", "ROU")} == dict.fromkeys(
        ("EC", "SC1", "SC2", "SC3", "ROU"), ""
    )


def test_the_real_catalog_declares_500_sorted_unique_paths() -> None:
    paths = declared_paths(load_catalog(CATALOG))

    assert len(paths) == 22 * 22 + 16, "22 ana lig × 22 sezon (0506…2627) + 16 ek lig"
    assert list(paths) == sorted(set(paths))
    assert "/mmz4281/0506/E0.csv" in paths and "/mmz4281/2627/G1.csv" in paths
    assert "/new/SWZ.csv" in paths and "/mmz4281/0405/E0.csv" not in paths


def test_a_valid_file_loads_into_frozen_records(tmp_path: Path) -> None:
    catalog = load_catalog(write(tmp_path, VALID))

    assert catalog == Catalog(
        current_season="2627",
        leagues=(
            HistoryLeague(
                "E0", "eng.1", "Premier League", "England", 1, MAIN, "2425", "soccer_epl"
            ),
            HistoryLeague("BRA", "bra.1", "Serie A", "Brazil", 1, EXTRA, "", ""),
        ),
    )


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [("0506", "0708", ("0506", "0607", "0708")), ("2627", "2627", ("2627",))],
)
def test_season_codes_expand_inclusively(first: str, last: str, expected: tuple[str, ...]) -> None:
    assert season_codes(first, last) == expected


@pytest.mark.parametrize(
    ("first", "last"),
    [("0507", "0708"), ("506", "0708"), ("2627", "2526"), ("0506", "26/27")],
)
def test_season_codes_reject_a_malformed_or_reversed_range(first: str, last: str) -> None:
    with pytest.raises(ValueError, match="sezon"):
        season_codes(first, last)


def test_file_paths_give_one_file_per_main_season_and_one_file_per_extra_league() -> None:
    assert file_paths(E0, current_season="2627") == (
        "/mmz4281/2526/E0.csv",
        "/mmz4281/2627/E0.csv",
    )
    assert file_paths(BRA, current_season="2627") == ("/new/BRA.csv",)


def test_a_main_league_first_played_in_the_current_season_declares_one_file(
    tmp_path: Path,
) -> None:
    """`first_season == current_season` geçerlidir: kataloğa yeni giren ligin tek dosyası olur."""
    text = VALID.replace('first_season: "2425"', 'first_season: "2627"', 1)

    assert declared_paths(load_catalog(write(tmp_path, text))) == (
        "/mmz4281/2627/E0.csv",
        "/new/BRA.csv",
    )


@pytest.mark.parametrize(
    ("path", "season"),
    [
        ("/mmz4281/2526/E0.csv", "2526"),
        ("/mmz4281/0506/SC3.csv", "0506"),
        ("/new/BRA.csv", None),
        ("/mmz4281/2526/E0.csv?x=1", None),
    ],
)
def test_season_of_path_reads_the_season_directory(path: str, season: str | None) -> None:
    assert season_of_path(path) == season


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('first_season: "2425"', "first_season: 2425", "dize olmayan"),
        ('first_season: "2425"', "first_season: 0506", "dize olmayan"),
        ('current_season: "2627"', "current_season: 2627", "sezon kodu"),
        ('first_season: "2425"', 'first_season: "2527"', "sezon kodu"),
        ('first_season: "2425"', 'first_season: "2728"', "güncel sezondan sonra"),
        ('first_season: ""', 'first_season: "2425"', "first_season boş olmalı"),
        ("kind: extra", "kind: cup", "kind"),
        ("tier: 1, kind: main", "tier: 0, kind: main", "tier"),
        ("tier: 1, kind: main", "tier: true, kind: main", "tier"),
        ("code: BRA", "code: E0", "yinelenen code"),
        ("league_id: bra.1", "league_id: eng.1", "yinelenen league_id"),
        ("country: Brazil, ", "", "eksik alan"),
        ("country: Brazil, ", "country: Brazil, footystats_path: /x, ", "bilinmeyen alan"),
        ('name: "Serie A"', "name: 7", "dize olmayan"),
    ],
)
def test_an_invalid_catalog_is_refused_by_name(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    assert old in VALID, f"test kurgusu bayat: {old!r}"

    with pytest.raises(ValueError, match=message):
        load_catalog(write(tmp_path, VALID.replace(old, new, 1)))


def test_a_catalog_without_current_season_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="current_season"):
        load_catalog(write(tmp_path, VALID.replace('current_season: "2627"\n', "")))


def test_a_catalog_with_an_unknown_top_level_key_is_refused(tmp_path: Path) -> None:
    """Yanlış yazılmış bir anahtar (ör. `curent_season`) sessizce yok sayılmasın."""
    with pytest.raises(ValueError, match="kökte tam olarak"):
        load_catalog(write(tmp_path, VALID.replace("leagues:\n", "notes: x\nleagues:\n", 1)))


def test_kinds_and_rating_groups_map_every_league_code_read_only() -> None:
    """Elo grubu (R94) ülke, tür katalogdaki tür; eşlemler paylaşıldığı için yazılamaz."""
    catalog = load_catalog(CATALOG)
    codes = {league.code for league in catalog.leagues}

    assert set(kinds_of(catalog)) == codes == set(rating_groups(catalog))
    assert all(rating_groups(catalog)[lg.code] == lg.country for lg in catalog.leagues)
    assert all(kinds_of(catalog)[lg.code] == lg.kind for lg in catalog.leagues)
    with pytest.raises(TypeError):
        kinds_of(catalog)["XX"] = "main"  # type: ignore[index]
