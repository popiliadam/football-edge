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


def test_the_scanned_script_exists_and_is_executable() -> None:
    """`run: ./scripts/check_secrets.sh` ancak dosya çalıştırılabilirse koşar."""
    script = REPO / SCAN_SCRIPT

    assert script.is_file(), f"{SCAN_SCRIPT} yok: iş akışı adımı ilk koşuda düşer"
    assert os.access(script, os.X_OK), f"{SCAN_SCRIPT} çalıştırılabilir değil"
