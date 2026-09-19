from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
import psycopg

from football_edge.collector import ContractViolation, Observation, fetch_text
from football_edge.collectors.weather import FORECAST_PATH, parse_forecast, weather_observation
from football_edge.observations import write_observations
from football_edge.sources import Source, enabled_sources, load_sources, robots_for

LOGGER = logging.getLogger("football_edge.collectors.venues")

SOURCE_ID = "wikidata"
ENTITY_PATH = "/wiki/Special:EntityData/{qid}.json"


def parse_entity_coordinates(payload: dict[str, Any], qid: str) -> tuple[float, float]:
    """P625 (koordinat konumu) talebinden (enlem, boylam).

    SPARQL DEĞİL REST: `Special:EntityData/<QID>.json` düz bir GET'tir. SPARQL ucu yerel
    `outward_action_gate` tarafından `net_post` olarak engelleniyor (ölçüldü 2026-09-19) ve
    tek bir varlık için zaten gereksiz.
    """
    claims = payload.get("entities", {}).get(qid, {}).get("claims", {})
    statements = claims.get("P625")
    if not statements:
        raise ContractViolation(f"{SOURCE_ID}: {qid} için P625 (koordinat) yok")
    value = statements[0]["mainsnak"]["datavalue"]["value"]
    # Alanlar ADLA okunur: konumla okumak enlem/boylamı takas eder ve hava tahmini
    # başka bir kıtadan gelir — hata vermeden.
    return float(value["latitude"]), float(value["longitude"])


def venue_observation(
    qid: str, latitude: float, longitude: float, *, observed_at: datetime
) -> Observation:
    return Observation(
        source_id=SOURCE_ID,
        entity_kind="venue",
        entity_key=qid,
        observed_at=observed_at,
        payload={"latitude": latitude, "longitude": longitude},
    )


# ---------------------------------------------------------------------------
# CLI kablolaması (`fetch-venues`) — Task 7'nin R1 gereği ERTELEDİĞİ bileşim.
#
# `config/sources.yaml`nin wikidata kaydı TEK bir declared_path taşır (R7: beyan edilen
# yol GERÇEKTEN fetch edilen olmalı, önek değil) — bu yüzden bu demet de TEK girdi taşır.
# Genişletmek önce sources.yaml'a yeni bir declared_path eklemeyi gerektirir. `home_team`
# The Odds API'nin kanonik ad uzayından (spec §5.3, `matches.home_team` ile BİREBİR string
# eşleşir) — kod aday çıkarıp Jev'in seçtiği TAM varlık eşlemesi Task 11'in işi, burada YOK:
# bu tek, elle doğrulanmış gerçeği (Rams Park = Galatasaray'ın stadyumu) kodlar.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VenueSpec:
    home_team: str
    qid: str


VENUES: tuple[VenueSpec, ...] = (VenueSpec(home_team="Galatasaray", qid="Q81492"),)

_HOURLY_FIELDS = "temperature_2m,precipitation,wind_speed_10m"


def _forecast_path(latitude: float, longitude: float, *, forecast_days: int) -> str:
    query = urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": _HOURLY_FIELDS,
            "forecast_days": forecast_days,
            # Review Important (M5'in eksik yarısı): `parse_forecast` saatlik damgaları NAIVE
            # karşılaştırır, bu yalnız yanıt GMT'yse doğrudur. Vendor varsayılanına GÜVENMEK
            # yerine AÇIKÇA istenir — `weather._require_gmt_response` yanıtı AYRICA doğrular,
            # bu parametre yok sayılsa/değişse bile sessizce geçilmesin diye.
            "timezone": "GMT",
        }
    )
    return f"{FORECAST_PATH}?{query}"


@dataclass(frozen=True)
class VenuesResult:
    written: int
    # Koordinatı toplanamayan stadyum QID'leri — o stadyumun maçları da hiç denenmez
    # (koordinatsız hava tahmini istenemez).
    failed_venues: tuple[str, ...] = ()
    # Koordinat toplandı ama BELİRLİ bir maçın hava tahmini toplanamadı (match_id).
    failed_matches: tuple[str, ...] = ()


