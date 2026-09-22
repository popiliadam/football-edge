"""football-data.co.uk CSV baytı → `HistMatch`; saf, ağsız, veritabanısız (tasarım §4.4).

Kısmî kayıp sessiz geçemez (Ruling 6): düşürülen her satır nedeniyle `rejected`e, yok sayılan her
fiyat hücresi `dropped_prices`e sayılır; `check_quality` payları `REJECT_LIMIT`e karşı sorar.
Oransız satır reddedilmez (T1 2022/23'te %8) — oransız kayıt olarak geçer.

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
from football_edge.history.catalog import EXTRA, MAIN, HistoryLeague
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

REASON_DATE = "tarih çözülemedi"
REASON_TIME = "saat çözülemedi"
REASON_TEAM = "takım adı boş"
REASON_GOALS = "gol çözülemedi"
REASON_RESULT = "sonuç gollerle tutarsız"
REASON_SEASON = "sezon boş"
REASON_DUPLICATE = "yinelenen maç (tarih, ev, deplasman)"

_LONDON = ZoneInfo("Europe/London")
_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{2}|\d{4})")
_TIME = re.compile(r"(\d{2}):(\d{2})")
_COUNT = re.compile(r"\d+")
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


_LAYOUTS: Mapping[str, _Layout] = MappingProxyType(
    {
        MAIN: _Layout("HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", None),
        EXTRA: _Layout("Home", "Away", "HG", "AG", "Res", "Season"),
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
        return date(int(year) + (2000 if len(year) == 2 else 0), int(month), int(day))
    except ValueError:
        return None


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
    match_date = _date(_cell(row, get("Date")))
    if match_date is None:
        return Rejected(line, REASON_DATE)
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
    kickoff = None if clock is None else _kickoff_utc(match_date, clock)
    return _Fields(season, match_date, kickoff, home, away, home_goals, away_goals, result)


def _row(line: int, row: Sequence[str], ctx: _Context) -> _Row:
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


def _context(header: Sequence[str], league: HistoryLeague, season: str | None) -> _Context:
    names = [name.strip() for name in header]
    # Yinelenen başlıkta İLK sütun geçerli: ters sırada kurulan sözlükte öndeki konum kazanır.
    index = {name: position for position, name in reversed(list(enumerate(names))) if name}
    return _Context(
        league=league,
        season=season,
        layout=_LAYOUTS[league.kind],
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
    text, encoding = _decode(content)
    records = list(csv.reader(io.StringIO(text, newline="")))
    if not records:
        return ParseResult((), (), 0, 0, encoding, ())
    ctx = _context(records[0], league, season)
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
