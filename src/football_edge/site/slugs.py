"""Sitenin URL bölütleri (Faz 6 İz B tasarımı §8.2).

`naming.normalise_team`e DAYANMAZ: o, kaynaklar arası eşleşme için yük taşır ve eşleşme düzeltmesi
URL'leri sessizce değiştirmemeli. Bu fonksiyonun her değişikliği `tests/test_site_slugs.py`deki
dondurulmuş vektörleri kırmızı yapar — yayımlanmış bir URL'yi değiştirmek bilinçli bir karardır.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

import yaml

from football_edge.site.contract import RESERVED_LEAGUE_SLUGS

# NFKD'nin ayrıştırmadığı harfler (birleştirici işaret taşımazlar).
_FOLD = str.maketrans(
    {
        "İ": "i",
        "I": "i",
        "ı": "i",
        "ß": "ss",
        "ø": "o",
        "Ø": "o",
        "æ": "ae",
        "Æ": "ae",
        "œ": "oe",
        "Œ": "oe",
        "đ": "d",
        "Đ": "d",
        "ł": "l",
        "Ł": "l",
    }
)
_APOSTROPHES = re.compile(r"['’ʼ`]")
_NON_SLUG = re.compile(r"[^a-z0-9]+")
SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def slugify(text: str) -> str:
    """ASCII küçük harf, rakam ve tek tire: `Beşiktaş JK` → `besiktas-jk`.

    Kesme işareti silinir (`Newell's` → `newells`); başka her harf dışı dizi tek tireye iner.
    Harf ya da rakam kalmazsa `ValueError`: boş bölüt yol üretmez.
    """
    folded = unicodedata.normalize("NFKD", text.translate(_FOLD))
    ascii_only = "".join(char for char in folded if not unicodedata.combining(char))
    lowered = _APOSTROPHES.sub("", ascii_only).lower()
    slug = _NON_SLUG.sub("-", lowered).strip("-")
    if not slug:
        raise ValueError(f"slug üretilemedi: {text!r}")
    return slug


def match_slug(home: str, away: str) -> str:
    """Maç yolunun süs bölütü (`{home}-vs-{away}`); yolun kimliği `path_id`dir (§8.1)."""
    return f"{slugify(home)}-vs-{slugify(away)}"


def load_league_slugs(path: Path) -> Mapping[str, str]:
    """`config/site_leagues.yaml`: lig kimliği → kalıcı URL bölütü; biçim, tekillik, ayrılmış ad.

    Lig slug'ı addan türetilemez: `ger.1` ve `aut.1`in ikisi de "Bundesliga". Değer yayımlandıktan
    sonra değişirse URL değişir — AK20 b'nin kaybolan-slug kontrolü onu kırmızı yapar.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"version", "league_slugs"} or raw["version"] != 1:
        raise ValueError(f"{path}: kökte yalnız `version: 1` ve `league_slugs` olmalı")
    entries = raw["league_slugs"]
    if not isinstance(entries, dict) or not entries:
        raise ValueError(f"{path}: `league_slugs` boş olmayan bir eşlem olmalı")
    seen: dict[str, str] = {}
    for league_id, slug in entries.items():
        if not isinstance(slug, str) or SLUG.fullmatch(slug) is None or len(slug) > 80:
            raise ValueError(f"{path}: {league_id} slug'ı biçim dışı")
        if slug in RESERVED_LEAGUE_SLUGS:
            raise ValueError(f"{path}: {league_id} slug'ı ayrılmış bir bölüt")
        if slug in seen:
            raise ValueError(f"{path}: {league_id} ve {seen[slug]} aynı slug'ı taşıyor")
        seen[slug] = str(league_id)
    return MappingProxyType({str(key): str(value) for key, value in entries.items()})
