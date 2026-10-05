"""Faz 4 canlı ayağın ön kaydı: `config/faz4_preregistration.yaml` (Plan 3 spec §4; R188–R199).

Yükleyici şemayı BİREBİR ister — eksik/fazla/yinelenen alan, yanlış tür, aralık dışı sayı ve
desteklenmeyen yöntem adı alan adıyla reddedilir: değerlendirme kodu yalnız ön kaydın adlandırdığı
yöntemi uygular, ön kayıt da yalnız uygulanabilecek yöntemi adlandırabilir. `COMPARISONS` ve
`COUNTS_PRINTED` renderer'ın sözleşmesidir (ana spec §8, 16c dersi): ikisi de dosyayla aynı olmalı.
Dosyanın depoyla karşılaştırılması `gate4.seal`dadır.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

PREREGISTRATION_PATH = Path("config/faz4_preregistration.yaml")
QUESTIONS = "config/jev_questions.yaml"
LIVE = "config/faz4_live.yaml"
OPS = "config/faz4_ops.yaml"
LANGUAGES = "config/languages.yaml"
LEAGUES = "config/leagues.yaml"
# Spec §5: donmuş dosyalar mühürle birebir kalır (`seal.seal_violations` zorlar); kollar yalnız
# kaydedilir — pencerede sayımla gerekçeli değişebilirler, rapor mühürlü sha'yla karşılaştırır.
FROZEN_FILES = frozenset(
    {
        "config/model_faz3.yaml",
        "config/blend_weights_faz3.yaml",
        "config/history_lock.yaml",
        "config/history_leagues.yaml",
        LIVE,
        QUESTIONS,
    }
)
RECORDED_FILES = frozenset({"config/history_aliases.yaml", OPS, LANGUAGES, LEAGUES})
COMPARISONS = ("D1", "D1b", "D1c", "D2", "D3", "D5", "D6", "D7", "D8", "D9", "D10")
COUNTS_PRINTED = (
    "window_start",
    "seal_tag_sha",
    "preregistration_sha256",
    "closure_kind",
    "closing_round",
    "evaluation_date",
    "closing_haberli_decisions",
    "d1_n",
    "n_stop",
    "shadow_matches",
    "haberli_matches",
    "incomplete",
    "rejected_price",
    "fallback_leagues",
    "unsettled",
    "no_decision",
    "side_status",
    "imputed_sides",
    "asked_after_kickoff",
    "missing_by_question",
    "language_excluded",
    "league_excluded",
    "item_set_hash_mismatch",
    "outside_frozen_set",
    "language_entry_reports",
    "arm_changes",
)
CLOSURE_KINDS = ("n_stop", "date", "vendor", "user")
N_STOP_FLOOR = 1800  # ana spec §7 güç tahmini; R194 sabitler
TRAIN_REQUIRES = ("haberli", "harman_complete", "settled", "in_window", "gate_language")
BOOTSTRAP_ORDER = ("decided_at", "match_id")
LEVELS = ("none", "low", "medium", "high")
VERDICTS = ("passed", "failed", "underpowered")
# Desteklenen tek yöntemler: alan → değer (spec R189–R193, §1).
_LITERALS: Mapping[tuple[str, ...], object] = MappingProxyType(
    {
        ("phase",): "faz4",
        ("leg",): "live",
        ("seal_tag",): "faz4-onkayit",
        ("window", "start"): "first_asked_after_seal_commit",
        ("stop", "tie"): "n_stop",
        ("feature", "sign"): "away_minus_home",
        ("feature", "level_score"): "choice",
        ("feature", "asked_after_kickoff"): "missing",
        ("beta", "solver"): "projected_bisection",
        ("beta", "train", "result_date"): "strictly_before_decision_utc_date",
        ("gate",): "D1",
        ("methods", "log_loss"): "market.metrics.per_match_log_loss",
        ("methods", "bootstrap"): "market.metrics.bootstrap_mean",
        ("methods", "d1b"): "round_cluster",
        ("methods", "d3_placebo"): "backtest.strategies.Placebo",
        ("methods", "calibration"): "market.metrics.calibration_or_none",
        ("methods", "d9_sd_ddof"): 1,
        ("methods", "d9_sd_weeks"): 4,
        ("methods", "d10_feature"): "coverage_indicator",
    }
)
_KEYS: Mapping[tuple[str, ...], frozenset[str]] = MappingProxyType(
    {
        (): frozenset(
            {
                "phase",
                "leg",
                "seal_tag",
                "window",
                "stop",
                "feature",
                "level_scores",
                "beta",
                "comparisons",
                "gate",
                "descriptive_bounds",
                "d8_questions",
                "d5_leagues",
                "bootstrap",
                "tau",
                "calibration_bins",
                "methods",
                "closure_kinds",
                "languages",
                "sha256",
                "counts_printed",
                "verdicts",
            }
        ),
        ("window",): frozenset({"tier2_prompt_version", "start"}),
        ("stop",): frozenset({"n_stop", "date_limit", "tie", "evaluation_lag_days"}),
        ("feature",): frozenset(
            {
                "weakness",
                "strength",
                "excluded",
                "divisor",
                "sign",
                "level_score",
                "c_min",
                "asked_after_kickoff",
            }
        ),
        ("level_scores",): frozenset(LEVELS),
        ("beta",): frozenset({"lambda", "lower", "upper", "solver", "tol", "empty", "train"}),
        ("beta", "train"): frozenset({"gap_hours", "result_date", "requires"}),
        ("descriptive_bounds",): frozenset({"lower", "upper"}),
        ("bootstrap",): frozenset({"resamples", "seed", "level", "order"}),
        ("methods",): frozenset(
            {
                "log_loss",
                "bootstrap",
                "d1b",
                "d3_placebo",
                "calibration",
                "d9_sd_ddof",
                "d9_sd_weeks",
                "d10_feature",
            }
        ),
        ("languages",): frozenset({"sealed", "entry"}),
        ("languages", "entry"): frozenset({"min_n", "min_accuracy", "jev_model"}),
        ("verdicts",): frozenset(VERDICTS),
    }
)
_SHA = re.compile(r"^[0-9a-f]{64}$")


class PreregistrationError(ValueError):
    """Ön kayıt dosyası şemaya uymuyor; alan adıyla."""


@dataclass(frozen=True)
class Faz4Preregistration:
    """Ön kaydın doğrulanmış hâli; alanlar spec §4'ün sırasıyla (R189–R195)."""

    tier2_prompt_version: str
    n_stop: int
    date_limit: datetime
    evaluation_lag_days: int
    weakness: tuple[str, ...]
    strength: tuple[str, ...]
    excluded: tuple[str, ...]
    divisor: int
    c_min: float
    level_scores: Mapping[str, float]
    ridge_lambda: float
    beta_lower: float
    beta_upper: float
    tol: float
    gap_hours: int
    comparisons: tuple[str, ...]
    gate: str
    descriptive_bounds: tuple[float, float]
    d8_questions: tuple[str, ...]
    d5_leagues: tuple[str, ...]
    resamples: int
    seed: int
    level: float
    tau: float
    calibration_bins: int
    closure_kinds: tuple[str, ...]
    sealed_languages: tuple[str, ...]
    entry_min_n: int
    entry_min_accuracy: float
    entry_jev_model: str
    sha256: Mapping[str, str]
    counts_printed: tuple[str, ...]
    verdicts: Mapping[str, str]


