"""Dondurulmuş hiperparametreler (Faz 3 tasarımı §5.2, R129): `config/model_faz3.yaml`.

Dosyayı `select` yazar, controller commit'ler; walk-forward, ön kayıt ve `final_eval` yalnız bu
dosyayı okur. Katalog ve kilidin sha256'sı dosyadadır: ikisinden biri değişirse walk-forward
reddeder (§12/8 — katalog kilitte değil, ama modelin gördüğü katalog sabitlenir).
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from football_edge.market.devig import METHODS
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import ORDERED, EloModelConfig

VERSION = 1
MODEL_CONFIG_PATH = Path("config/model_faz3.yaml")
_TOP = frozenset(
    {
        "version",
        "selected_at",
        "catalog_sha256",
        "lock_sha256",
        "method",
        "elo",
        "dixon_coles",
        "cadence_days",
        "tau",
        "sensitivity",
    }
)


class ModelConfigError(ValueError):
    """Model yapılandırması okunamadı ya da eksik/fazla alan taşıyor."""


@dataclass(frozen=True)
class ModelConfig:
    selected_at: str
    catalog_sha256: str
    lock_sha256: str
    method: str
    elo: EloModelConfig
    dixon_coles: DCConfig
    cadence_days: int
    tau: float
    sensitivity: tuple[float, ...]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump_model_config(config: ModelConfig) -> str:
    payload = {
        "version": VERSION,
        "selected_at": config.selected_at,
        "catalog_sha256": config.catalog_sha256,
        "lock_sha256": config.lock_sha256,
        "method": config.method,
        "elo": asdict(config.elo),
        "dixon_coles": asdict(config.dixon_coles),
        "cadence_days": config.cadence_days,
        "tau": config.tau,
        "sensitivity": list(config.sensitivity),
    }
    return yaml.safe_dump(payload, sort_keys=True, allow_unicode=True)


def _section(
    raw: dict[str, Any], name: str, fields: frozenset[str], optional: frozenset[str] = frozenset()
) -> dict[str, Any]:
    section = raw.get(name)
    if not isinstance(section, dict) or not fields - optional <= set(section) <= fields:
        raise ModelConfigError(f"{name}: alanlar {sorted(fields)} olmalı")
    return section


def _elo_optional(raw: dict[str, Any]) -> frozenset[str]:
    """16k-b: δ (`draw`) yalnız `quadratic` biçimde okunur; `ordered` dosya onu taşımayabilir
    (eksikse sınıfın varsayılanı dolar, olasılığa girmez). Mühürlü `model_faz3.yaml` alanı taşır
    ve aynen okunur; `quadratic`te ve `draw_form`u yazmayan dosyada alan zorunlu kalır."""
    section = raw.get("elo")
    if isinstance(section, dict) and section.get("draw_form") == ORDERED:
        return frozenset({"draw"})
    return frozenset()


def load_model_config(path: Path) -> ModelConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ModelConfigError(f"{path}: okunamadı: {error}") from error
    if not isinstance(raw, dict) or set(raw) != _TOP:
        raise ModelConfigError(f"{path}: üst alanlar {sorted(_TOP)} olmalı")
    # YAML `true` Python'da `== 1`dir: bool `int`in alt sınıfı, tip ayrıca denetlenir.
    if type(raw["version"]) is not int or raw["version"] != VERSION:
        raise ModelConfigError(f"{path}: sürüm {raw['version']!r}, beklenen {VERSION}")
    if raw["method"] not in METHODS:
        raise ModelConfigError(f"{path}: bilinmeyen vig yöntemi {raw['method']!r}")
    try:
        elo_fields = frozenset(asdict(EloModelConfig()))
        elo = EloModelConfig(**_section(raw, "elo", elo_fields, _elo_optional(raw)))
        dc = DCConfig(**_section(raw, "dixon_coles", frozenset(asdict(DCConfig()))))
        return ModelConfig(
            selected_at=str(raw["selected_at"]),
            catalog_sha256=str(raw["catalog_sha256"]),
            lock_sha256=str(raw["lock_sha256"]),
            method=str(raw["method"]),
            elo=elo,
            dixon_coles=dc,
            cadence_days=int(raw["cadence_days"]),
            tau=float(raw["tau"]),
            sensitivity=tuple(float(value) for value in raw["sensitivity"]),
        )
    except (TypeError, ValueError) as error:
        raise ModelConfigError(f"{path}: geçersiz değer: {error}") from error
