from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from football_edge.collector import ContractViolation, Observation

SOURCE_ID = "openmeteo"
FORECAST_PATH = "/v1/forecast"
_MAX_GAP = timedelta(hours=1)


def parse_forecast(payload: dict[str, Any], kickoff: datetime) -> dict[str, float]:
    """Maç saatine EN YAKIN saatlik tahmini seçer; pencere dışındaysa patlar.

    Pencere dışı bir saat için "en yakın"ı vermek sessiz yanlış veridir: model onu maç
    saatinin havası sanar. Sızıntı değil ama aynı kadar zararlı — ölçülmemiş bir sayıyı
    ölçülmüş gibi kullanmak.
    """
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
        "temperature_c": float(hourly["temperature_2m"][position]),
        "precipitation_mm": float(hourly["precipitation"][position]),
        "wind_kmh": float(hourly["wind_speed_10m"][position]),
        "elevation_m": float(payload["elevation"]),
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