class _UniqueKeyLoader(yaml.SafeLoader):
    """Yinelenen anahtarı reddeder: mühürlü metni okuyan insan kodun kullandığı sayıyı görsün."""


def _unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    keys = [loader.construct_object(key) for key, _ in node.value]
    if duplicates := sorted({str(k) for k in keys if keys.count(k) > 1}):
        raise PreregistrationError(f"yinelenen alan {duplicates}")
    return loader.construct_mapping(node)


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _unique_mapping,
)


def _name(path: tuple[str, ...]) -> str:
    return ".".join(path) or "kök"


def _at(raw: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = raw
    for key in path:
        value = value[key]
    return value


def _check_keys(raw: object, path: tuple[str, ...] = ()) -> None:
    if not isinstance(raw, Mapping):
        raise PreregistrationError(f"{_name(path)}: eşlem olmalı")
    expected = _KEYS[path]
    if missing := sorted(expected - set(raw)):
        raise PreregistrationError(f"{_name(path)}: eksik alan {missing}")
    if extra := sorted(set(raw) - expected):
        raise PreregistrationError(f"{_name(path)}: bilinmeyen alan {extra}")
    for key in sorted(expected):
        if (*path, key) in _KEYS:
            _check_keys(raw[key], (*path, key))


def _real(raw: Mapping[str, Any], path: tuple[str, ...], low: float, high: float) -> float:
    value = _at(raw, path)
    ok = isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)
    if not ok or not low <= value <= high:
        raise PreregistrationError(f"{_name(path)}: [{low}, {high}] aralığında sayı ({value!r})")
    return float(value)


