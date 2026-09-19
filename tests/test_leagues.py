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
  - id: tur.1
    odds_api_key: soccer_turkey_super_league
    name: Super Lig
    country: Turkey
    lang: tr
    gl: TR
    active: false
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
