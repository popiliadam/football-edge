from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import psycopg
from bs4 import BeautifulSoup, Tag

from football_edge.collector import ContractViolation, Observation, assert_schema, fetch_text
from football_edge.leagues import League
from football_edge.observations import write_observations
from football_edge.sources import load_sources, robots_for

LOGGER = logging.getLogger("football_edge.collectors.footystats")

SOURCE_ID = "footystats"

# `<a href='/clubs/galatasaray-187'>` — sondaki sayı kararlı FootyStats takım kimliğidir.
# Ada göre eşleşmeye göre çok daha sağlam: ad değişir, kimlik değişmez.
_CLUB_HREF = re.compile(r"/clubs/[a-z0-9-]+-(?P<club_id>\d+)/?$")

_REQUIRED_COLUMNS = ("Team", "MP", "xG", "xGA")


def _text(node: Any) -> str:
    """Bir düğümün görünür metnini tek yoldan alır (bs4 tipleri tek yerde daraltılır)."""
    return "" if node is None else str(node.get_text(" ", strip=True))


def _first_string(node: Tag) -> str:
    """`<a>Galatasaray<div class='hover-modal'>…</div></a>` — yalnız İLK metin düğümü.

    `get_text()` gömülü hover-modal'ın tamamını da getirir. Bu YALNIZ takım adının
    derdi değil: canlı fixture'a bakınca (`tests/fixtures/footystats/
    turkey-super-lig-xg.html`) `MP` BAŞLIK hücresi de AYNI deseni taşıyor —
    `<th>MP<div class="hover-modal-content">…Matches Played…</div></th>` (ölçüldü).
    `_columns()` bunu düzeltmezse sütun adı "MP" değil "MP Matches Played" okunur ve
    `_REQUIRED_COLUMNS`deki "MP" hiç eşleşmez: GERÇEK veriye karşı yanlış pozitif bir
    ContractViolation — sayfa kırılmadığı hâlde toplayıcı hiçbir satır yazamaz. Aynı
    fonksiyon bu yüzden hem takım adında hem başlık adında kullanılıyor.
    """
    for child in node.children:
        if isinstance(child, str) and child.strip():
            return child.strip()
    return _text(node)


def _number(cell: Tag, column: str, team: str) -> float:
    raw = _text(cell).replace(",", "")
    try:
        return float(raw)
    except ValueError as error:
        raise ContractViolation(f"{SOURCE_ID}: '{column}' sayı değil ({team}): {raw!r}") from error


def _columns(table: Tag) -> dict[str, int]:
    headers = tuple(_first_string(cell) for cell in table.select("thead th"))
    index = {name: position for position, name in enumerate(headers) if name}
    missing = tuple(name for name in _REQUIRED_COLUMNS if name not in index)
    if missing:
        raise ContractViolation(
            f"{SOURCE_ID}: beklenen sütun(lar) yok {missing} — bulunanlar: {headers}"
        )
    return index


def _data_rows(table: Tag) -> tuple[Tag, ...]:
    """`tbody`nin DOĞRUDAN `<tr>` çocukları — iç içe geçenleri değil.

    Takım hücresinin hover-modal'ı kendi mobil düzeni için AYRICA `<tr>`/`<td>` kullanıyor
    (Form/PPG/Ev-Deplasman istatistik alt tablosu, aynı hover-modal-content bloğunun
    içinde). `table.select("tbody tr")` ÖZYİNELİ olduğundan bunları da toplar: ölçüldü,
    canlı fixture'da 18 gerçek satır yerine 216 `<tr>` döner. `row.find_all("td")` da aynı
    şekilde özyineli olduğu için gerçek bir satırda 10 yerine 50 `<td>` toplar — ve konum
    tabanlı `cells[index["MP"]]` artık MP değil, hover-kartındaki "Form" etiketini okur:
    HATA VERMEZ, sessizce yanlış sayı üretir (ölçüldü — bkz. task-5-report.md).

    Yalnız DOĞRUDAN çocuklar tabloların gerçek sütun sayısıyla birebir eşleşir: ölçüldü,
    18/18 satır tam 10 doğrudan `<td>` taşıyor — `thead`deki 10 başlıkla aynı sayı, aynı
    sıra.
    """
    body = table.find("tbody")
    return () if not isinstance(body, Tag) else tuple(body.find_all("tr", recursive=False))


def parse_xg_table(
    html_text: str, *, league_id: str, observed_at: datetime
) -> tuple[Observation, ...]:
    """FootyStats lig xG tablosunu gözlemlere çevirir.

    Sütunlar İSİMLE bulunur, konumla değil: FootyStats sütun ekleyince konumla okuyan bir
    ayrıştırıcı komşu sütunu okur ve HATA VERMEZ — xG yerine xGD yazar. Sessiz yanlış veri,
    eksik veriden kötüdür; model onu doğru sanıp fit eder.

    Satırlar ve hücreler de DOĞRUDAN çocuklardan okunur, özyineli `select`/`find_all`
    değil — bkz. `_data_rows` docstring'i: aksi hâlde takım hücresinin gömülü mobil
    düzeni sahte satır/hücre ekler ve konum tabanlı okuma komşu (hatta rastgele iç içe)
    bir hücreyi okur.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.find("table", class_="xg-all")
    if not isinstance(table, Tag):
        raise ContractViolation(f"{SOURCE_ID}: 'xg-all' tablosu bulunamadı — sayfa şekli değişti")
    index = _columns(table)
    parsed: tuple[Observation, ...] = ()
    for row in _data_rows(table):
        cells = row.find_all("td", recursive=False)
        if len(cells) <= max(index.values()):
            continue  # ara başlık / reklam satırı
        team_cell = cells[index["Team"]]
        link = team_cell.find("a", href=_CLUB_HREF)
        if not isinstance(link, Tag):
            continue
        found = _CLUB_HREF.search(str(link.get("href", "")))
        if found is None:
            continue
        name = _first_string(link)
        club_id = int(found.group("club_id"))
        parsed = (
            *parsed,
            Observation(
                source_id=SOURCE_ID,
                entity_kind="team",
                entity_key=f"{league_id}:{club_id}",
                observed_at=observed_at,
                payload={
                    "team_name": name,
                    "footystats_id": club_id,
                    "matches_played": int(_number(cells[index["MP"]], "MP", name)),
                    "xg": _number(cells[index["xG"]], "xG", name),
                    "xga": _number(cells[index["xGA"]], "xGA", name),
                },
            ),
        )
    return parsed


def collect_footystats(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    leagues: tuple[League, ...],
    *,
    sources_path: Path,
    robots_dir: Path,
    now: datetime,
) -> int:
    """Etkin liglerin xG tablolarını toplar; YAZILAN yeni gözlem sayısını döner.

    Lig başına arıza izolasyonu Faz 0'daki `_collect` ile aynı gerekçeyle: tek ligin
    kırılması diğerlerini düşürmemeli.
    """
    source = next(entry for entry in load_sources(sources_path) if entry.id == SOURCE_ID)
    parser = robots_for(source, robots_dir)
    written = 0
    for league in leagues:
        try:
            body = fetch_text(client, source, league.footystats_path, parser, expect="text/html")
            parsed = parse_xg_table(body, league_id=league.id, observed_at=now)
            assert_schema(
                parsed,
                source_id=SOURCE_ID,
                required=frozenset({"team_name", "footystats_id", "xg", "xga"}),
                minimum_rows=10,
            )
            written += write_observations(conn, parsed)
            conn.commit()
        except Exception:
            conn.rollback()
            LOGGER.exception("lig=%s footystats toplanamadı, diğerlerine devam", league.id)
    return written
