"""TFF baş hakem atamasını `matches` satırına bağlama (spec 2026-10-02 §4).

Bu modülün ilk parçası takım adı eşlemesidir: `config/tff_teams.yaml`. Anahtar `normalise_team(TFF
adı)`, değer bu sezon `matches`te (`league_id = tur.1`) GÖRÜLEN The Odds API yazımı ya da `null`
(yazım henüz görülmedi — uydurulmaz; o takımın maçı `awaiting_alias` sayılır).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from football_edge.naming import normalise_team

TFF_TEAMS_PATH = Path("config/tff_teams.yaml")
_TOP_KEYS = frozenset({"league_label_contains", "league_id", "teams"})
# Controller düzeltmesi C1: bu sözcüklerden birini taşıyan etiket kadın/genç ligidir, işlenmez.
_EXCLUDED_LEAGUE_WORDS = ("kadın", "kadin", "u19", "u21", "gelişim", "gelisim")


@dataclass(frozen=True)
class TeamMap:
    league_label_contains: str  # bu ifadeyi TAM ifade olarak TAŞIYAN TFF lig bloğu işlenir (C1)
    league_id: str  # `matches.league_id` hedefi
    teams: Mapping[str, str | None]  # normalise_team(TFF adı) → API adı | None

    def matches_league(self, label: str) -> bool:
        """Etiket `league_label_contains`ı TAM ifade olarak taşır ("Süper Ligi" eşleşmez) ve
        kadın/genç ligi bloğu değildir (controller düzeltmesi C1). `İ` önce `i`ye katlanır: yalnız
        `casefold` onu `i̇` yapar ve büyük harfli "SÜPER LİG" sessizce lig dışı kalırdı."""
        folded = label.replace("İ", "i").casefold()
        if any(word in folded for word in _EXCLUDED_LEAGUE_WORDS):
            return False
        phrase = re.escape(self.league_label_contains.casefold()) + r"(?!\w)"
        return re.search(phrase, folded) is not None


def load_team_map(path: Path = TFF_TEAMS_PATH) -> TeamMap:
    """Biçim dışı her dosya `ValueError`dır; mesaj yolu ve kuralı adlandırır."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != _TOP_KEYS:
        raise ValueError(f"{path}: üst anahtarlar {sorted(_TOP_KEYS)} olmalı")
    label, league_id, teams = raw["league_label_contains"], raw["league_id"], raw["teams"]
    if not (isinstance(label, str) and label and isinstance(league_id, str) and league_id):
        raise ValueError(f"{path}: league_label_contains ve league_id boş olmayan metin olmalı")
    if not isinstance(teams, dict) or not teams:
        raise ValueError(f"{path}: teams boş olmayan bir eşleme olmalı")
    return TeamMap(label, league_id, _checked_teams(path, teams))


def _checked_teams(path: Path, teams: Mapping[Any, Any]) -> dict[str, str | None]:
    for key, value in teams.items():
        if not isinstance(key, str) or normalise_team(key) != key:
            raise ValueError(f"{path}: anahtar normalise_team çıktısı değil: {key!r}")
        if value is not None and not (isinstance(value, str) and value.strip()):
            raise ValueError(f"{path}: {key!r} değeri null ya da boş olmayan metin olmalı")
    return {str(key): value for key, value in teams.items()}
