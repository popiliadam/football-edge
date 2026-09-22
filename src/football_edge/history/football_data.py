"""football-data.co.uk CSV baytı → `HistMatch`; saf, ağsız, veritabanısız (tasarım §4.4).

Kısmî kayıp sessiz geçemez (Ruling 6): düşürülen her satır nedeniyle `rejected`e, yok sayılan her
fiyat hücresi `dropped_prices`e sayılır; `check_quality` payları `REJECT_LIMIT`e karşı sorar.
Oransız satır reddedilmez (T1 2022/23'te %8) — oransız kayıt olarak geçer. Genişliği başlıktan
farklı kayıt (tırnaksız virgül, "2,5" fiyatı, eksik hücre) fiyatları yanlış sütuna taşırdı: satır
olarak reddedilir. CSV'nin kendisi bozuksa (dengesiz tırnak) kısmî ayrıştırma yoktur — `parse_file`
dosyayı adlandıran bir `ContractViolation` fırlatır.

Sütun adları football-data'nın başlıklarıdır; ana (`/mmz4281/`) ve ek (`/new/`) dosyalar farklı
adlar taşır, `_LAYOUTS` ikisini aynı kayda indirir. Oran sütunu adları (kitap, market, sonuç,
evre) dörtlüsünden ÜRETİLİR; başlıkta olmayan ad yok sayılır, başlıkta olup sözlükte olmayan
sütun (Asya handikabı, diğer bahisçiler, `HxG`) okunmaz.
"""

from __future__ import annotations

import csv
import io
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from types import MappingProxyType
from zoneinfo import ZoneInfo

from football_edge.collector import ContractViolation
from football_edge.history.catalog import EXTRA, MAIN, HistoryLeague, season_codes
from football_edge.history.types import (
    CLOSING,
    H2H,
    MARKET_OUTCOMES,
    PRE_CLOSING,
    RESULTS,
    TOTALS_25,
    HistMatch,
    OddsKey,
)

REJECT_LIMIT: float = 0.01
BOOKS: tuple[str, ...] = ("Avg", "Max", "B365", "PS", "BFE", "BbAv", "BbMx")
# Şut, isabetli şut, faul, korner, sarı, kırmızı — ev ve deplasman.
STAT_COLUMNS: tuple[str, ...] = (
    "HS",
    "AS",
    "HST",
    "AST",
    "HF",
    "AF",
    "HC",
    "AC",
    "HY",
    "AY",
    "HR",
    "AR",
)
# `AvgC*` 2019/20'den beri her ana lig dosyasında var (ölçüm belgesi §2.4); yoksa sütun kaymıştır.
CLOSING_ERA: str = "1920"
CLOSING_REFERENCE: tuple[str, ...] = ("AvgCH", "AvgCD", "AvgCA")
# Ölçülen doluluk 2019/20'den %100 (T1 2022/23 %92): sütun var ama fiyatların çoğu boşsa kapanış
# referansı (D3) yoktur.
CLOSING_COVERAGE: float = 0.5

REASON_DATE = "tarih çözülemedi"
REASON_TIME = "saat çözülemedi"
REASON_TEAM = "takım adı boş"
REASON_GOALS = "gol çözülemedi"
REASON_RESULT = "sonuç gollerle tutarsız"
REASON_SEASON = "sezon boş"
REASON_DUPLICATE = "yinelenen maç (tarih, ev, deplasman)"
REASON_WIDTH = "sütun sayısı başlıkla uyuşmuyor"
REASON_DIVISION = "Div lig koduyla uyuşmuyor"
REASON_WINDOW = "tarih sezon penceresinin dışında"
REASON_SEASON_FORMAT = "sezon biçimi tanınmıyor"

