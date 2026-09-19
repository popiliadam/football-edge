from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.weather import parse_forecast

FIXTURE = Path("tests/fixtures/venue/open-meteo.json")
_TRT = timezone(timedelta(hours=3))


def payload() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.contract
def test_picks_the_hour_nearest_to_kickoff() -> None:
    body = payload()
    first_hour = str(body["hourly"]["time"][0])  # type: ignore[index]
    kickoff = datetime.fromisoformat(first_hour).replace(tzinfo=UTC)
    values = parse_forecast(body, kickoff)
    assert values["temperature_c"] == float(body["hourly"]["temperature_2m"][0])  # type: ignore[index]


@pytest.mark.contract
def test_elevation_comes_straight_from_the_response() -> None:
    """Rakım için ayrı kaynak yok: Open-Meteo zaten veriyor."""
    values = parse_forecast(payload(), datetime(2026, 9, 19, 0, 0, tzinfo=UTC))
    assert values["elevation_m"] == float(payload()["elevation"])  # type: ignore[index]


def test_kickoff_outside_the_forecast_window_raises() -> None:
    """Tahmin penceresi dışındaki saat için EN YAKIN saati vermek sessiz yanlış veridir."""
    with pytest.raises(ContractViolation, match="pencere"):
        parse_forecast(payload(), datetime(2030, 1, 1, 12, 0, tzinfo=UTC))


def test_naive_kickoff_raises() -> None:
    """review (Important): dilimsiz `kickoff` sessizce UTC SANILAMAZ.

    Eski kod `kickoff.replace(tzinfo=None)` ile dilimi doğrudan atıyordu — naive bir
    `kickoff` de zaten UTC farz ediliyordu, hatasız. Artık `tzinfo=None` reddedilir.
    """
    naive = datetime(2026, 9, 19, 17, 0)
    with pytest.raises(ContractViolation, match="UTC"):
        parse_forecast(payload(), naive)


@pytest.mark.contract
def test_mistagged_timezone_kickoff_raises_instead_of_silently_shifting() -> None:
    """review (Important) — ölçülmüş, somut senaryo.

    Gerçek maç saati 17:00 UTC'dir (fixture: index 17, `temperature_c=20.3`). Çağıran onu
    DOĞRU biçimde 20:00 TRT (UTC+3) olarak etiketler ama UTC'ye ÇEVİRMEDEN geçirirse: eski
    kod dilimi sessizce atıp "20:00" rakamlarını UTC sanıyor ve index 20'yi
    (`temperature_c=19.1`) seçiyordu — pencere İÇİNDE, `_MAX_GAP` hiç tetiklenmeden,
    makul görünen ama YANLIŞ bir sayı (ölçüldü, bu testten önce, düzeltilmemiş kodla).
    Artık dönüştürülmüyor, REDDEDİLİYOR: çağıran `.astimezone(UTC)`i kendisi çağırmalı.
    """
    mistagged_20_trt = datetime(2026, 9, 19, 20, 0, tzinfo=_TRT)  # gerçekte 17:00 UTC
    with pytest.raises(ContractViolation, match="UTC"):
        parse_forecast(payload(), mistagged_20_trt)


@pytest.mark.contract
def test_picks_the_nearer_of_two_adjacent_hours() -> None:
    """review (Minor #2): eski test kickoff'u TAM saat başına eşitliyordu (fark=0) — bu
    yalnız "birebir eşleşme kendini döner"i kanıtlar, iki KOMŞU aday arasında GERÇEKTEN
    en yakını seçtiğini değil. Fixture'da 17:00=20.3°C, 18:00=19.8°C (farklı, ayırt edici).
    """
    body = payload()
    nearer_to_17 = datetime(2026, 9, 19, 17, 20, tzinfo=UTC)  # 17:00'a 20dk, 18:00'a 40dk
    nearer_to_18 = datetime(2026, 9, 19, 17, 40, tzinfo=UTC)  # 17:00'a 40dk, 18:00'a 20dk
    assert parse_forecast(body, nearer_to_17)["temperature_c"] == 20.3
    assert parse_forecast(body, nearer_to_18)["temperature_c"] == 19.8


def test_missing_hourly_field_raises_a_named_violation() -> None:
    """review (Minor #1): eksik bir saatlik alan çıplak `KeyError` değil, adlandırılmış
    `ContractViolation` vermeli — `venues.parse_entity_coordinates`teki P625 deseniyle
    aynı aile (bu iki dosya TEK bir hata yüzeyi olarak okunmalı).
    """
    body: dict[str, Any] = payload()
    del body["hourly"]["precipitation"]
    first_hour = str(body["hourly"]["time"][0])
    kickoff = datetime.fromisoformat(first_hour).replace(tzinfo=UTC)
    with pytest.raises(ContractViolation, match="precipitation"):
        parse_forecast(body, kickoff)


def test_missing_elevation_field_raises_a_named_violation() -> None:
    """`_payload_value` `_hourly_value`den AYRI bir fonksiyon (liste indekslemiyor) —
    kendi mutasyon kanıtını hak ediyor, `precipitation` testinin onu KAPSADIĞI varsayılmaz.
    """
    body: dict[str, Any] = payload()
    del body["elevation"]
    first_hour = str(body["hourly"]["time"][0])
    kickoff = datetime.fromisoformat(first_hour).replace(tzinfo=UTC)
    with pytest.raises(ContractViolation, match="elevation"):
        parse_forecast(body, kickoff)


def test_response_not_gmt_raises() -> None:
    """review Important — M5'in İSTEK tarafını sağlamlaştırdı, YANIT tarafı doğrulanmamış
    kalmıştı. `hourly.time[]` NAIVE'dir ve `kickoff.replace(tzinfo=None)`e DOĞRUDAN
    karşılaştırılır (bkz. `parse_forecast`) — bu yalnız yanıt GERÇEKTEN GMT'yse doğrudur.
    Vendor `timezone=GMT` isteğini YOK SAYARSA ya da varsayılanı DEĞİŞTİRİRSE, kayma
    `_MAX_GAP`in içinde (48 saatlik yoğun ızgarada neredeyse hep öyle) BAŞKA ama GEÇERLİ bir
    saate iner — `_require_utc`in önlediği TAM AYNI sınıf arıza, turun DİĞER yarısında.
    Burada TRT'nin (+3 saat) ofsetini taşıyan bir yanıt kullanılıyor — M5'in kendi TRT
    senaryosuyla (task-7-report.md) simetrik."""
    body = payload()
    body["utc_offset_seconds"] = 10800  # +3 saat (TRT) — GMT DEĞİL
    first_hour = str(body["hourly"]["time"][0])
    kickoff = datetime.fromisoformat(first_hour).replace(tzinfo=UTC)
    with pytest.raises(ContractViolation, match="GMT"):
        parse_forecast(body, kickoff)


def test_missing_utc_offset_field_raises_a_named_violation() -> None:
    """Alan HİÇ yoksa da (kanıtsız, `None != 0`) aynı ihlal — `.get()` kullanılır, çıplak
    indeksleme değil (bkz. `_require_gmt_response` docstring'i): "kanıtsız" ile "yanlış"
    burada AYNI muameleyi görür."""
    body = payload()
    del body["utc_offset_seconds"]
    first_hour = str(body["hourly"]["time"][0])
    kickoff = datetime.fromisoformat(first_hour).replace(tzinfo=UTC)
    with pytest.raises(ContractViolation, match="GMT"):
        parse_forecast(body, kickoff)
