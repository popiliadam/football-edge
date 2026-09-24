"""`scripts/check_secrets.sh` Netlify tokenını ve site DSN'ini de tanır (H5c).

Tarama geçici bir git deposunda koşturulur (git grep izlenen dosyaları okur). Ad=değer satırları
ve token parçalardan kurulur: kapının kendi taraması bu test dosyasını eşlemesin.

Ad=değer taraması YAML/JSON değerini, `--auth` bayrağını, küçük harfli adı ve Markdown'ı görmez
(inceleme I4); Netlify tokenı bu yüzden biçimiyle (`nfp_` + 36 alfasayısal) de aranır.

Taramalar eşleşen satırı değil yalnız `dosya:satır`ı basar (yeniden inceleme N3): satır secret'ın
kendisidir ve CI logu public. Tarama yedi workflow'un ilk adımıdır; bulursa kırmızı kalmalıdır.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.workflow_helpers import _steps

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts/check_secrets.sh"
NAME = "NETLIFY_AUTH" + "_TOKEN"
TOKEN = "nfp" + "_" + "Q7xK2m" * 6  # 36 alfasayısal: kişisel erişim tokenının biçimi


def _run(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/check_secrets.sh"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        # Üst dizinlerdeki bir depo bulunmasın: git'siz vaka gerçekten git'sizdir.
        env={**os.environ, "GIT_CEILING_DIRECTORIES": str(tmp_path.parent)},
    )


def _scan(tmp_path: Path, line: str, name: str = "ayar.txt") -> subprocess.CompletedProcess[str]:
    (tmp_path / "scripts").mkdir()
    shutil.copy(SCRIPT, tmp_path / "scripts/check_secrets.sh")
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / name).write_text(line + "\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    return _run(tmp_path)


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
    assert "ayar.txt:1\n" in result.stdout, "yer basılır"
    assert line.split("=", 1)[1] not in result.stdout + result.stderr, "değer loga düşmez"


def test_an_empty_assignment_stays_clean(tmp_path: Path) -> None:
    result = _scan(tmp_path, "NETLIFY_AUTH" + "_TOKEN=")

    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize(
    ("name", "line"),
    [
        ("site.yml", f"          {NAME}: {TOKEN}"),
        ("ayar.json", f'{{"{NAME}": "{TOKEN}"}}'),
        ("yayin.sh", f"netlify deploy --prod --auth {TOKEN}"),
        ("ayar.txt", TOKEN),
        ("ayar.txt", f"{NAME.lower()}={TOKEN}"),
        ("NOTLAR.md", f"Yayın tokenı: `{TOKEN}`"),
    ],
    ids=["yaml", "json", "cli-auth", "bare", "lowercase-name", "markdown"],
)
def test_a_netlify_token_is_red_in_any_form_and_any_file(
    tmp_path: Path, name: str, line: str
) -> None:
    result = _scan(tmp_path, line, name)

    assert result.returncode == 1, result.stdout
    assert "HATA: izlenen dosyada Netlify erişim tokenı var" in result.stdout
    assert f"{name}:1\n" in result.stdout, "yer basılır"
    assert TOKEN not in result.stdout + result.stderr, "token loga düşmez"


def test_a_scan_that_cannot_run_is_red_by_name(tmp_path: Path) -> None:
    """`pipefail` olmadan boru `cut`un 0'ını dönerdi: düşen git "eşleşme var" gibi okunurdu —
    ya da (0 → temiz sayan bir düzenlemeyle) sessizce yeşil. İki tarama da adıyla kırmızı."""
    (tmp_path / "scripts").mkdir()
    shutil.copy(SCRIPT, tmp_path / "scripts/check_secrets.sh")

    result = _run(tmp_path)

    assert result.returncode == 1, result.stdout
    assert "HATA: git grep taraması koşamadı" in result.stdout
    assert "HATA: Netlify token taraması koşamadı" in result.stdout
    assert "dolu secret ataması var" not in result.stdout


def test_every_workflow_runs_the_scan_bare_so_a_finding_stops_it() -> None:
    """Tarama zamanlanmış workflow'ların (seal, snapshot, …) erken adımıdır: `if`,
    `continue-on-error`, `shell` ya da `||` olmadan — bulgu adımı ve koşuyu kırmızı yapar."""
    scans = [
        step
        for path in sorted((REPO / ".github/workflows").glob("*.y*ml"))
        for step in _steps(path)
        if "check_secrets.sh" in str(step.get("run", ""))
    ]

    assert len(scans) >= 7, scans
    assert all(
        step == {"name": "Secret taraması", "run": "./scripts/check_secrets.sh"} for step in scans
    )
