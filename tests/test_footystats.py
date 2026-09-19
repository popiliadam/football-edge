from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.footystats import parse_xg_table

FIXTURE = Path("tests/fixtures/footystats/turkey-super-lig-xg.html")
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def fixture_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.mark.contract
def test_parses_every_team_in_the_league() -> None:
    parsed = parse_xg_table(fixture_html(), league_id="tur.1", observed_at=NOW)
    assert len(parsed) >= 18, f"Süper Lig 18+ takım; {len(parsed)} ayrıştırıldı"


@pytest.mark.contract
def test_payload_carries_the_required_fields_in_plausible_ranges() -> None:
    parsed = parse_xg_table(fixture_html(), league_id="tur.1", observed_at=NOW)
    for entry in parsed:
        assert entry.payload["team_name"]
        assert entry.payload["footystats_id"] > 0
        assert entry.payload["matches_played"] >= 0
        # Sezon toplamı xG: 0 ile 4 gol/maç arası makul. Aralık iddiası, ayrıştırıcının
        # yanlış SÜTUNU okuduğunu yakalar — eksik sütunu değil.
        assert 0.0 <= entry.payload["xg"] <= entry.payload["matches_played"] * 4 + 4
        assert 0.0 <= entry.payload["xga"] <= entry.payload["matches_played"] * 4 + 4


@pytest.mark.contract
def test_entity_key_is_league_scoped_and_stable() -> None:
    parsed = parse_xg_table(fixture_html(), league_id="tur.1", observed_at=NOW)
    keys = tuple(entry.entity_key for entry in parsed)
    assert len(set(keys)) == len(keys), "yinelenen entity_key — join sessizce çoğaltır"
    assert all(key.startswith("tur.1:") for key in keys)


def test_missing_table_raises_rather_than_returning_empty() -> None:
    """Kırılan ayrıştırıcı BOŞ LİSTE döndürmemeli: boş liste sessizce başarı gibi görünür."""
    with pytest.raises(ContractViolation, match="xg-all"):
        parse_xg_table("<html><body>hiçbir şey</body></html>", league_id="tur.1", observed_at=NOW)


def test_renamed_column_raises() -> None:
    """Sütun adı değişirse indeksle okumak YANLIŞ SAYIYI sessizce alır. Ad kontrol edilir."""
    broken = (
        "<table class='xg-all'><thead><tr><th>#</th><th>Team</th><th>MP</th>"
        "<th>ExpG</th><th>ExpGA</th></tr></thead><tbody></tbody></table>"
    )
    with pytest.raises(ContractViolation, match="xG"):
        parse_xg_table(broken, league_id="tur.1", observed_at=NOW)
