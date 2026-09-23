"""Donmuş harman ağırlığı (Faz 4 tasarımı §2 T0a, R161): `config/blend_weights_faz3.yaml`.

Gölge satırları yalnız bileşen taşır; harman haftalık raporda BU dosyanın ağırlığıyla kurulur.
Ağırlık geliştirme döneminin E satırlarıyla fit edilir (`wf_eval.frozen_weights`): holdout ve
sonrası dönemi ağırlığı hiç görmez. Dosyayı `live freeze-weights` yazar, controller commit'ler.
Model yapılandırması, kilit ve katalog sha256'sı dosyadadır: biri değişirse rapor reddeder —
başka bir yapılandırmanın satırları bu ağırlıkla harmanlanmaz.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from football_edge.backtest.walkforward import BLEND_COMPONENTS, Row
from football_edge.backtest.wf_eval import (
    LEAGUE_MIN_MATCHES,
    frozen_rows,
    frozen_weights,
    pooled_weights,
)
from football_edge.model.pool import MIN_FIT_MATCHES

VERSION = 1
BLEND_WEIGHTS_PATH = Path("config/blend_weights_faz3.yaml")
LIVE_SEASON = "live"
# Hiçbir lig kodu değil: `frozen_weights` onu HER ZAMAN havuza düşürür (satırı yok) — havuz ağırlığı
# da aynı fonksiyondan. `fallback`ten atılması bu yüzden bilgi kaybı değildir: havuzun kendisi fit
# edilemezse `freeze` dosyayı hiç kurmaz (`PooledFitFailed`).
_POOLED = "*"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_DIGESTS = ("model_config_sha256", "lock_sha256", "catalog_sha256")
_TOP = frozenset({"version", *_DIGESTS, "components", "pooled", "leagues", "fallback"})


class BlendWeightsError(ValueError):
    """Harman ağırlığı dosyası okunamadı ya da eksik/fazla/geçersiz alan taşıyor."""


class PooledFitFailed(ValueError):
    """Havuz ağırlığı fit edilemedi: `MARKET_ONLY` dondurulmaz (son inceleme I-2).

    Yazılsaydı havuza düşen her lig adsız biçimde yalnız piyasayı alırdı ve rapor onu
    "havuz ağırlığı" diye okurdu."""


@dataclass(frozen=True)
class BlendWeights:
    model_config_sha256: str
    lock_sha256: str
    catalog_sha256: str
    components: tuple[str, ...]  # BLEND_COMPONENTS sırası
    pooled: tuple[float, ...]  # bütün ana liglerin E satırlarıyla; satır yetmezse MARKET_ONLY
    leagues: Mapping[str, tuple[float, ...]]  # yalnız kendi ağırlığını fit eden ligler
    fallback: tuple[str, ...]  # LEAGUE_MIN_MATCHES altında kalıp havuza düşen ligler


def freeze(
    rows: Sequence[Row],
    leagues: Sequence[str],
    *,
    model_config_sha256: str,
    lock_sha256: str,
    catalog_sha256: str,
) -> BlendWeights:
    """Ana liglerin canlı ağırlığı; yalnız `zone == E` satırları fit'e girer (`frozen_weights`).

    Havuz fit edilemezse (az E satırı ya da yakınsamama) `PooledFitFailed`: dosya kurulmaz."""
    if pooled_weights(rows) is None:
        count = len(frozen_rows(rows))
        cause = (
            f"{count} E satırı < {MIN_FIT_MATCHES}"
            if count < MIN_FIT_MATCHES
            else f"{count} E satırıyla yakınsamama"
        )
        raise PooledFitFailed(f"havuz ağırlığı fit edilemedi: {cause} — MARKET_ONLY dondurulmaz")
    found, fell = frozen_weights(rows, [(league, LIVE_SEASON) for league in (*leagues, _POOLED)])
    fallback = frozenset(entry.removesuffix(f"/{LIVE_SEASON}") for entry in fell)
    return BlendWeights(
        model_config_sha256=model_config_sha256,
        lock_sha256=lock_sha256,
        catalog_sha256=catalog_sha256,
        components=BLEND_COMPONENTS,
        pooled=found[(_POOLED, LIVE_SEASON)],
        leagues=MappingProxyType(
            {
                league: found[(league, LIVE_SEASON)]
                for league in sorted(set(leagues))
                if league not in fallback
            }
        ),
        fallback=tuple(sorted(fallback - {_POOLED})),
    )


def fallback_reasons(rows: Sequence[Row], weights: BlendWeights) -> Mapping[str, str]:
    """Havuza düşen her ligin sebebi: az E satırı ya da kendi fitinin yakınsamaması.

    `LEAGUE_MIN_MATCHES` ≥ `MIN_FIT_MATCHES` olduğundan eşiği geçen ligin fiti yalnız
    yakınsamadığı için düşer. Dosya biçimi değişmez; sebep `freeze-weights` logundadır."""
    counts = Counter(row.key.league for row in frozen_rows(rows))
    return MappingProxyType(
        {
            league: (
                f"{counts[league]} E satırı < {LEAGUE_MIN_MATCHES}"
                if counts[league] < LEAGUE_MIN_MATCHES
                else f"kendi fiti yakınsamadı ({counts[league]} E satırı)"
            )
            for league in weights.fallback
        }
    )


def weights_for(weights: BlendWeights, league: str) -> tuple[float, ...]:
    """Ligin kendi ağırlığı; yoksa (havuza düşen ya da dosyada olmayan lig) havuz ağırlığı."""
    return weights.leagues.get(league, weights.pooled)


def dump_blend_weights(weights: BlendWeights) -> str:
    payload = {
        "version": VERSION,
        "model_config_sha256": weights.model_config_sha256,
        "lock_sha256": weights.lock_sha256,
        "catalog_sha256": weights.catalog_sha256,
        "components": list(weights.components),
        "pooled": list(weights.pooled),
        "leagues": {league: list(values) for league, values in sorted(weights.leagues.items())},
        "fallback": list(weights.fallback),
    }
    return yaml.safe_dump(payload, sort_keys=True, allow_unicode=True)


def _vector(value: Any, name: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != len(BLEND_COMPONENTS):
        raise BlendWeightsError(f"{name}: {len(BLEND_COMPONENTS)} ağırlık olmalı: {value!r}")
    if not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value):
        raise BlendWeightsError(f"{name}: ağırlık sayı olmalı: {value!r}")
    found = tuple(float(item) for item in value)
    if not all(math.isfinite(item) and item >= 0.0 for item in found):
        raise BlendWeightsError(f"{name}: ağırlık sonlu ve ≥ 0 olmalı: {found}")
    return found


def _digest(raw: dict[str, Any], name: str) -> str:
    # YAML tırnaksız yalnız-rakam özeti tamsayı okur: tip de denetlenir, str() ile yamanmaz.
    value = raw[name]
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise BlendWeightsError(f"{name}: 64 haneli küçük harf sha256 olmalı: {value!r}")
    return value


def load_blend_weights(path: Path) -> BlendWeights:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise BlendWeightsError(f"{path}: okunamadı: {error}") from error
    if not isinstance(raw, dict) or set(raw) != _TOP:
        raise BlendWeightsError(f"{path}: üst alanlar {sorted(_TOP)} olmalı")
    # YAML `true` Python'da `== 1`dir: bool `int`in alt sınıfı, tip ayrıca denetlenir.
    if type(raw["version"]) is not int or raw["version"] != VERSION:
        raise BlendWeightsError(f"{path}: sürüm {raw['version']!r}, beklenen {VERSION}")
    if raw["components"] != list(BLEND_COMPONENTS):
        raise BlendWeightsError(f"{path}: bileşenler {list(BLEND_COMPONENTS)} olmalı")
    leagues, fallback = raw["leagues"], raw["fallback"]
    if not isinstance(leagues, dict) or not all(isinstance(key, str) for key in leagues):
        raise BlendWeightsError(f"{path}: leagues lig kodu → ağırlık eşlemi olmalı")
    if not isinstance(fallback, list) or not all(isinstance(item, str) for item in fallback):
        raise BlendWeightsError(f"{path}: fallback lig kodu listesi olmalı")
    if set(fallback) & set(leagues):
        raise BlendWeightsError(
            f"{path}: hem kendi ağırlığı hem havuz: {sorted(set(fallback) & set(leagues))}"
        )
    return BlendWeights(
        model_config_sha256=_digest(raw, "model_config_sha256"),
        lock_sha256=_digest(raw, "lock_sha256"),
        catalog_sha256=_digest(raw, "catalog_sha256"),
        components=BLEND_COMPONENTS,
        pooled=_vector(raw["pooled"], "pooled"),
        leagues=MappingProxyType(
            {
                league: _vector(values, f"leagues.{league}")
                for league, values in sorted(leagues.items())
            }
        ),
        fallback=tuple(fallback),
    )
