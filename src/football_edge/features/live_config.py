"""Kademe 2'nin dondurulmuş kümesi (Plan 2 R185; I-11) ve işletme ayarları.

İki dosya. `config/faz4_live.yaml` SEÇİM-ANLAMLI alanları taşır (kademe 1 sürümü, Jev modeli, kapı
eşikleri); kümenin kimliği bu dosyanın KENDİSİDİR: `prompt_version = sha256(soru dosyası + bu
dosya)` her kademe 2 satırına girer (yeni migration yok; 0012'nin `^[0-9a-f]{64}$` kısıtı).
`config/faz4_ops.yaml` işletme ayarlarını taşır (tahmin birimi, taraf tavanı, karar yaşı) ve
hash'e GİRMEZ: fiyat düzeltmesi seçim dilimi sayacını sıfırlamaz (spec R185'ten bilinçli sapma).
`frozen_violations` kümenin YAZIMA hazır olduğunu sorar (model sabit, kademe 1 sürümü güncel).
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from football_edge.features.questions import QUESTIONS_PATH

LIVE_CONFIG_PATH = Path("config/faz4_live.yaml")
OPS_CONFIG_PATH = Path("config/faz4_ops.yaml")
# Dondurulmuş küme eksik/bozuk ya da dönen model kümedekinden farklı (collect 2–8, backtest 9–14,
# live 15/18, bütçe 16, Jev anahtarı 17, boş tur 19, site 20–24).
EXIT_FROZEN_SET = 25
TIER1 = "tier1"
TIER2 = "tier2"
MAX_DECISION_AGE_HOURS = 6  # spec M-2: daha uzun pencere kabul edilmez
_LIVE_KEYS = frozenset({"tier1_prompt_version", "jev_model", "min_belongs", "min_reliability"})
_OPS_KEYS = frozenset({"estimate_usd", "max_sides_per_run", "max_decision_age_hours"})
_SHA = re.compile(r"^[0-9a-f]{64}$")


class LiveConfigError(ValueError):
    """`config/faz4_live.yaml` ya da `config/faz4_ops.yaml` sözleşmeye uymuyor; alan adıyla."""


@dataclass(frozen=True)
class LiveConfig:
    tier1_prompt_version: str
    jev_model: str | None
    min_belongs: float
    min_reliability: float
    estimate_usd: Mapping[str, float]
    max_sides_per_run: int
    max_decision_age: timedelta
    prompt_version: str


def live_prompt_version(questions_bytes: bytes, live_bytes: bytes) -> str:
    return hashlib.sha256(questions_bytes + live_bytes).hexdigest()


def _number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _unit(raw: Mapping[str, Any], key: str) -> float:
    value = raw[key]
    if not _number(value) or not 0.0 <= value <= 1.0:
        raise LiveConfigError(f"{key}: 0 ile 1 arasında sayı olmalı ({value!r})")
    return float(value)


def _whole(raw: Mapping[str, Any], key: str, low: int, high: int) -> int:
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise LiveConfigError(f"{key}: {low}–{high} arası tam sayı olmalı ({value!r})")
    return value


def _estimates(raw: Mapping[str, Any]) -> Mapping[str, float]:
    found = raw["estimate_usd"]
    if not isinstance(found, Mapping) or set(found) != {TIER1, TIER2}:
        raise LiveConfigError(f"estimate_usd: tam olarak {TIER1} ve {TIER2} olmalı")
    for key, value in found.items():
        if not _number(value) or not (math.isfinite(value) and value > 0):
            raise LiveConfigError(f"estimate_usd.{key}: sonlu ve > 0 olmalı ({value!r})")
    return MappingProxyType({str(k): float(v) for k, v in found.items()})


def _model(raw: Mapping[str, Any]) -> str | None:
    value = raw["jev_model"]
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise LiveConfigError(f"jev_model: null ya da boş olmayan metin olmalı ({value!r})")
    return value


def _mapping(path: Path, keys: frozenset[str]) -> tuple[bytes, Mapping[str, Any]]:
    content = path.read_bytes()
    raw = yaml.safe_load(content)
    if not isinstance(raw, Mapping) or set(raw) != keys:
        raise LiveConfigError(f"{path}: alanlar tam olarak {sorted(keys)} olmalı")
    return content, raw


def load_live_config(
    path: Path = LIVE_CONFIG_PATH,
    *,
    ops_path: Path = OPS_CONFIG_PATH,
    questions_path: Path = QUESTIONS_PATH,
) -> LiveConfig:
    content, live = _mapping(path, _LIVE_KEYS)
    _, ops = _mapping(ops_path, _OPS_KEYS)
    version = live["tier1_prompt_version"]
    if not isinstance(version, str) or _SHA.fullmatch(version) is None:
        raise LiveConfigError(f"tier1_prompt_version: 64 haneli sha256 olmalı ({version!r})")
    hours = _whole(ops, "max_decision_age_hours", 1, MAX_DECISION_AGE_HOURS)
    return LiveConfig(
        tier1_prompt_version=version,
        jev_model=_model(live),
        min_belongs=_unit(live, "min_belongs"),
        min_reliability=_unit(live, "min_reliability"),
        estimate_usd=_estimates(ops),
        max_sides_per_run=_whole(ops, "max_sides_per_run", 1, 1000),
        max_decision_age=timedelta(hours=hours),
        prompt_version=live_prompt_version(questions_path.read_bytes(), content),
    )


def frozen_violations(config: LiveConfig, *, questions_prompt_version: str) -> tuple[str, ...]:
    """Kademe 2 YAZIMINA engeller: model sabit değil ya da kademe 1 sürümü eski soru dosyası."""
    found: tuple[str, ...] = ()
    if config.jev_model is None:
        found = (*found, "jev_model sabitlenmedi (null) — Plan 2 Task 5 ölçer ve sabitler")
    elif "latest" in config.jev_model.casefold():
        found = (*found, f"jev_model {config.jev_model!r}: 'latest' takma adı sabit değildir")
    if config.tier1_prompt_version != questions_prompt_version:
        found = (
            *found,
            "tier1_prompt_version soru dosyasının bugünkü sha256'sı değil — kademe 1 cevapları "
            "başka bir sürüme ait; yeni küme gerekir",
        )
    return found