_LONDON = ZoneInfo("Europe/London")
_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{2}|\d{4})")
# İki haneli yıl POSIX `%y` kuralıyla (`datetime.strptime` ile aynı): 69–99 → 19xx, 00–68 → 20xx.
# football-data'da iki haneli yıl 2005/06–2016/17 dosyalarındadır (ölçüm belgesi §2.4).
_CENTURY_PIVOT = 69
_TIME = re.compile(r"(\d{2}):(\d{2})")
_COUNT = re.compile(r"\d+")
# Ana lig sezonu "YYyy" → [YYYY-06-01, YYYY+1-07-31]. Pencere dönem sınırını korur (holdout kaynağın
# Date'iyle 2026-07-01'de biter), bu yüzden bütün sezonlar için genişletilmez.
_WINDOW_OPENS = (6, 1)
_WINDOW_CLOSES = (7, 31)
# Tek istisna COVID ile uzayan 2019/20: Serie A son haftası 02/08/2020'de oynandı (R105).
_EXTENDED_SEASON = "1920"
_EXTENDED_CLOSES = (8, 31)
_EXTRA_SEASON = re.compile(r"(\d{4})(?:/(\d{4}))?")
_SEASON_YEARS = range(2000, 2101)  # ek lig Season yılları [2000, 2100]
# Pinnacle'ın 1X2 sütunları `PS…`, Ü/A sütunları `P…` önekini taşır.
_TOTALS_PREFIX: Mapping[str, str] = MappingProxyType({"PS": "P"})
_TOTALS_SUFFIX: Mapping[str, str] = MappingProxyType({"over": ">2.5", "under": "<2.5"})


@dataclass(frozen=True)
class _Layout:
    home: str
    away: str
    home_goals: str
    away_goals: str
    result: str
    season: str | None  # ek dosyada sezon satırdadır
    division: str | None  # ana lig dosyasında satırın lig kodu (dosya koduyla aynı olmalı)


_LAYOUTS: Mapping[str, _Layout] = MappingProxyType(
    {
        MAIN: _Layout("HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", None, division="Div"),
        EXTRA: _Layout("Home", "Away", "HG", "AG", "Res", "Season", division=None),
    }
)


def _column(book: str, market: str, outcome: str, phase: str) -> str:
    closing = "C" if phase == CLOSING else ""
    if market == H2H:
        return f"{book}{closing}{outcome}"
    return f"{_TOTALS_PREFIX.get(book, book)}{closing}{_TOTALS_SUFFIX[outcome]}"


ODDS_COLUMNS: Mapping[str, OddsKey] = MappingProxyType(
    {
        _column(book, market, outcome, phase): OddsKey(book, market, outcome, phase)
        for book in BOOKS
        for market in (H2H, TOTALS_25)
        for outcome in MARKET_OUTCOMES[market]
        for phase in (PRE_CLOSING, CLOSING)
    }
)
_REFERENCE_KEYS: tuple[OddsKey, ...] = tuple(ODDS_COLUMNS[name] for name in CLOSING_REFERENCE)


@dataclass(frozen=True)
class Rejected:
    line: int
    reason: str


@dataclass(frozen=True)
class ParseResult:
    matches: tuple[HistMatch, ...]
    rejected: tuple[Rejected, ...]
    dropped_prices: int
    price_cells: int
    encoding: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class _Context:
    league: HistoryLeague
    season: str | None
    layout: _Layout
    width: int  # başlığın alan sayısı; her kayıt tam bu genişlikte olmalı
    window: tuple[date, date] | None  # ana lig sezonunun tarih penceresi; ek ligde None
    index: Mapping[str, int]
    odds: tuple[tuple[int, OddsKey], ...]
    stats: tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class _Fields:
    season: str
    date: date
    kickoff: datetime | None
    home: str
    away: str
    home_goals: int
    away_goals: int
    result: str


@dataclass(frozen=True)
class _Row:
    outcome: HistMatch | Rejected
    price_cells: int
    dropped: int


def _decode(content: bytes) -> tuple[str, str]:
    try:
        return content.decode("utf-8-sig"), "utf-8-sig"
    except UnicodeDecodeError:
        return content.decode("latin-1"), "latin-1"


def _source_path(league: HistoryLeague, season: str | None) -> str:
    """İhlal mesajının adlandırdığı dosya (`catalog.file_paths`in yol şablonu): `parse_file`
    sözleşmesi yol almaz, yol lig ve sezondan bellidir."""
    if league.kind == EXTRA:
        return f"/new/{league.code}.csv"
    return f"/mmz4281/{season}/{league.code}.csv"