def _require_source(sources: tuple[Source, ...], source_id: str) -> Source:
    for entry in enabled_sources(sources):
        if entry.id == source_id:
            return entry
    raise RuntimeError(f"{source_id}: kaynak kaydı yok ya da enabled=false — toplama durduruldu")


def _due_matches(
    conn: psycopg.Connection[Any], home_team: str, now: datetime, horizon_days: int
) -> tuple[tuple[str, datetime], ...]:
    """`home_team`in mühürlenmemiş, ufuk içindeki maçları — `(match_id, commence_time)`.

    Ufuk SINIRLANIR: Open-Meteo tahmin penceresi yalnız birkaç gün ileriyi kapsar ve
    `parse_forecast` zaten pencere dışını `ContractViolation`la reddeder — ama sınırsız
    bir sorgu her turda aylar sonrasına boşuna istek attırırdı.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, commence_time FROM matches
            WHERE home_team = %s AND sealed_at IS NULL
              AND commence_time BETWEEN %s AND %s
            ORDER BY commence_time
            """,
            (home_team, now, now + timedelta(days=horizon_days)),
        )
        return tuple((str(record[0]), record[1]) for record in cur.fetchall())


def collect_venues(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    *,
    sources_path: Path,
    robots_dir: Path,
    now: datetime,
    horizon_days: int = 5,
) -> VenuesResult:
    """Yapılandırılmış stadyumların koordinatını ve yaklaşan ev sahibi maçlarının maç-saati
    havasını toplar — `venues.py`/`weather.py` BİLEŞİMİ, Task 7'nin R1 gereği merge adımına
    ERTELEDİĞİ kablolama.

    **Kickoff UTC'ye BURADA, `parse_forecast` çağrılmadan ÖNCE çevrilir**
    (`commence_time.astimezone(UTC)`): `parse_forecast` naive ya da UTC-farkında OLMAYAN
    bir `kickoff`u REDDEDER (bkz. `weather.parse_forecast` docstring'i) — yanlış etiketli
    bir dilim (ör. TRT/UTC+3) sessizce ama YANLIŞ bir saatlik dilime iner, hata vermeden
    (ölçüldü: task-7-report.md, 19.1°C döner, doğrusu 20.3°C'ydi, İSTİSNA YOK). Bu projede
    `matches.commence_time` HER ZAMAN UTC damgalıdır (`db.connect()` oturumu `-c
    timezone=UTC` ile açar, `ledger.canonical_timestamp` de her yazımda UTC'ye çevirir) —
    ama bu wiring o değişmez kurala GÜVENİP dönüşümü ATLAMAZ: `parse_forecast`in kendi
    sözleşmesi AÇIKÇA yerine getirilir, oturum ayarı sessizce değişse bile doğru kalsın diye.

    Hem stadyum-koordinatı hem maç-saati-havası aynı `now` ile `observed_at` damgalanır —
    `assert_fresh` BURADA ÇAĞRILMAZ (R23): ikisi de toplayıcının KENDİ damgaladığı bir an,
    kırılamayan bir iddia olurdu (bkz. `tff.collect_tff` docstring'i, aynı gerekçe).

    Arıza izolasyonu İKİ KATMANLIDIR (`collect_footystats`teki lig izolasyonuyla aynı
    gerekçe): bir stadyumun koordinatı toplanamazsa o stadyumun maçları hiç denenmez
    (isimle raporlanır, `failed_venues`); koordinat toplandıysa her maçın hava tahmini
    AYRI AYRI izole edilir (`failed_matches`) — bir maçın penceresi dışında kalması
    (ör. çok ileri bir tarih) diğer maçların yazılmasını engellemez.
    """
    sources = load_sources(sources_path)
    wikidata = _require_source(sources, "wikidata")
    openmeteo = _require_source(sources, "openmeteo")
    wikidata_parser = robots_for(wikidata, robots_dir)
    openmeteo_parser = robots_for(openmeteo, robots_dir)

    written = 0
    failed_venues: tuple[str, ...] = ()
    failed_matches: tuple[str, ...] = ()

    for spec in VENUES:
        try:
            body = fetch_text(
                client,
                wikidata,
                ENTITY_PATH.format(qid=spec.qid),
                wikidata_parser,
                expect="application/json",
            )
            latitude, longitude = parse_entity_coordinates(json.loads(body), spec.qid)
            new_rows = write_observations(
                conn, (venue_observation(spec.qid, latitude, longitude, observed_at=now),)
            )
            conn.commit()
            # Minor #4 (review, promoted): `written` yalnız commit BAŞARIYLA dönünce eklenir.
            # commit() kendisi düşerse (G1 — Faz 0'ın dört düzeltme turu harcadığı ders: "not
            # failed" "durably written" demek değildir) satırlar geri alınır ama SAYILMIŞ
            # olurdu; "N yeni gözlem" hiç kalıcı olmamış veri için basılırdı.
            written += new_rows
            # Minor #3 (review, promoted): AYNI try İÇİNDE, KASITLI. Bu sorgu dışarıda
            # kalsaydı bir DB arızası `collect_venues`i, `_fetch_venues_command`ı atlayıp
            # `main()`e ÇIPLAK traceback olarak ulaşırdı — docstring'in vaat ettiği iki
            # katmanlı izolasyonun ihlali: adsız stdout satırı yok, `EXIT_SOURCE_FAILED` yok,
            # yalnız sıfır olmayan ama TEŞHİSSİZ bir exit kodu.
            due = _due_matches(conn, spec.home_team, now, horizon_days)
        except Exception:
            conn.rollback()
            LOGGER.exception("stadyum=%s koordinat toplanamadı", spec.qid)
            failed_venues = (*failed_venues, spec.qid)
            continue

        for match_id, commence_time in due:
            try:
                if commence_time.tzinfo is None:
                    # Minor #2 (review, promoted): `.astimezone(UTC)` bir NAIVE datetime'da
                    # SİSTEM YEREL saatini varsayıp SESSİZCE çevirir — `_require_utc`i GEÇEN
                    # ama YANLIŞ bir aware değer üretir (`astimezone`'un kendisi hatasız çalışır;
                    # guard'ı atlatan LAUNDERING tam olarak budur). Bugün ERİŞİLEMEZ
                    # (`commence_time` timestamptz, psycopg her zaman aware döner) — ama bu
                    # wiring `_require_utc`in TEK çağıranı, yani naive dal bugün ÖLÜ kod;
                    # sütun ileride `timestamp`e değişirse sessizce RUNNER'IN saat dilimine
                    # KAYARDI, hata vermeden.
                    raise ContractViolation(
                        f"maç={match_id}: commence_time naive (tzinfo yok) — UTC varsayılamaz"
                    )
                kickoff = commence_time.astimezone(UTC)
                forecast_path = _forecast_path(latitude, longitude, forecast_days=horizon_days + 1)
                forecast_body = fetch_text(
                    client, openmeteo, forecast_path, openmeteo_parser, expect="application/json"
                )
                values = parse_forecast(json.loads(forecast_body), kickoff)
                new_weather_rows = write_observations(
                    conn, (weather_observation(match_id, values, observed_at=now),)
                )
                conn.commit()
                written += new_weather_rows  # Minor #4 — bkz. yukarıdaki yorum, aynı gerekçe.
            except Exception:
                conn.rollback()
                LOGGER.exception("maç=%s hava toplanamadı (stadyum=%s)", match_id, spec.qid)
                failed_matches = (*failed_matches, match_id)

    return VenuesResult(written=written, failed_venues=failed_venues, failed_matches=failed_matches)
