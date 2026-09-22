"""Tarihsel lig kataloğu (`config/history_leagues.yaml`) ve football-data yol üretimi.

Katalog, kaynak kayıt defterindeki `football-data` `declared_paths`inin TEK kaynağıdır: yollar
buradan türetilir ve bir test ikisinin eşit olduğunu zorlar (tasarım D20). Canlı
`config/leagues.yaml` bu dosyadan bağımsızdır (D19).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

MAIN: str = "main"
EXTRA: str = "extra"
KINDS = frozenset({MAIN, EXTRA})

REQUIRED_FIELDS = frozenset(
    {"code", "league_id", "name", "country", "tier", "kind", "first_season", "odds_api_key"}
)
_TEXT_FIELDS = ("code", "league_id", "name", "country", "kind", "first_season", "odds_api_key")
_SEASON = re.compile(r"\d{4}")
_MAIN_PATH = re.compile(r"/mmz4281/(\d{4})/[A-Za-z0-9]+\.csv")


@dataclass(frozen=True)
class HistoryLeague:
    code: str
    league_id: str
    name: str
    country: str
    tier: int
    kind: str
    first_season: str
    odds_api_key: str


@dataclass(frozen=True)
class Catalog:
    current_season: str
    leagues: tuple[HistoryLeague, ...]


def _check_season(code: object) -> str:
    """Sezon kodu `YYyy` (ör. "0506"): dört rakam, ikinci çift birincinin bir fazlası.

    Tırnaksız YAML değeri sayı okunur (`0506` sekizlik 326 olur); dize olmayan her şey reddedilir.
    """
    if not isinstance(code, str) or not _SEASON.fullmatch(code):
        raise ValueError(f"geçersiz sezon kodu: {code!r} (tırnaklı 'YYyy', ör. '0506')")
    if (int(code[:2]) + 1) % 100 != int(code[2:]):
        raise ValueError(f"geçersiz sezon kodu: {code!r} (yıllar ardışık değil)")
    return code


def season_codes(first: str, last: str) -> tuple[str, ...]:
    """`first`ten `last`e (ikisi dahil) sezon kodları; yalnız 2000–2099 sezonları."""
    start, end = int(_check_season(first)[:2]), int(_check_season(last)[:2])
    if start > end:
        raise ValueError(f"sezon aralığı ters: {first} > {last}")
    return tuple(f"{year:02d}{(year + 1) % 100:02d}" for year in range(start, end + 1))


def _check_fields(entry: dict[str, Any]) -> None:
    keys = frozenset(entry)
    missing = REQUIRED_FIELDS - keys
    if missing:
        raise ValueError(f"lig kaydında eksik alan: {sorted(missing)} ({entry.get('code', '?')})")
    unknown = keys - REQUIRED_FIELDS
    if unknown:
        raise ValueError(f"lig kaydında bilinmeyen alan: {sorted(unknown)} ({entry['code']})")
    wrong = [name for name in _TEXT_FIELDS if not isinstance(entry[name], str)]
    if wrong:
        raise ValueError(f"lig kaydında dize olmayan alan: {wrong} ({entry['code']})")
    tier = entry["tier"]
    if isinstance(tier, bool) or not isinstance(tier, int) or tier < 1:
        raise ValueError(f"lig kaydında geçersiz tier: {tier!r} ({entry['code']})")


def _league(entry: object, current_season: str) -> HistoryLeague:
    if not isinstance(entry, dict):
        raise ValueError(f"lig kaydı eşleme değil: {entry!r}")
    _check_fields(entry)
    if entry["kind"] not in KINDS:
        raise ValueError(f"geçersiz kind: {entry['kind']!r} ({entry['code']})")
    if entry["kind"] == EXTRA and entry["first_season"] != "":
        raise ValueError(f"ek lig tek dosyadır, first_season boş olmalı ({entry['code']})")
    if entry["kind"] == MAIN and _check_season(entry["first_season"]) > current_season:
        raise ValueError(f"first_season güncel sezondan sonra ({entry['code']})")
    return HistoryLeague(**entry)


def _check_unique(leagues: tuple[HistoryLeague, ...]) -> None:
    for field in ("code", "league_id"):
        values = [getattr(league, field) for league in leagues]
        repeated = sorted({value for value in values if values.count(value) > 1})
        if repeated:
            raise ValueError(f"yinelenen {field}: {repeated}")


def load_catalog(path: Path) -> Catalog:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"current_season", "leagues"}:
        raise ValueError(f"{path}: kökte tam olarak 'current_season' ve 'leagues' olmalı")
    current = _check_season(raw["current_season"])
    if not isinstance(raw["leagues"], list):
        raise ValueError(f"{path}: 'leagues' bir liste olmalı")
    leagues = tuple(_league(entry, current) for entry in raw["leagues"])
    _check_unique(leagues)
    return Catalog(current_season=current, leagues=leagues)


def file_paths(league: HistoryLeague, *, current_season: str) -> tuple[str, ...]:
    """Ana lig: sezon başına bir dosya; ek lig: bütün yılları taşıyan tek dosya."""
    if league.kind == EXTRA:
        return (f"/new/{league.code}.csv",)
    seasons = season_codes(league.first_season, current_season)
    return tuple(f"/mmz4281/{season}/{league.code}.csv" for season in seasons)


def declared_paths(catalog: Catalog) -> tuple[str, ...]:
    """Kataloğun istediği her yol, sıralı ve tekil — `sources.yaml`ın beyanı bununla EŞİT olmalı."""
    return tuple(
        sorted(
            {
                path
                for league in catalog.leagues
                for path in file_paths(league, current_season=catalog.current_season)
            }
        )
    )


def season_of_path(path: str) -> str | None:
    """`/mmz4281/2526/E0.csv` → "2526"; ek lig (`/new/BRA.csv`) ya da tanınmayan yol → None."""
    found = _MAIN_PATH.fullmatch(path)
    return None if found is None else found.group(1)