def _records(text: str, path: str) -> list[list[str]]:
    """Katı CSV: dengesiz tırnak kısmî ayrıştırma değil, dosyayı adlandıran bir ihlaldir."""
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        records = list(reader)
    except csv.Error as error:
        raise ContractViolation(
            f"{path}: CSV çözülemedi (fiziksel satır {reader.line_num}): {error}"
        ) from error
    # Kayıtlar arasında kapanan bir tırnak çifti aradaki satırları tek hücreye yutar ve katı okuyucu
    # bunu hata saymaz; football-data'da çok satırlı hücre yoktur.
    spanning = [
        number
        for number, record in enumerate(records)
        if any("\n" in cell or "\r" in cell for cell in record)
    ]
    if spanning:
        raise ContractViolation(
            f"{path}: CSV kaydı {spanning[0]} birden çok satıra yayılıyor — dengesiz tırnak"
        )
    return records


def _season_window(season: str) -> tuple[date, date]:
    """Ana lig sezonunun tarih penceresi, iki uç dahil; bozuk sezon kodu `ValueError`."""
    (code,) = season_codes(season, season)
    start = 2000 + int(code[:2])  # sezon kodları yalnız 2000–2099 (catalog)
    closes = _EXTENDED_CLOSES if code == _EXTENDED_SEASON else _WINDOW_CLOSES
    return date(start, *_WINDOW_OPENS), date(start + 1, *closes)


def _is_extra_season(text: str) -> bool:
    """Ek lig `Season`ı "YYYY" ya da "YYYY/YYYY"; yıllar [2000, 2100]."""
    found = _EXTRA_SEASON.fullmatch(text)
    return found is not None and all(int(year) in _SEASON_YEARS for year in found.groups() if year)


def _cell(row: Sequence[str], position: int | None) -> str:
    if position is None or position >= len(row):
        return ""
    return row[position].strip()


def _kickoff_utc(match_date: date, clock: time) -> datetime:
    """Europe/London yerel saati → UTC (tasarım D5).

    Yaz saati geçişinde iki yorumdan GEÇ olan an seçilir: ilkbahar boşluğunda (29/03/2026 01:30
    yok) geçiş öncesi ofset, sonbahar tekrarında (25/10/2026 01:30 iki kez) ikinci geçiş. Sonuç
    bilinme anı (başlama + 3 sa) böylece olası gerçek andan hiçbir zaman önceye düşmez.
    """
    local = datetime.combine(match_date, clock, tzinfo=_LONDON)
    return max(local.replace(fold=0).astimezone(UTC), local.replace(fold=1).astimezone(UTC))


def _date(text: str) -> date | None:
    found = _DATE.fullmatch(text)
    if found is None:
        return None
    day, month, year = found.groups()
    try:
        return date(_full_year(year), int(month), int(day))
    except ValueError:
        return None


def _full_year(year: str) -> int:
    if len(year) == 4:
        return int(year)
    return int(year) + (1900 if int(year) >= _CENTURY_PIVOT else 2000)


def _clock(text: str) -> time | None:
    found = _TIME.fullmatch(text)
    if found is None:
        return None
    try:
        return time(int(found.group(1)), int(found.group(2)))
    except ValueError:
        return None


def _price(text: str) -> float | None:
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) and value > 1.0 else None


def _prices(row: Sequence[str], ctx: _Context) -> tuple[Mapping[OddsKey, float], int, int]:
    """(geçerli fiyatlar, dolu fiyat hücresi, yok sayılan hücre)."""
    read = ((key, _cell(row, position)) for position, key in ctx.odds)
    filled = tuple((key, text) for key, text in read if text)
    parsed = tuple((key, _price(text)) for key, text in filled)
    kept = {key: value for key, value in parsed if value is not None}
    return MappingProxyType(kept), len(filled), len(filled) - len(kept)


def _stats(row: Sequence[str], ctx: _Context) -> Mapping[str, int]:
    """Faz 2'de kullanılmaz (sonuçla aynı anda bilinir); sayı olmayan hücre atlanır."""
    cells = ((name, _cell(row, position)) for position, name in ctx.stats)
    return MappingProxyType({name: int(text) for name, text in cells if _COUNT.fullmatch(text)})


