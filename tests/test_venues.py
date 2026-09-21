from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.venues import (
    VenuesResult,
    _forecast_path,
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


def test_forecast_path_requests_gmt_explicitly() -> None:
    """review Important — M5'in İSTEK yarısı: vendor varsayılanına GÜVENMEK yerine
    `timezone=GMT` AÇIKÇA istenir. Yanıt tarafı AYRICA `weather._require_gmt_response`
    ile doğrulanır (bkz. test_weather.py) — bu iki katmanlı bir savunma, ikisi de gerekli:
    istek parametresi tek başına vendor'ın onu GERÇEKTEN uyguladığını KANITLAMAZ.
    """
    path = _forecast_path(41.1, 29.0, forecast_days=3)
    assert "timezone=GMT" in path


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
        "timezone": "GMT",
        "utc_offset_seconds": 0,
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


def test_collect_venues_rejects_a_naive_commence_time_instead_of_laundering_it(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Minor #2 (review, promoted): `.astimezone(UTC)` bir NAIVE datetime'da SİSTEM YEREL
    saatini varsayıp SESSİZCE aware bir değere çevirir — `_require_utc`i GEÇEN ama YANLIŞ
    bir `kickoff` üretir (`astimezone`'un kendisi hatasız çalışır; guard'ı atlatan LAUNDERING
    tam olarak budur). Bugün `commence_time` her zaman aware (timestamptz) olduğu için
    ERİŞİLEMEZ bir dal, ama `collect_venues` bu wiring'in TEK çağıranı — sütun ileride
    `timestamp`e değişirse sessizce RUNNER'IN saat dilimine kayardı. `caplog` kullanılır
    (yalnız `failed_matches` değil): sistem yerel saat dilimine göre laundered değer
    KAZA ESERİ pencere içine düşüp "başarıyla" yazılabilir ya da farklı bir nedenle
    (pencere dışı) düşebilir — ikisi de dışarıdan `failed_matches`e bakan bir testi
    yanıltabilir. Loglanan mesajın KENDİSİ (`tzinfo yok`) guard'ın GERÇEKTEN tetiklendiğini,
    sistemden BAĞIMSIZ biçimde kanıtlar.
    """
    sources_path = _sources_yaml(tmp_path)
    write_robots(tmp_path, "wikidata", "")
    write_robots(tmp_path, "openmeteo", "")
    naive_kickoff = datetime(2026, 9, 19, 17, 0)  # tzinfo YOK
    db = FakeVenuesDb(
        matches={
            "evt-naive": {
                "home_team": "Galatasaray",
                "commence_time": naive_kickoff,
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

    with caplog.at_level(logging.ERROR):
        result = collect_venues(
            db,  # type: ignore[arg-type]
            client,
            sources_path=sources_path,
            robots_dir=tmp_path,
            now=NOW,
        )

    assert result.failed_matches == ("evt-naive",)
    assert not any(row["entity_kind"] == "match_weather" for row in db.rows)
    assert "tzinfo yok" in caplog.text, (
        f"naive kickoff SESSİZCE laundering'e uğramış olabilir: {caplog.text}"
    )


def test_collect_venues_isolates_a_due_matches_query_failure(tmp_path: Path) -> None:
    """Minor #3 (review, promoted): `_due_matches`in SQL'i koordinat commit edildikten
    SONRA düşse bile arıza `collect_venues`in KENDİSİNDE izole edilmeli — `_fetch_venues_
    command`ı, `main()`i atlayıp ÇIPLAK traceback olarak main()'e sızmamalı (aksi hâlde
    `EXIT_SOURCE_FAILED` yok, adlandırılmış stdout satırı yok — yalnız teşhissiz bir exit
    kodu). Koordinat bu senaryoda GERÇEKTEN yazılıp commit edildiği için `written` onu
    sayar; yalnız SONRAKİ sorgu arızası bu turu `failed_venues`e düşürür.
    """
    sources_path = _sources_yaml(tmp_path)
    write_robots(tmp_path, "wikidata", "")
    write_robots(tmp_path, "openmeteo", "")
    db = FakeVenuesDb(due_query_fails=True)
    wikidata_ok = _json_response(_wikidata_payload("Q81492", 41.1, 29.0))
    client = httpx.Client(transport=httpx.MockTransport(_handler(wikidata_ok, [])))

    result = collect_venues(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert result.failed_venues == ("Q81492",), "sorgu arızası venue try'ının İÇİNDE izole edilmeli"
    assert result.written == 1, "koordinat GERÇEKTEN commit edildi, kaybolmamalı"


def test_collect_venues_does_not_count_a_venue_write_whose_commit_fails(tmp_path: Path) -> None:
    """Minor #4 (review, promoted) — Faz 0'ın G1'iyle AYNI sınıf arıza: "not failed" ile
    "durably written" aynı şey değildir. `commit()` düşerse satır kalıcı DEĞİLDİR;
    `written`i önceden artırmak, hiç kalıcı olmamış veri için "N yeni gözlem" basmak demektir.
    """
    sources_path = _sources_yaml(tmp_path)
    write_robots(tmp_path, "wikidata", "")
    write_robots(tmp_path, "openmeteo", "")
    db = FakeVenuesDb(commit_fails=lambda _db: True)
    wikidata_ok = _json_response(_wikidata_payload("Q81492", 41.1, 29.0))
    client = httpx.Client(transport=httpx.MockTransport(_handler(wikidata_ok, [])))

    result = collect_venues(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert result.written == 0
    assert result.failed_venues == ("Q81492",)
    assert db.rollbacks == 1


def test_collect_venues_does_not_count_a_weather_write_whose_commit_fails(tmp_path: Path) -> None:
    """Minor #4 (review, promoted), İKİNCİ örnek — `venues.py:199`'daki hava-yazma satırı,
    stadyum-yazma satırından AYRI (`venues.py:181`). Koordinatın commit'i BAŞARILI olsun
    (`written` onu doğru sayar); yalnız hava gözleminin commit'i düşsün — `written` o
    ikinci satırı SAYMAMALI.
    """
    sources_path = _sources_yaml(tmp_path)
    write_robots(tmp_path, "wikidata", "")
    write_robots(tmp_path, "openmeteo", "")
    db = FakeVenuesDb(
        matches={
            "evt1": {
                "home_team": "Galatasaray",
                "commence_time": datetime(2026, 9, 19, 17, 0, tzinfo=UTC),
                "sealed_at": None,
            }
        },
        commit_fails=lambda current: current.commits >= 1,
    )
    wikidata_ok = _json_response(_wikidata_payload("Q81492", 41.1, 29.0))
    openmeteo_ok = _json_response(_openmeteo_payload(["2026-09-19T17:00"], [20.3]))
    client = httpx.Client(transport=httpx.MockTransport(_handler(wikidata_ok, [openmeteo_ok])))

    result = collect_venues(
        db,  # type: ignore[arg-type]
        client,
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    assert result.written == 1  # yalnız koordinat — hava commit'i düştü, sayılmadı
    assert result.failed_venues == ()
    assert result.failed_matches == ("evt1",)
    assert db.commits == 1  # koordinatın commit'i başarılı, hava'nınki denenip düştü
    assert db.rollbacks == 1
