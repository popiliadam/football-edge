"""`scripts/check_secrets.sh` Netlify tokenını ve site DSN'ini de tanır (H5c).

Tarama geçici bir git deposunda koşturulur (git grep izlenen dosyaları okur). Ad=değer satırları
parçalardan kurulur: kapının kendi taraması bu test dosyasını eşlemesin.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts/check_secrets.sh"


def _scan(tmp_path: Path, line: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "scripts").mkdir()
    shutil.copy(SCRIPT, tmp_path / "scripts/check_secrets.sh")
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / "ayar.txt").write_text(line + "\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    return subprocess.run(
        ["bash", "scripts/check_secrets.sh"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "line",
    [
        "NETLIFY_AUTH" + "_TOKEN=nfp_" + "a1b2c3d4e5f6g7h8i9j0",
        "SITE_DATABASE" + "_URL=postgresql://site_reader:" + "gizli-parola-123@h:5432/postgres",
    ],
    ids=["netlify", "site-dsn"],
)
def test_a_filled_site_or_netlify_secret_turns_the_scan_red(tmp_path: Path, line: str) -> None:
    result = _scan(tmp_path, line)

    assert result.returncode == 1, result.stdout
    assert "HATA: izlenen dosyada dolu secret ataması var" in result.stdout


def test_an_empty_assignment_stays_clean(tmp_path: Path) -> None:
    result = _scan(tmp_path, "NETLIFY_AUTH" + "_TOKEN=")

    assert result.returncode == 0, result.stdout
