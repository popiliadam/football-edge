from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from football_edge.collector import ContractViolation, Observation

SOURCE_ID = "openmeteo"
FORECAST_PATH = "/v1/forecast"
_MAX_GAP = timedelta(hours=1)


def _require_utc(kickoff: datetime) -> None:
    """`kickoff` UTC-farkında (aware, offset=0) olmalı — ne NAIVE ne BAŞKA bir dilim.

    review (Important, 2026-09-19): eski kod `kickoff.replace(tzinfo=None)` ile dilimi
    SESSİZCE atıyordu. Naive bir `kickoff` da YANLIŞ dilimli (ör. TRT/UTC+3) bir `kickoff`
    da aynı sonucu veriyordu: rakamlar SANKİ zaten UTC'ymiş gibi Open-Meteo'nun
    (`timezone=GMT`) naive saatlik damgalarıyla doğrudan karşılaştırılıyordu.

    Bu TEHLİKELİ bir arıza sınıfıdır çünkü SESSİZ kalır: birkaç saatlik bir kayma
    pencerenin (48 saat, yoğun saatlik ızgara) DIŞINA neredeyse hiç düşmez — BAŞKA ama
    GEÇERLİ bir saate iner, `_MAX_GAP` hiç tetiklenmez. Ölçüldü (bu dosyanın fixture'ına
    karşı, düzeltilmeden önce): gerçek maç saati 17:00 UTC iken, doğru biçimde 20:00 TRT
    etiketlenmiş ama UTC'ye çevrilmemiş bir `kickoff` 19.1°C döndürüyordu — doğrusu
    20.3°C'ydi (bkz. `tests/test_weather.py::
    test_mistagged_timezone_kickoff_raises_instead_of_silently_shifting`). Makul görünen
    ama YANLIŞ bir sayı, hatasız dönüyordu.

    DÖNÜŞTÜRMÜYORUZ, REDDEDİYORUZ: `.astimezone(UTC)` teknik olarak güvenli olsa da, bu
    projede `Observation.observed_at` dahil HER yerde kural "girdi zaten UTC'dir" (bkz.
    `collector.py`, tüm testler `tzinfo=UTC` ile kurulur) — tek bir yerde sessiz dönüşüm
    eklemek bu kuralı istisnalı hâle getirir ve yeni bir dönüşüm yüzeyi (DST, zoneinfo)
    açar. Çağıran `.astimezone(UTC)`i KENDİSİ, açıkça çağırmalı.
    """
    if kickoff.utcoffset() != timedelta(0):
        raise ContractViolation(
            f"{SOURCE_ID}: kickoff UTC olmalı (aware, offset=0); gelen tzinfo={kickoff.tzinfo!r}"
        )


def _hourly_value(hourly: dict[str, Any], key: str, position: int) -> float:
    """`hourly[key][position]`, ama adlandırılmamış `KeyError`/`IndexError` yerine
    `ContractViolation` (review Minor #1): `venues.parse_entity_coordinates`teki P625
    deseniyle AYNI aile — bu iki dosya TEK bir hata yüzeyi olarak okunmalı.
    """
    try:
        return float(hourly[key][position])
    except (KeyError, IndexError) as error:
        raise ContractViolation(f"{SOURCE_ID}: saatlik alan eksik/kısa: '{key}'") from error


def _payload_value(payload: dict[str, Any], key: str) -> float:
    try:
        return float(payload[key])
    except KeyError as error:
        raise ContractViolation(f"{SOURCE_ID}: alan yok: '{key}'") from error


def parse_forecast(payload: dict[str, Any], kickoff: datetime) -> dict[str, float]:
    """Maç saatine EN YAKIN saatlik tahmini seçer; pencere dışındaysa patlar.

    Pencere dışı bir saat için "en yakın"ı vermek sessiz yanlış veridir: model onu maç
    saatinin havası sanar. Sızıntı değil ama aynı kadar zararlı — ölçülmemiş bir sayıyı
    ölçülmüş gibi kullanmak.

    `kickoff` UTC-aware olmalı — bkz. `_require_utc` docstring'i: naive ya da başka
    dilimli bir `kickoff` sessizce YANLIŞ AMA GEÇERLİ bir saate iner, hatasız.
    """
    _require_utc(kickoff)
    hourly = payload.get("hourly", {})
    stamps = hourly.get("time", [])
    if not stamps:
        raise ContractViolation(f"{SOURCE_ID}: saatlik tahmin yok")
    target = kickoff.replace(tzinfo=None)
    parsed = [datetime.fromisoformat(str(stamp)) for stamp in stamps]
    position = min(range(len(parsed)), key=lambda index: abs(parsed[index] - target))
    if abs(parsed[position] - target) > _MAX_GAP:
        raise ContractViolation(
            f"{SOURCE_ID}: maç saati {kickoff.isoformat()} tahmin penceresinin dışında"
        )
    return {
        "temperature_c": _hourly_value(hourly, "temperature_2m", position),
        "precipitation_mm": _hourly_value(hourly, "precipitation", position),
        "wind_kmh": _hourly_value(hourly, "wind_speed_10m", position),
        "elevation_m": _payload_value(payload, "elevation"),
    }


def weather_observation(
    match_id: str, values: dict[str, float], *, observed_at: datetime
) -> Observation:
    """`observed_at` ÇAĞIRANIN sorumluluğudur: buraya FETCH ZAMANI geçirilmeli, tahmin
    penceresindeki saatin KENDİ değeri değil (ölçüldü 2026-09-19).

    Open-Meteo yanıtının hiçbir yerinde "bu tahmin ne zaman üretildi" diyen bir duvar-saati
    alanı yok — `generationtime_ms` bir SÜREDİR (işlem süresi, ör. 0.09 ms), bir zaman damgası
    değil. Tek aday `hourly.time[]`dir, ama o maçın KENDİ saatidir (tahminin HEDEFİ) — maç
    saati fetch anına göre neredeyse HER ZAMAN gelecektedir (aksi hâlde tahmine gerek kalmaz).
    O değeri `observed_at` yaparsak `assert_fresh`in "gelecekte bir gözlem olamaz" korumasi
    (bkz. `collector.assert_fresh`) HER meşru hava gözlemini reddeder — R23'ün "her zaman
    doğru" tuzağının aynası, ters yönde "her zaman yanlış". Fetch zamanı bu tuzağa düşmez:
    herhangi bir sonraki kontrol anına göre her zaman GEÇMİŞTEdir.

    Bu, `assert_fresh`i YİNE de aynı turda (damgalanan `now` ile) çağırmayı meşru KILMAZ
    (R23) — bu fonksiyon zaten çağırmıyor. Anlamlı hâle geldiği yer SONRAKİ bir turdur:
    depolanmış gözlemler taze bir `now`a karşı kontrol edildiğinde, "bu maçın tahminini en
    son ne zaman yeniledik" sorusuna gerçek bir cevap verir.
    """
    return Observation(
        source_id=SOURCE_ID,
        entity_kind="match_weather",
        entity_key=match_id,
        observed_at=observed_at,
        payload=dict(values),
    )
