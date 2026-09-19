from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.venues import parse_entity_coordinates, venue_observation

# Q170980 (brief'in orijinal QID'si) "obelisk" kavram-öğesi çıktı — P625 taşımıyor
# (ölçüldü 2026-09-19, ham yanıt tests/fixtures/venue/wikidata-Q170980.json'da duruyor,
# testlerde KULLANILMIYOR). Yerine Q81492 = Rams Park (Galatasaray SK'nin stadyumu,
# eski adıyla Türk Telekom Stadyumu/Arena) seçildi — P625 taşıdığı doğrulandı.
FIXTURE = Path("tests/fixtures/venue/wikidata-Q81492.json")
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


@pytest.mark.contract
def test_reads_coordinates_from_the_rest_payload() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    latitude, longitude = parse_entity_coordinates(payload, "Q81492")
    assert 35.0 < latitude < 43.0, "Türkiye enlem aralığı dışında"
    assert 25.0 < longitude < 45.0


def test_missing_coordinate_claim_raises() -> None:
    payload = {"entities": {"Q1": {"claims": {}}}}
    with pytest.raises(ContractViolation, match="P625"):
        parse_entity_coordinates(payload, "Q1")


def test_swapped_latitude_longitude_is_caught() -> None:
    """Wikidata `value` sözlüğünde lat/lon ADLIDIR; konuma göre okumak ikisini takas eder."""
    payload = {
        "entities": {
            "Q1": {
                "claims": {
                    "P625": [
                        {
                            "mainsnak": {
                                "datavalue": {"value": {"latitude": 41.1, "longitude": 29.0}}
                            }
                        }
                    ]
                }
            }
        }
    }
    assert parse_entity_coordinates(payload, "Q1") == (41.1, 29.0)


def test_observation_is_venue_kinded() -> None:
    entry = venue_observation("Q81492", 41.1, 29.0, observed_at=NOW)
    assert entry.entity_kind == "venue"
    assert entry.entity_key == "Q81492"