def _winner(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "H"
    return "A" if home_goals < away_goals else "D"


def _fields(line: int, row: Sequence[str], ctx: _Context) -> _Fields | Rejected:
    """Satırın maç alanları; ilk bozuk alanın nedeniyle `Rejected`."""
    get = ctx.index.get
    if ctx.layout.division and _cell(row, get(ctx.layout.division)) != ctx.league.code:
        return Rejected(line, REASON_DIVISION)
    match_date = _date(_cell(row, get("Date")))
    if match_date is None:
        return Rejected(line, REASON_DATE)
    if ctx.window is not None and not ctx.window[0] <= match_date <= ctx.window[1]:
        return Rejected(line, REASON_WINDOW)
    clock_text = _cell(row, get("Time"))
    clock = _clock(clock_text) if clock_text else None
    if clock_text and clock is None:
        return Rejected(line, REASON_TIME)
    home, away = _cell(row, get(ctx.layout.home)), _cell(row, get(ctx.layout.away))
    if not home or not away:
        return Rejected(line, REASON_TEAM)
    goals = (_cell(row, get(ctx.layout.home_goals)), _cell(row, get(ctx.layout.away_goals)))
    if not all(_COUNT.fullmatch(text) for text in goals):
        return Rejected(line, REASON_GOALS)
    home_goals, away_goals = int(goals[0]), int(goals[1])
    result = _cell(row, get(ctx.layout.result))
    if result not in RESULTS or result != _winner(home_goals, away_goals):
        return Rejected(line, REASON_RESULT)
    season = ctx.season if ctx.layout.season is None else _cell(row, get(ctx.layout.season))
    if not season:
        return Rejected(line, REASON_SEASON)
    if ctx.layout.season is not None and not _is_extra_season(season):
        return Rejected(line, REASON_SEASON_FORMAT)
    kickoff = None if clock is None else _kickoff_utc(match_date, clock)
    return _Fields(season, match_date, kickoff, home, away, home_goals, away_goals, result)


def _row(line: int, row: Sequence[str], ctx: _Context) -> _Row:
    if len(row) != ctx.width:
        # Kaymış kaydın hücresi hangi sütuna ait bilinmez: satır düşer, hücresi fiyat sayılmaz.
        return _Row(Rejected(line, REASON_WIDTH), 0, 0)
    odds, cells, dropped = _prices(row, ctx)
    fields = _fields(line, row, ctx)
    if isinstance(fields, Rejected):
        return _Row(fields, cells, dropped)
    match = HistMatch(
        league=ctx.league.code,
        season=fields.season,
        date=fields.date,
        kickoff=fields.kickoff,
        home=fields.home,
        away=fields.away,
        home_goals=fields.home_goals,
        away_goals=fields.away_goals,
        result=fields.result,
        odds=odds,
        stats=_stats(row, ctx),
        source_line=line,
    )
    return _Row(match, cells, dropped)


def _context(
    header: Sequence[str],
    league: HistoryLeague,
    season: str | None,
    window: tuple[date, date] | None,
) -> _Context:
    names = [name.strip() for name in header]
    # Yinelenen başlıkta İLK sütun geçerli: ters sırada kurulan sözlükte öndeki konum kazanır.
    index = {name: position for position, name in reversed(list(enumerate(names))) if name}
    return _Context(
        league=league,
        season=season,
        layout=_LAYOUTS[league.kind],
        width=len(header),
        window=window,
        index=MappingProxyType(index),
        odds=tuple((index[name], key) for name, key in ODDS_COLUMNS.items() if name in index),
        stats=tuple((index[name], name) for name in STAT_COLUMNS if name in index),
    )


def _without_duplicates(rows: Sequence[_Row]) -> tuple[_Row, ...]:
    """Aynı (tarih, ev, deplasman) ikinci kez geçerse sonraki satır reddedilir, ilki kalır."""
    found = [
        (position, row.outcome)
        for position, row in enumerate(rows)
        if isinstance(row.outcome, HistMatch)
    ]
    first = {(match.date, match.home, match.away): position for position, match in reversed(found)}
    repeated = {
        position: match.source_line
        for position, match in found
        if first[(match.date, match.home, match.away)] != position
    }
    return tuple(
        _Row(Rejected(repeated[position], REASON_DUPLICATE), row.price_cells, row.dropped)
        if position in repeated
        else row
        for position, row in enumerate(rows)
    )


def _check_season_argument(league: HistoryLeague, season: str | None) -> None:
    if league.kind == MAIN and season is None:
        raise ValueError(f"{league.code}: ana lig dosyası için season zorunlu")
    if league.kind == EXTRA and season is not None:
        raise ValueError(f"{league.code}: ek lig dosyasında sezon satırdan okunur, season verilmez")


def parse_file(content: bytes, *, league: HistoryLeague, season: str | None) -> ParseResult:
    _check_season_argument(league, season)
    window = None if season is None else _season_window(season)
    text, encoding = _decode(content)
    records = _records(text, _source_path(league, season))
    if not records:
        return ParseResult((), (), 0, 0, encoding, ())
    ctx = _context(records[0], league, season, window)
    rows = _without_duplicates(
        tuple(
            _row(line, record, ctx)
            for line, record in enumerate(records[1:], start=1)
            if any(cell.strip() for cell in record)
        )
    )
    return ParseResult(
        matches=tuple(row.outcome for row in rows if isinstance(row.outcome, HistMatch)),
        rejected=tuple(row.outcome for row in rows if isinstance(row.outcome, Rejected)),
        dropped_prices=sum(row.dropped for row in rows),
        price_cells=sum(row.price_cells for row in rows),
        encoding=encoding,
        columns=tuple(name.strip() for name in records[0] if name.strip()),
    )


def _required(league: HistoryLeague) -> tuple[str, ...]:
    layout = _LAYOUTS[league.kind]
    names = (layout.season, "Date", layout.home, layout.away)
    return (*(name for name in names if name), layout.home_goals, layout.away_goals, layout.result)


def _check_closing_coverage(result: ParseResult, *, path: str, season: str) -> None:
    """Sütunlar var ama maçların çoğunda AvgC 1X2 boşsa dosya kapanış referansı taşımıyor."""
    if not result.matches:
        return  # payda yok: reddedilen satır payı ya da "hiç maç yok" konuşur
    complete = sum(all(key in match.odds for key in _REFERENCE_KEYS) for match in result.matches)
    if complete / len(result.matches) < CLOSING_COVERAGE:
        raise ContractViolation(
            f"{path}: {season} dönem beklentisi — AvgC 1X2 {complete}/{len(result.matches)} maçta "
            f"tam (< {CLOSING_COVERAGE:.0%})"
        )


def check_quality(
    result: ParseResult, *, path: str, league: HistoryLeague, season: str | None
) -> None:
    """Dosya düzeyinde veri sözleşmesi; ihlal `ContractViolation` — mesaj yalnız sayı taşır."""
    missing = [name for name in _required(league) if name not in result.columns]
    if missing:
        raise ContractViolation(f"{path}: zorunlu sütun yok {missing}")
    if league.kind == MAIN and season is not None and season >= CLOSING_ERA:
        absent = [name for name in CLOSING_REFERENCE if name not in result.columns]
        if absent:
            raise ContractViolation(f"{path}: {season} dönem beklentisi — {absent} sütunu yok")
        _check_closing_coverage(result, path=path, season=season)
    rows = len(result.matches) + len(result.rejected)
    if rows and len(result.rejected) / rows > REJECT_LIMIT:
        reasons = Counter(entry.reason for entry in result.rejected).most_common()
        raise ContractViolation(
            f"{path}: reddedilen satır {len(result.rejected)}/{rows} > {REJECT_LIMIT:.0%} "
            f"— nedenler {reasons}"
        )
    if result.price_cells and result.dropped_prices / result.price_cells > REJECT_LIMIT:
        raise ContractViolation(
            f"{path}: yok sayılan fiyat hücresi {result.dropped_prices}/{result.price_cells} "
            f"> {REJECT_LIMIT:.0%}"
        )
    if not result.matches:
        # Kırılan kaynak boş liste üretir; boş liste başarıdan ayırt edilemez (R88, Ruling 6).
        raise ContractViolation(f"{path}: hiç maç yok — yalnız başlık satırı, tam kayıp")
