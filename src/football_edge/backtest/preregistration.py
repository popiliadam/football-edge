"""Holdout ön kaydı (Faz 3 tasarımı §8.1; R130, R135, R139): `config/<faz>_preregistration.yaml`.

Açılıştan ÖNCE commit'lenir; `final_eval` dosyanın commit'lenmiş hâliyle çalışma ağacındakinin aynı
olduğunu, ağacın temiz olduğunu ve üç özetin (model yapılandırması, kilit, katalog) tuttuğunu
açmadan sınar. Açılışın `purpose`u ön kaydın sha256'sını taşır. Faz bir parametredir (16d);
gerçek açılış yalnız kanonik yollarla yapılır (16b), prova serbesttir.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from football_edge.backtest.model_config import file_sha256

# Faz → ön kaydın karşılaştırmaları. Yeni faz buraya satır ekler; ön kayıt dosyası birebir uyar.
PHASES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {"faz3": ("C1", "C2", "C3", "C4", "C5", "C6")}
)
_FIELDS = frozenset(
    {
        "phase",
        "model_config_sha256",
        "lock_sha256",
        "catalog_sha256",
        "comparisons",
        "tau",
        "sensitivity",
        "resamples",
    }
)


class PreflightError(RuntimeError):
    """Açılış öncesi denetimlerden biri tutmadı: holdout AÇILMAZ."""


@dataclass(frozen=True)
class Preregistration:
    phase: str
    model_config_sha256: str
    lock_sha256: str
    catalog_sha256: str
    comparisons: tuple[str, ...]
    tau: float
    sensitivity: tuple[float, ...]
    resamples: int


@dataclass(frozen=True)
class CanonicalPaths:
    """Gerçek açılışın kabul ettiği TEK yollar (16b): başka commit'li dosya ön kayıt değildir."""

    prereg: Path
    model: Path
    lock: Path
    catalog: Path


@dataclass(frozen=True)
class Git:
    """Git'e yalnız okuma soruları; testlerde sahte fonksiyonlarla kurulur."""

    head: Callable[[], str]
    clean: Callable[[], bool]
    committed: Callable[[Path], bool]  # dosya izleniyor ve HEAD'deki hâliyle aynı


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(("git", *args), capture_output=True, text=True, check=False)


def real_git() -> Git:
    return Git(
        head=lambda: _git("rev-parse", "HEAD").stdout.strip(),
        clean=lambda: _git("status", "--porcelain").stdout.strip() == "",
        committed=lambda path: (
            _git("ls-files", "--error-unmatch", str(path)).returncode == 0
            and _git("diff", "--quiet", "HEAD", "--", str(path)).returncode == 0
        ),
    )


def load_preregistration(path: Path, *, phase: str) -> Preregistration:
    if phase not in PHASES:
        raise PreflightError(f"bilinmeyen faz {phase!r} (bilinen: {', '.join(sorted(PHASES))})")
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise PreflightError(f"{path}: okunamadı: {error}") from error
    if not isinstance(raw, dict) or set(raw) != _FIELDS:
        raise PreflightError(f"{path}: alanlar {sorted(_FIELDS)} olmalı")
    if raw["phase"] != phase or tuple(raw["comparisons"]) != PHASES[phase]:
        raise PreflightError(f"{path}: faz {phase!r} ve karşılaştırmalar {PHASES[phase]} olmalı")
    return Preregistration(
        phase=str(raw["phase"]),
        model_config_sha256=str(raw["model_config_sha256"]),
        lock_sha256=str(raw["lock_sha256"]),
        catalog_sha256=str(raw["catalog_sha256"]),
        comparisons=tuple(str(item) for item in raw["comparisons"]),
        tau=float(raw["tau"]),
        sensitivity=tuple(float(value) for value in raw["sensitivity"]),
        resamples=int(raw["resamples"]),
    )


def _check_canonical(
    canonical: CanonicalPaths, *, prereg: Path, model: Path, lock: Path, catalog: Path
) -> None:
    # `resolve`: `./config/x.yaml` ve mutlak yol aynı dosyadır; başka bir dosya değildir.
    for name, given, expected in (
        ("ön kayıt", prereg, canonical.prereg),
        ("model yapılandırması", model, canonical.model),
        ("kilit", lock, canonical.lock),
        ("katalog", catalog, canonical.catalog),
    ):
        if given.resolve() != expected.resolve():
            raise PreflightError(f"{name} kanonik yolda değil: {given} (beklenen {expected})")


def preflight(
    *,
    prereg_path: Path,
    model_path: Path,
    lock_path: Path,
    catalog_path: Path,
    git: Git,
    phase: str,
    canonical: CanonicalPaths | None,
) -> Preregistration:
    """Açılış öncesi bütün denetimler; biri tutmazsa `PreflightError` (hiçbir şey açılmaz).

    `canonical` gerçek açılışta verilir; prova `None` geçer (her yolla koşabilir, açılış yok).
    """
    if canonical is not None:
        _check_canonical(
            canonical, prereg=prereg_path, model=model_path, lock=lock_path, catalog=catalog_path
        )
    if not git.clean():
        raise PreflightError("çalışma ağacı temiz değil")
    if not git.committed(prereg_path):
        raise PreflightError(f"{prereg_path}: commit'lenmemiş ya da HEAD'dekinden farklı")
    prereg = load_preregistration(prereg_path, phase=phase)
    for name, expected, path in (
        ("model yapılandırması", prereg.model_config_sha256, model_path),
        ("kilit", prereg.lock_sha256, lock_path),
        ("katalog", prereg.catalog_sha256, catalog_path),
    ):
        if file_sha256(path) != expected:
            raise PreflightError(f"{name} ön kayıttaki özetle uyuşmuyor: {path}")
    return prereg
