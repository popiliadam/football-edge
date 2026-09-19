"""CI kapının secret adımını da koşmalı: depo PUBLIC, kaçan secret anında halka açılır.

`scripts/check_secrets.sh` yalnız `./verify.sh` içinde, yalnız YEREL koşuyordu (G6):
kapıyı elle koşmayan bir push taramadan geçmeden iner. Tarama ucuzdur, credential
istemez ve checkout'tan sonra her runner'da çalışır — CI'da koşmaması bir tercih değil,
bir boşluktu (HANDOFF §3.4/15).

Bu dosya iş akışlarının İÇERİĞİNİ okur, koşmaz: runner'da gerçekten yeşil verdiği
ölçülmedi (workflow'lar hâlâ hiç koşmadı — HANDOFF §3.2).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from football_edge import collect

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = (
    REPO / ".github/workflows/snapshot.yml",
    REPO / ".github/workflows/seal.yml",
)
SCAN_SCRIPT = "scripts/check_secrets.sh"


def _steps(path: Path) -> list[dict[str, Any]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    (job,) = document["jobs"].values()
    return list(job["steps"])


def _index_of(steps: list[dict[str, Any]], needle: str, key: str = "run") -> int | None:
    for index, step in enumerate(steps):
        if needle in str(step.get(key, "")):
            return index
    return None


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_workflow_scans_for_secrets_before_the_paid_run(path: Path) -> None:
    """Tarama checkout'tan SONRA, toplayıcıdan ÖNCE koşmalı."""
    steps = _steps(path)
    checkout = _index_of(steps, "actions/checkout", key="uses")
    scan = _index_of(steps, SCAN_SCRIPT)
    collector = _index_of(steps, "football_edge.collect")

    assert scan is not None, f"{path.name} secret taramasını hiç koşmuyor"
    assert checkout is not None, "checkout adımı yok: git tabanlı tarama koşamaz"
    assert collector is not None, "iş akışı toplayıcıyı çağırmıyor — test kurgusu bayatlamış"
    assert checkout < scan, f"{path.name}: tarama checkout'tan önce, depo henüz yok"
    assert scan < collector, f"{path.name}: tarama ücretli/secret'lı adımdan sonra koşuyor"


# ── I4: seal.yml, toplayıcının verdiği her kodu ADIYLA karşılamalı ──────────
# Adı olmayan bir kod `*)` arm'ına düşer ve "beklenmedik kodla düştü" der: operatör
# kalıcı kaybolmuş bir kapanış fiyatını, bilinmeyen bir arızadan ayırt edemez.

SEAL = REPO / ".github/workflows/seal.yml"


def _seal_run_body() -> str:
    step = next(
        step for step in _steps(SEAL) if "football_edge.collect seal" in str(step.get("run", ""))
    )
    return str(step["run"])


@pytest.mark.parametrize(
    ("code", "name"),
    [
        (collect.EXIT_QUOTA_EXHAUSTED, "kredi"),
        (collect.EXIT_LEAGUE_FAILED, "lig"),
        (collect.EXIT_MIRROR_FAILED, "ayna"),
        (collect.EXIT_MISSED_SEAL, "mühür"),
    ],
)
def test_seal_workflow_names_every_exit_code_the_collector_can_return(code: int, name: str) -> None:
    body = _seal_run_body()
    arm = next((line for line in body.splitlines() if line.strip().startswith(f"{code})")), None)

    assert arm is not None, (
        f"seal.yml exit {code} için case arm'ı taşımıyor: '*)' dalına düşer ve "
        "operatör arızayı adıyla göremez"
    )
    assert name in arm, f"exit {code} arm'ı arızayı adlandırmıyor ({name!r} geçmiyor): {arm!r}"


def test_the_scanned_script_exists_and_is_executable() -> None:
    """`run: ./scripts/check_secrets.sh` ancak dosya çalıştırılabilirse koşar."""
    script = REPO / SCAN_SCRIPT

    assert script.is_file(), f"{SCAN_SCRIPT} yok: iş akışı adımı ilk koşuda düşer"
    assert os.access(script, os.X_OK), f"{SCAN_SCRIPT} çalıştırılabilir değil"
