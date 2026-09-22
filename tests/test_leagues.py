from __future__ import annotations

from pathlib import Path

import pytest

from football_edge.leagues import League, active_leagues, load_leagues

VALID = """
leagues:
  - id: eng.1
    odds_api_key: soccer_epl
    name: Premier League
    country: England
    lang: en
    gl: GB
    active: true
    footystats_path: /england/premier-league/xg
  - id: tur.1
    odds_api_key: soccer_turkey_super_league
    name: Super Lig
    country: Turkey
    lang: tr
    gl: TR
    active: false
    footystats_path: /turkey/super-lig/xg
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "leagues.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_all_leagues(tmp_path: Path) -> None:
    leagues = load_leagues(write(tmp_path, VALID))
    assert len(leagues) == 2
    assert leagues[0] == League(
        id="eng.1",
        odds_api_key="soccer_epl",
        name="Premier League",
        country="England",
        lang="en",
        gl="GB",
        active=True,
        footystats_path="/england/premier-league/xg",
    )


def test_active_leagues_filters(tmp_path: Path) -> None:
    leagues = load_leagues(write(tmp_path, VALID))
    assert tuple(lg.id for lg in active_leagues(leagues)) == ("eng.1",)


def test_missing_field_raises(tmp_path: Path) -> None:
    text = VALID.replace("    country: England\n", "")
    with pytest.raises(ValueError, match="eksik alan"):
        load_leagues(write(tmp_path, text))


def test_unknown_field_raises(tmp_path: Path) -> None:
    text = VALID.replace("    gl: GB\n", "    gl: GB\n    tier: 1\n")
    with pytest.raises(ValueError, match="bilinmeyen alan"):
        load_leagues(write(tmp_path, text))


def test_duplicate_id_raises(tmp_path: Path) -> None:
    text = VALID.replace("id: tur.1", "id: eng.1")
    with pytest.raises(ValueError, match="yinelenen"):
        load_leagues(write(tmp_path, text))


# ── İz A (2026-09-23): `footystats_path` isteğe bağlı ───────────────────────
# Her ligin footystats sayfası yok; alan zorunlu kalırsa sayfası olmayan lig ya
# yapılandırılamaz ya da uydurma bir yol taşır (toplayıcı onu isteyip düşer).

WITHOUT_FOOTYSTATS = """
leagues:
  - id: ned.1
    odds_api_key: soccer_netherlands_eredivisie
    name: Eredivisie
    country: Netherlands
    lang: nl
    gl: NL
    active: false
"""


def test_footystats_path_may_be_absent_and_reads_as_none(tmp_path: Path) -> None:
    (league,) = load_leagues(write(tmp_path, WITHOUT_FOOTYSTATS))
    assert league.footystats_path is None


def test_footystats_path_when_present_must_be_an_absolute_path(tmp_path: Path) -> None:
    """Boş anahtar (`footystats_path:` → None) ya da göreli yol sessizce "sayfa yok"
    sayılmaz: yazılmışsa gerçek bir yol olmalı, yoksa satır hiç yazılmamalı."""
    for bad in ("    footystats_path:\n", "    footystats_path: netherlands/x\n"):
        with pytest.raises(ValueError, match="footystats_path"):
            load_leagues(write(tmp_path, WITHOUT_FOOTYSTATS + bad))


def test_league_without_footystats_path_can_be_built_directly() -> None:
    league = League(
        id="aut.1",
        odds_api_key="soccer_austria_bundesliga",
        name="Bundesliga",
        country="Austria",
        lang="de",
        gl="AT",
        active=False,
    )
    assert league.footystats_path is None


# ── Canlı altı ligin davranışı SABİT (İz A) ─────────────────────────────────
# Gerçek `config/leagues.yaml`e karşı: lig eklemek ya da alanı isteğe bağlı yapmak, bugün
# toplanan altı ligin HİÇBİR alanını değiştirmemeli — kimliği, anahtarı, footystats yolu,
# sırası (toplama sırası = kredi harcama sırası) dâhil.
REPO = Path(__file__).resolve().parents[1]

LIVE_SIX = (
    League(
        "eng.1",
        "soccer_epl",
        "Premier League",
        "England",
        "en",
        "GB",
        True,
        "/england/premier-league/xg",
    ),
    League(
        "esp.1", "soccer_spain_la_liga", "La Liga", "Spain", "es", "ES", True, "/spain/la-liga/xg"
    ),
    League(
        "ita.1", "soccer_italy_serie_a", "Serie A", "Italy", "it", "IT", True, "/italy/serie-a/xg"
    ),
    League(
        "ger.1",
        "soccer_germany_bundesliga",
        "Bundesliga",
        "Germany",
        "de",
        "DE",
        True,
        "/germany/bundesliga/xg",
    ),
    League(
        "fra.1",
        "soccer_france_ligue_one",
        "Ligue 1",
        "France",
        "fr",
        "FR",
        True,
        "/france/ligue-1/xg",
    ),
    League(
        "tur.1",
        "soccer_turkey_super_league",
        "Super Lig",
        "Turkey",
        "tr",
        "TR",
        True,
        "/turkey/super-lig/xg",
    ),
)


def test_the_six_live_leagues_are_unchanged_and_are_the_only_active_ones() -> None:
    configured = load_leagues(REPO / "config/leagues.yaml")
    assert configured[: len(LIVE_SIX)] == LIVE_SIX
    assert active_leagues(configured) == LIVE_SIX
