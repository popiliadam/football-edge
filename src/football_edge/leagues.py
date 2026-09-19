from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class League:
    id: str
    odds_api_key: str
    name: str
    country: str
    lang: str
    gl: str
    active: bool
    footystats_path: str


REQUIRED_FIELDS = frozenset(
    {"id", "odds_api_key", "name", "country", "lang", "gl", "active", "footystats_path"}
)


def _validate(entry: dict[str, Any], seen: frozenset[str]) -> None:
    keys = frozenset(entry)
    missing = REQUIRED_FIELDS - keys
    if missing:
        raise ValueError(f"lig kaydında eksik alan: {sorted(missing)} ({entry.get('id', '?')})")
    unknown = keys - REQUIRED_FIELDS
    if unknown:
        raise ValueError(f"lig kaydında bilinmeyen alan: {sorted(unknown)} ({entry['id']})")
    if entry["id"] in seen:
        raise ValueError(f"yinelenen lig id: {entry['id']}")


def load_leagues(path: Path) -> tuple[League, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "leagues" not in raw:
        raise ValueError(f"{path}: kökte 'leagues' anahtarı yok")
    entries = raw["leagues"]
    leagues: tuple[League, ...] = ()
    seen: frozenset[str] = frozenset()
    for entry in entries:
        _validate(entry, seen)
        leagues = (*leagues, League(**entry))
        seen = seen | {entry["id"]}
    return leagues


def active_leagues(leagues: tuple[League, ...]) -> tuple[League, ...]:
    return tuple(league for league in leagues if league.active)
