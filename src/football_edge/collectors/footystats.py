from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import psycopg
from bs4 import BeautifulSoup, Tag

from football_edge.collector import ContractViolation, Observation, assert_schema, fetch_text
from football_edge.leagues import League
from football_edge.observations import write_observations
from football_edge.sources import Source, enabled_sources, load_sources, robots_for

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

    `xg_per_match`/`xga_per_match`: FootyStats bu tabloda MAÇ BAŞINA ortalama veriyor,
    SEZON TOPLAMI değil (review #1, task-5-report.md) — ölçüldü: Galatasaray MP=5, GF=2.60;
    5 maçta 2.6 gol OLAMAZ, bu maç başına ortalamadır, ve `xG vs Actual` sütunu tam olarak
    `GF - xG` formülünü doğruluyor (2.60 - 2.50 = +0.10). Alan adı birimi TAŞIR: yalnız
    "xg" deseydi, FootyStats sezon toplamına geçtiğinde (her değer MP katına sıçrar) alan
    adı DEĞİŞMEDEN geçerdi ve bir birim sıçraması model tarafından sinyal sanılırdı.

    Satır sayısı ile ayrıştırılan takım sayısı AYNI OLMALI: aksi hâlde bir satır (kısa
    satır, eşleşmeyen href, vb.) SESSİZCE atlanmış demektir. `assert_schema(minimum_rows=
    10)` bunu YAKALAMAZ — 20 takımlık bir ligin yarısı sessizce kaybolup yine de eşiği
    geçebilir (review #5). Bu yüzden eksik kalan her durum burada RAISE eder, yalnız
    loglamaz: sessiz eksiklik, hiç veri olmamasından kötüdür.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.find("table", class_="xg-all")
    if not isinstance(table, Tag):
        raise ContractViolation(f"{SOURCE_ID}: 'xg-all' tablosu bulunamadı — sayfa şekli değişti")
    index = _columns(table)
    rows = _data_rows(table)
    parsed: tuple[Observation, ...] = ()
    for row in rows:
        cells = row.find_all("td", recursive=False)
        if len(cells) <= max(index.values()):
            continue  # şekli uymuyor — aşağıdaki sayım eksikliği yakalar, sessiz geçmez
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
                    "xg_per_match": _number(cells[index["xG"]], "xG", name),
                    "xga_per_match": _number(cells[index["xGA"]], "xGA", name),
                },
            ),
        )
    if len(parsed) < len(rows):
        raise ContractViolation(
            f"{SOURCE_ID}: {league_id} — {len(rows)} satır bulundu, yalnız {len(parsed)} takım "
            "ayrıştırıldı; en az bir satır sessizce atlandı"
        )
    return parsed


def _enabled_source(sources_path: Path) -> Source:
    """`enabled: false` kapatma anahtarıdır — sessizce yok sayılmamalı (review #2).

    Eskiden `load_sources(...)` TÜM kayıtları (kapalılar dâhil) tarıyordu:
    `sources-audit`in kullandığı `enabled_sources()` footystats'ı doğru biçimde dışlarken,
    toplayıcı aynı yolu göz ardı edip fetch etmeye DEVAM ediyordu — operatörün kapatma
    anahtarı yalnız DENETİMİ kapatıyordu, TOPLAMAYI değil. Robots koruması yine de her
    yolu ayrı ayrı sınadığı için bu bir izinsiz-erişim açığı DEĞİLDİ, ama beş paralel
    worktree'nin kopyalayacağı satırdı.

    Kayıt yoksa/kapalıysa çıplak `next()`in adsız `StopIteration`i yerine ADLANDIRILMIŞ
    bir `RuntimeError` fırlatılır.
    """
    for entry in enabled_sources(load_sources(sources_path)):
        if entry.id == SOURCE_ID:
            return entry
    raise RuntimeError(
        f"{SOURCE_ID}: kaynak kaydı yok ya da enabled=false ({sources_path}) — toplama durduruldu"
    )


@dataclass(frozen=True)
class FootyStatsResult:
    written: int
    # Başarısız lig id'leri — boş demet "hepsi tamam" demektir. `collect.py`nin çağıranı
    # bunu adıyla raporlayıp `EXIT_LEAGUE_FAILED` ile çıkmalı (review #3): eskiden bu bilgi
    # atılıyordu ve ALTI LİGİN HEPSİ kırılsa bile "footystats: 0 yeni gözlem" ikinci turun
    # idempotent 0'ıyla AYIRT EDİLEMEZ biçimde exit 0 veriyordu.
    failed_leagues: tuple[str, ...] = ()


def collect_footystats(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    leagues: tuple[League, ...],
    *,
    sources_path: Path,
    robots_dir: Path,
    now: datetime,
) -> FootyStatsResult:
    """Etkin liglerin xG tablolarını toplar.

    Lig başına arıza izolasyonu Faz 0'daki `rounds._collect` ile aynı gerekçeyle (R53'e
    kadar `collect.py`'deydi): tek ligin kırılması diğerlerini düşürmemeli. Ama izolasyon
    SESSİZ olamaz (review #3) — bkz. `FootyStatsResult.failed_leagues` docstring'i.
    """
    source = _enabled_source(sources_path)
    parser = robots_for(source, robots_dir)
    written = 0
    failed: tuple[str, ...] = ()
    for league in leagues:
        try:
            body = fetch_text(client, source, league.footystats_path, parser, expect="text/html")
            parsed = parse_xg_table(body, league_id=league.id, observed_at=now)
            assert_schema(
                parsed,
                source_id=SOURCE_ID,
                required=frozenset({"team_name", "footystats_id", "xg_per_match", "xga_per_match"}),
                minimum_rows=10,
            )
            new_rows = write_observations(conn, parsed)
            conn.commit()
            # Minor #4 (review, promoted) — G1 ile aynı gerekçe: commit() kendisi düşerse
            # satırlar geri alınır ama sayaç ÖNCEDEN artmış olurdu, "N yeni gözlem" hiç
            # kalıcı olmamış veri için basılırdı. I-1 (Faz 1 SON inceleme, 2026-09-19):
            # R48 bu düzeltmeyi venues.py/news.py/results.py'a taşıdı ama bu REFERANS
            # toplayıcıya (Task 5, R48'den ÖNCEYDİ) geri süpürülmedi — üç kardeşi
            # kopyalandığı orijinal hâlâ yanlıştı. Sondalandı: commit düşünce
            # `FootyStatsResult(written=18, ...)`, `commits=0` — 18 satır hiç kalıcı
            # olmadan "yazıldı" diye raporlanıyordu.
            written += new_rows
        except Exception:
            conn.rollback()
            LOGGER.exception("lig=%s footystats toplanamadı, diğerlerine devam", league.id)
            failed = (*failed, league.id)
    return FootyStatsResult(written=written, failed_leagues=failed)
