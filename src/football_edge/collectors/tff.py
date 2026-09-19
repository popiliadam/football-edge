"""TFF (Türkiye Futbol Federasyonu) haftalık hakem ataması toplayıcısı.

**Ölçülen ve brief'i düzelten (2026-09-19):** brief `pageID=433`i ("Haftanın Hakem,
Gözlemci ve Temsilcileri") doğru sayfa olarak veriyordu. ÖLÇÜLDÜ ki bu YANLIŞ: 433
varsayılan GET'te BOŞ bir arama formu döner — üç kademeli RadComboBox (Organizasyon →
Grup → Hafta) + "Ara" düğmesi, hepsi postback/AJAX. Sonuç konteyneri (`DataList1`) tek
bir boş `<span>` taşır, SIFIR satır — iki bağımsız taze fetch'te de aynı (89112 bayt,
aynı boş form). Doldurmak "Ara"ya tıklamayı (bir ASP.NET postback, yani POST) gerektirir;
outward_action_gate POST'u zaten engelliyor.

**Gerçek veri `pageID=600`de** ("Tüm Liglerin Fikstürleri" — spec'in ASIL önerdiği
sayfa). Önceki ölçüm (brief) burada "hakem verisi yok" demişti; bu da YANLIŞTI — 600
düz bir `<table>` taşımıyor (muhtemelen `find_all("table")` ile taranıp boş dönmüştü),
ama `<div class="row haftaninMaclariMaclar">` ile TEKRARLANAN, GET'le DOĞRUDAN erişilebilir
bir blok, TÜM liglerin bu haftaki maçlarını hakem atamalarıyla BİRLİKTE taşıyor —
ölçüldü: 7 lig bloğu, 63 maç (bkz. task-6-report.md).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import psycopg
from bs4 import BeautifulSoup, Tag

from football_edge.collector import ContractViolation, Observation, assert_schema, fetch_text
from football_edge.naming import normalise_team
from football_edge.observations import write_observations
from football_edge.sources import Source, enabled_sources, load_sources, robots_for

LOGGER = logging.getLogger("football_edge.collectors.tff")

SOURCE_ID = "tff"

# pageID=600, pageID=433 DEĞİL — yukarıdaki modül docstring'i ölçümü taşıyor. Bu yol
# ZATEN `config/sources.yaml`nin (salt okunur) `declared_paths` listesinde.
REFEREE_PATH = "/Default.aspx?pageID=600"

# TFF gövdesi windows-1254. charset yalnız HTTP başlığında, gövdede meta yok — kodlama
# httpx'in tahminine bırakılırsa Türkçe adlar sessizce bozulur ve varlık eşleme hiçbir
# şey bulamaz.
ENCODING = "windows-1254"

# Aşağıdaki dört işaret ÖLÇÜLDÜ (2026-09-19, pageID=600, gerçek yanıt — bkz.
# tests/fixtures/tff/haftanin-maclari-600.html): TFF'in ASP.NET DataList/Repeater
# çıktısı sabit CSS sınıfları kullanıyor. `_MATCH_ROW_CLASS` tek başına yeterli çünkü
# bs4 bunu bir <div>'in OLASI BİRDEN ÇOK sınıfından biri olarak eşleştirir (gerçek
# markup `class="row haftaninMaclariMaclar"` — iki token).
_LEAGUE_LABEL_ID_SUFFIX = "_lblMacOrgAdi"
_CONTAINER_ID_SUFFIX = "_ctnr_div"
_MATCH_ROW_CLASS = "haftaninMaclariMaclar"
_HOME_CLASS = "haftaninMaclariMaclarEvSahibi"
_AWAY_CLASS = "haftaninMaclariMaclarMisafir"
_OFFICIALS_CLASS = "haftaninMaclariMaclarHakemler"

# Görevli etiketleri ÖLÇÜLDÜ: (H) baş hakem, (Y) yardımcı hakem ×2, (D) dördüncü hakem,
# yalnız üst ligde ayrıca (V) VAR hakemi, (A) AVAR hakemi — 63 maçtan 11'i (Süper Lig)
# bu ikisini taşıyor, 51'i taşımıyor (alt liglerde VAR yok). Sözleşme (Interfaces,
# task-6-brief.md) TEK bir `referee` alanı istiyor; (H) o alanı doldurur.
#
# Sayfada tam "VAR" DİZESİ hiç geçmiyor (görev tek harfle "(V)" yazılıyor) — bu yüzden
# bir VAR atama sinyali GERÇEKTEN VAR OLDUĞU HÂLDE metin araması onu bulamaz. Bu alan
# şimdilik toplanmıyor (sözleşme kapsamı dışı); Task 13'te DEFERRED'a yazılır.
_HEAD_REFEREE_PREFIX = "(H)"


def _text(node: Any) -> str:
    return "" if node is None else str(node.get_text(" ", strip=True))


def _team_name(row: Tag, class_name: str) -> str:
    cell = row.find("div", class_=class_name)
    if not isinstance(cell, Tag):
        return ""
    link = cell.find("a")
    return _text(link) if link is not None else ""


def _head_referee(row: Tag) -> str:
    """`(H)` önekini taşıyan görevliyi ETİKETLE bulur, KONUMLA değil.

    Ölçüldü: görevli SAYISI satır başına sabit değil (4 ya da 6, VAR atanıp
    atanmamasına göre). Konum 0'ı "baş hakem" saymak bu fixture'da tesadüfen hep doğru
    çıkardı (H gözlenen HER satırda ilk sırada), ama bu garanti değil; TFF sırayı
    değiştirirse konum tabanlı okuma SESSİZCE yanlış kişiyi "hakem" diye yazar —
    footystats'ın "isimle bul, konumla değil" dersiyle aynı sınıf arıza.
    """
    officials_cell = row.find("div", class_=_OFFICIALS_CLASS)
    if not isinstance(officials_cell, Tag):
        return ""
    for link in officials_cell.find_all("a"):
        label = _text(link)
        if label.startswith(_HEAD_REFEREE_PREFIX):
            return label[len(_HEAD_REFEREE_PREFIX) :].strip()
    return ""


def _league_blocks(soup: BeautifulSoup) -> tuple[tuple[str, Tag], ...]:
    """Her lig bloğunu `(lig adı, o lige ait KONTEYNER)` çifti olarak döner.

    Lig adı (`_lblMacOrgAdi` span'i) ve o ligin maç satırları AYNI `..._ctnr_div`
    konteynerinin içinde yaşar (ölçüldü) — eşleme bu yüzden KONTEYNER TARAMALIDIR, tüm
    sayfadaki lig etiketlerini toplayıp satırları GLOBAL taramak DEĞİL. Sayfada 7 lig
    bloğu var ve İKİSİ AYNI ADI taşıyor ("Nesine 2. Lig" iki ayrı grup için iki kez,
    "Nesine 3. Lig" üç kez) — global bir eşleme bu durumda maçları YANLIŞ bloğa
    (genelde sondaki etikete) sessizce karıştırabilirdi.
    """
    blocks: tuple[tuple[str, Tag], ...] = ()
    for container in soup.find_all(
        "div", id=lambda value: bool(value) and value.endswith(_CONTAINER_ID_SUFFIX)
    ):
        label = container.find(
            "span", id=lambda value: bool(value) and value.endswith(_LEAGUE_LABEL_ID_SUFFIX)
        )
        if not isinstance(label, Tag):
            continue
        blocks = (*blocks, (_text(label), container))
    return blocks


def parse_referees(html_text: str, *, observed_at: datetime) -> tuple[Observation, ...]:
    """Haftanın hakem atamalarını gözlemlere çevirir (`pageID=600`, div tabanlı düzen).

    Satır şekli TFF tarafından değiştirilebilir; bu yüzden hem lig eşlemesi hem de
    baş-hakem alanı İSİM/ETİKET ile bulunur, konumla değil (bkz. `_league_blocks`,
    `_head_referee`). Bir maçın görevli listesi TAMAMEN boşsa (ölçüldü: 63 maçtan 1'i,
    TFF henüz atamamış — GERÇEK bir durum, ayrıştırıcı arızası değil) o satır sessizce
    atlanır. Ama HİÇ satır tanınmazsa `ContractViolation` fırlatılır: boş sonuç,
    sayfa şekli değiştiğinde başarıdan ayırt edilemez olurdu.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    parsed: tuple[Observation, ...] = ()
    for league_name, container in _league_blocks(soup):
        for row in container.find_all("div", class_=_MATCH_ROW_CLASS):
            home = _team_name(row, _HOME_CLASS)
            away = _team_name(row, _AWAY_CLASS)
            referee = _head_referee(row)
            if not (home and away and referee):
                continue
            parsed = (
                *parsed,
                Observation(
                    source_id=SOURCE_ID,
                    entity_kind="fixture_official",
                    entity_key=f"{normalise_team(home)}|{normalise_team(away)}",
                    observed_at=observed_at,
                    payload={
                        "home_team": home,
                        "away_team": away,
                        "referee": referee,
                        "league": league_name,
                    },
                ),
            )
    if not parsed:
        raise ContractViolation(f"{SOURCE_ID}: hiç hakem ataması tanınmadı — sayfa şekli değişti")
    return parsed


def _enabled_source(sources_path: Path) -> Source:
    """`enabled: false` sessizce yok sayılmaz (bkz. footystats._enabled_source, R2)."""
    for entry in enabled_sources(load_sources(sources_path)):
        if entry.id == SOURCE_ID:
            return entry
    raise RuntimeError(
        f"{SOURCE_ID}: kaynak kaydı yok ya da enabled=false ({sources_path}) — toplama durduruldu"
    )


def collect_tff(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    *,
    sources_path: Path,
    robots_dir: Path,
    now: datetime,
) -> int:
    """Bu haftanın hakem atamalarını toplar ve yazar; YENİ gözlem sayısını döner.

    CLI dalı bu task'ta YOK (Ruling R1) — `fetch-tff` alt komutu dört toplayıcının
    branch'leri birleştiğinde tek seferde eklenir. `assert_fresh` BURADA ÇAĞRILMAZ
    (R23): `observed_at=now`i toplayıcının kendisi damgalıyor, bu yüzden "en yeni gözlem
    taze mi" iddiası her zaman doğru olurdu — kırılamayan bir kontrol.
    """
    source = _enabled_source(sources_path)
    parser = robots_for(source, robots_dir)
    body = fetch_text(client, source, REFEREE_PATH, parser, expect="text/html", encoding=ENCODING)
    parsed = parse_referees(body, observed_at=now)
    assert_schema(
        parsed,
        source_id=SOURCE_ID,
        required=frozenset({"home_team", "away_team", "referee"}),
        minimum_rows=5,
    )
    written = write_observations(conn, parsed)
    conn.commit()
    return written
