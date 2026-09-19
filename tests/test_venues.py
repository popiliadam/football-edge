from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.venues import (
    VenuesResult,
    collect_venues,
    parse_entity_coordinates,
    venue_observation,
)
from tests.fake_sources import write_robots
from tests.fake_venues_db import FakeVenuesDb

# Q170980 (brief'in orijinal QID'si) "obelisk" kavram-öğesi çıktı — P625 taşımıyor
# (ölçüldü 2026-09-19, ham yanıt tests/fixtures/venue/wikidata-Q170980.json'da duruyor,
# testlerde KULLANILMIYOR). Yerine Q81492 = Rams Park (Galatasaray SK'nin stadyumu,
# eski adıyla Türk Telekom Stadyumu/Arena) seçildi — P625 taşıdığı doğrulandı.
FIXTURE = Path("tests/fixtures/venue/wikidata-Q81492.json")
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
_TRT = timezone(timedelta(hours=3))


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


# ---------------------------------------------------------------------------
# `collect_venues` kablolaması (M1/M5, merge adımı) — `tests/fake_venues_db.FakeVenuesDb`
# kullanır (`fake_db.py:FakeLedgerDb` ne `matches.home_team` ne `source_observations`i
# taşıyor, `fake_obs_db.py:FakeObservationDb` ise `matches`i hiç bilmiyor).
# ---------------------------------------------------------------------------


def _sources_yaml(tmp_path: Path) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(
        """
sources:
  - id: wikidata
    base_url: https://wikidata.test
    user_agent: football-edge-test/0.1
    crawl_delay_seconds: 0.0
    robots_verified_at: 2026-09-19
    declared_paths: ['/wiki/Special:EntityData/Q81492.json']
    enabled: true
    access_basis: robots
    terms_url: ''
    note: ''
  - id: openmeteo
    base_url: https://openmeteo.test
    user_agent: football-edge-test/0.1
    crawl_delay_seconds: 0.0
    robots_verified_at: 2026-09-19
    declared_paths: ['/v1/forecast']
    enabled: true
    access_basis: api_terms
    terms_url: https://example.test/terms
    note: ''
""",
        encoding="utf-8",
    )
    return path


def _wikidata_payload(qid: str, latitude: float, longitude: float) -> dict[str, Any]:
    return {
        "entities": {
            qid: {
                "claims": {
                    "P625": [
                        {
                            "mainsnak": {
                                "datavalue": {
                                    "value": {"latitude": latitude, "longitude": longitude}
                                }
                            }
                        }
                    ]
                }
            }
        }
    }


def _openmeteo_payload(hours: list[str], temps: list[float]) -> dict[str, Any]:
    return {
        "elevation": 42.0,
        "hourly": {
            "time": hours,
            "temperature_2m": temps,
            "precipitation": [0.0 for _ in hours],
            "wind_speed_10m": [5.0 for _ in hours],
        },
    }