def _whole(raw: Mapping[str, Any], path: tuple[str, ...], low: int, high: int) -> int:
    value = _at(raw, path)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise PreregistrationError(f"{_name(path)}: {low}–{high} arası tam sayı ({value!r})")
    return value


def _names(raw: Mapping[str, Any], path: tuple[str, ...]) -> tuple[str, ...]:
    value = _at(raw, path)
    ok = isinstance(value, list) and bool(value)
    if not ok or not all(isinstance(v, str) and v.strip() for v in value):
        raise PreregistrationError(f"{_name(path)}: boş olmayan metin listesi olmalı ({value!r})")
    if len(set(value)) != len(value):
        raise PreregistrationError(f"{_name(path)}: yinelenen öğe ({value!r})")
    return tuple(value)


def _exact(
    raw: Mapping[str, Any], path: tuple[str, ...], expected: Sequence[str]
) -> tuple[str, ...]:
    found = _names(raw, path)
    if found != tuple(expected):
        raise PreregistrationError(f"{_name(path)}: tam olarak {list(expected)} olmalı ({found})")
    return found


def _sha(value: object, where: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise PreregistrationError(f"{where}: 64 haneli sha256 olmalı ({value!r})")
    return value


def _literals(raw: Mapping[str, Any]) -> None:
    for path, expected in _LITERALS.items():
        found = _at(raw, path)
        if type(found) is not type(expected) or found != expected:
            raise PreregistrationError(
                f"{_name(path)}: desteklenen tek değer {expected!r} ({found!r})"
            )


def _feature(raw: Mapping[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    weakness, strength, excluded = (
        _names(raw, ("feature", key)) for key in ("weakness", "strength", "excluded")
    )
    every = [*weakness, *strength, *excluded]
    if len(set(every)) != len(every):
        raise PreregistrationError("feature: weakness, strength, excluded ayrık ve tekil olmalı")
    divisor = _whole(raw, ("feature", "divisor"), 1, 100)
    if divisor != len(weakness) + len(strength):
        raise PreregistrationError(f"feature.divisor: weakness + strength sayısı ({divisor})")
    return weakness, strength, excluded


def _level_scores(raw: Mapping[str, Any]) -> Mapping[str, float]:
    return MappingProxyType({key: _real(raw, ("level_scores", key), 0.0, 1.0) for key in LEVELS})


def _date_limit(raw: Mapping[str, Any]) -> datetime:
    value = raw["stop"]["date_limit"]
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise PreregistrationError(f"stop.date_limit: saat dilimli zaman damgası ({value!r})")
    return value


def _sha256(raw: Mapping[str, Any]) -> Mapping[str, str]:
    found = raw["sha256"]
    expected = FROZEN_FILES | RECORDED_FILES
    if not isinstance(found, Mapping) or set(found) != expected:
        raise PreregistrationError(f"sha256: tam olarak {sorted(expected)} olmalı")
    return MappingProxyType({name: _sha(found[name], f"sha256.{name}") for name in found})


def _verdicts(raw: Mapping[str, Any]) -> Mapping[str, str]:
    found = raw["verdicts"]
    for key in VERDICTS:
        if not isinstance(found[key], str) or not found[key].strip():
            raise PreregistrationError(f"verdicts.{key}: boş olmayan metin olmalı")
    return MappingProxyType({key: str(found[key]) for key in VERDICTS})


def _bounds(raw: Mapping[str, Any]) -> tuple[float, float]:
    lower = _real(raw, ("descriptive_bounds", "lower"), -100.0, -1e-9)
    upper = _real(raw, ("descriptive_bounds", "upper"), 1e-9, 100.0)
    return lower, upper


def _entry_model(raw: Mapping[str, Any]) -> str:
    value = raw["languages"]["entry"]["jev_model"]
    if not isinstance(value, str) or not value.strip():
        raise PreregistrationError(f"languages.entry.jev_model: boş olmayan metin ({value!r})")
    return value


def _validated(raw: Mapping[str, Any]) -> Faz4Preregistration:
    _check_keys(raw)
    _literals(raw)
    weakness, strength, excluded = _feature(raw)
    upper = _real(raw, ("beta", "upper"), 1e-9, 100.0)
    _real(raw, ("beta", "empty"), 0.0, 0.0)  # boş eğitim kümesi: β = 0 ⇒ harman_jev ≡ harman
    _exact(raw, ("beta", "train", "requires"), TRAIN_REQUIRES)
    _exact(raw, ("bootstrap", "order"), BOOTSTRAP_ORDER)
    return Faz4Preregistration(
        tier2_prompt_version=_sha(
            raw["window"]["tier2_prompt_version"], "window.tier2_prompt_version"
        ),
        n_stop=_whole(raw, ("stop", "n_stop"), N_STOP_FLOOR, 1_000_000),
        date_limit=_date_limit(raw),
        evaluation_lag_days=_whole(raw, ("stop", "evaluation_lag_days"), 1, 365),
        weakness=weakness,
        strength=strength,
        excluded=excluded,
        divisor=len(weakness) + len(strength),
        c_min=_real(raw, ("feature", "c_min"), 0.0, 1.0),
        level_scores=_level_scores(raw),
        ridge_lambda=_real(raw, ("beta", "lambda"), 1e-9, 1e6),
        beta_lower=_real(raw, ("beta", "lower"), 0.0, upper - 1e-9),
        beta_upper=upper,
        tol=_real(raw, ("beta", "tol"), 1e-14, 1e-3),
        gap_hours=_whole(raw, ("beta", "train", "gap_hours"), 1, 48),
        comparisons=_exact(raw, ("comparisons",), COMPARISONS),
        gate=raw["gate"],
        descriptive_bounds=_bounds(raw),
        d8_questions=_names(raw, ("d8_questions",)),
        d5_leagues=_names(raw, ("d5_leagues",)),
        resamples=_whole(raw, ("bootstrap", "resamples"), 1, 1_000_000),
        seed=_whole(raw, ("bootstrap", "seed"), 0, 2**63 - 1),
        level=_real(raw, ("bootstrap", "level"), 1e-9, 1 - 1e-9),
        tau=_real(raw, ("tau",), 0.0, 1.0),
        calibration_bins=_whole(raw, ("calibration_bins",), 1, 100),
        closure_kinds=_exact(raw, ("closure_kinds",), CLOSURE_KINDS),
        sealed_languages=_names(raw, ("languages", "sealed")),
        entry_min_n=_whole(raw, ("languages", "entry", "min_n"), 1, 100_000),
        entry_min_accuracy=_real(raw, ("languages", "entry", "min_accuracy"), 1e-9, 1.0),
        entry_jev_model=_entry_model(raw),
        sha256=_sha256(raw),
        counts_printed=_exact(raw, ("counts_printed",), COUNTS_PRINTED),
        verdicts=_verdicts(raw),
    )


def load_preregistration(path: Path = PREREGISTRATION_PATH) -> Faz4Preregistration:
    raw = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)  # noqa: S506
    if not isinstance(raw, Mapping):
        raise PreregistrationError(f"{path}: kök eşlem olmalı")
    return _validated(raw)