def _handler(wikidata_response: httpx.Response, openmeteo_responses: list[httpx.Response]) -> Any:
    calls = {"openmeteo": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "wikidata.test" in str(request.url):
            return wikidata_response
        index = calls["openmeteo"]
        calls["openmeteo"] += 1
        return openmeteo_responses[min(index, len(openmeteo_responses) - 1)]

    return handler


def _json_response(payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json=payload, headers={"content-type": "application/json"})


def test_collect_venues_writes_venue_and_weather_observations(tmp_path: Path) -> None:
    """Mutlu yol: stadyum koordinatı + tek ev sahibi maçın hava tahmini birlikte yazılır."""
    sources_path = _sources_yaml(tmp_path)
    write_robots(tmp_path, "wikidata", "")
    write_robots(tmp_path, "openmeteo", "")
    kickoff = datetime(2026, 9, 19, 17, 0, tzinfo=UTC)
    db = FakeVenuesDb(
        matches={"evt1": {"home_team": "Galatasaray", "commence_time": kickoff, "sealed_at": None}}
    )
    wikidata_ok = _json_response(_wikidata_payload("Q81492", 41.1, 29.0))
    openmeteo_ok = _json_response(
        _openmeteo_payload(
            ["2026-09-19T16:00", "2026-09-19T17:00", "2026-09-19T18:00"], [19.0, 20.3, 19.8]
        )
    )
    client = httpx.Client(transport=httpx.MockTransport(_handler(wikidata_ok, [openmeteo_ok])))

    result = collect_venues(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert result == VenuesResult(written=2, failed_venues=(), failed_matches=())
    kinds = {row["entity_kind"] for row in db.rows}
    assert kinds == {"venue", "match_weather"}
    weather_row = next(row for row in db.rows if row["entity_kind"] == "match_weather")
    assert json.loads(weather_row["payload"])["temperature_c"] == 20.3


def test_collect_venues_converts_non_utc_kickoff_before_forecasting(tmp_path: Path) -> None:
    """M5 — ölçülen senaryonun birebir aynısı (task-7-report.md): gerçek maç saati 17:00
    UTC'dir ve fixture'da 20.3°C taşır. Aynı an burada 20:00 TRT (UTC+3) olarak, `matches`
    tablosundan DOĞRU ama UTC'ye ÇEVRİLMEMİŞ biçimde gelir — `collect_venues` bunu
    `parse_forecast`e vermeden ÖNCE `.astimezone(UTC)` ile çevirmezse ya `ContractViolation`
    (`_require_utc`) fırlar ya da (dönüşüm silinip DOĞRUDAN sessizce kırpılsaydı) yanlış
    saate düşerdi; ikisi de bu testte YANLIŞ sonuç/RED verir.
    """
    sources_path = _sources_yaml(tmp_path)
    write_robots(tmp_path, "wikidata", "")
    write_robots(tmp_path, "openmeteo", "")
    mistagged_kickoff = datetime(2026, 9, 19, 20, 0, tzinfo=_TRT)  # gerçekte 17:00 UTC
    db = FakeVenuesDb(
        matches={
            "evt-trt": {
                "home_team": "Galatasaray",
                "commence_time": mistagged_kickoff,
                "sealed_at": None,
            }
        }
    )
    wikidata_ok = _json_response(_wikidata_payload("Q81492", 41.1, 29.0))
    openmeteo_ok = _json_response(
        _openmeteo_payload(
            ["2026-09-19T16:00", "2026-09-19T17:00", "2026-09-19T18:00"], [19.0, 20.3, 19.8]
        )
    )
    client = httpx.Client(transport=httpx.MockTransport(_handler(wikidata_ok, [openmeteo_ok])))

    result = collect_venues(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert result.failed_matches == (), f"UTC'ye çevrilmedi, maç izole edildi: {result}"
    weather_row = next(row for row in db.rows if row["entity_kind"] == "match_weather")
    assert json.loads(weather_row["payload"])["temperature_c"] == 20.3, (
        "yanlış saatlik dilim seçildi — TRT saat sayısı UTC sanılmış olabilir (19.1 beklenirdi "
        "eski/hatalı davranışta)"
    )


def test_collect_venues_isolates_a_failing_venue(tmp_path: Path) -> None:
    sources_path = _sources_yaml(tmp_path)
    write_robots(tmp_path, "wikidata", "")
    write_robots(tmp_path, "openmeteo", "")
    db = FakeVenuesDb(
        matches={
            "evt1": {
                "home_team": "Galatasaray",
                "commence_time": NOW + timedelta(days=1),
                "sealed_at": None,
            }
        }
    )
    wikidata_down = httpx.Response(500, json={"error": "boom"})

    def handler(request: httpx.Request) -> httpx.Response:
        return wikidata_down

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = collect_venues(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert result == VenuesResult(written=0, failed_venues=("Q81492",), failed_matches=())
    assert db.rows == []
    assert db.rollbacks >= 1


def test_collect_venues_isolates_a_failing_match_but_keeps_the_others(tmp_path: Path) -> None:
    """Koordinat toplanır; iki maçtan biri (openmeteo 500) düşer, diğeri YİNE de yazılır —
    `collect_footystats`teki lig izolasyonuyla aynı ilke, maç düzeyinde."""
    sources_path = _sources_yaml(tmp_path)
    write_robots(tmp_path, "wikidata", "")
    write_robots(tmp_path, "openmeteo", "")
    db = FakeVenuesDb(
        matches={
            "evt-ok": {
                "home_team": "Galatasaray",
                "commence_time": datetime(2026, 9, 19, 17, 0, tzinfo=UTC),
                "sealed_at": None,
            },
            "evt-bad": {
                "home_team": "Galatasaray",
                "commence_time": datetime(2026, 9, 19, 18, 0, tzinfo=UTC),
                "sealed_at": None,
            },
        }
    )
    wikidata_ok = _json_response(_wikidata_payload("Q81492", 41.1, 29.0))
    openmeteo_ok = _json_response(
        _openmeteo_payload(["2026-09-19T17:00", "2026-09-19T18:00"], [20.3, 19.8])
    )
    openmeteo_down = httpx.Response(500, json={"error": "boom"})
    client = httpx.Client(
        transport=httpx.MockTransport(_handler(wikidata_ok, [openmeteo_ok, openmeteo_down]))
    )

    result = collect_venues(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert result.written == 2  # 1 stadyum + 1 maç
    assert result.failed_venues == ()
    assert result.failed_matches == ("evt-bad",)
    weather_rows = [row for row in db.rows if row["entity_kind"] == "match_weather"]
    assert [row["entity_key"] for row in weather_rows] == ["evt-ok"]
