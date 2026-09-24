"""`scripts/check_secrets.sh` Netlify tokenını ve site DSN'ini de tanır (H5c).

Tarama geçici bir git deposunda koşturulur (git grep izlenen dosyaları okur). Ad=değer satırları
ve token parçalardan kurulur: kapının kendi taraması bu test dosyasını eşlemesin.

Ad=değer taraması YAML/JSON değerini, `--auth` bayrağını, küçük harfli adı ve Markdown'ı görmez
(inceleme I4); Netlify tokenı bu yüzden biçimiyle (`nfp_` + 36 alfasayısal) de aranır.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts/check_secrets.sh"
NAME = "NETLIFY_AUTH" + "_TOKEN"
TOKEN = "nfp" + "_" + "Q7xK2m" * 6  # 36 alfasayısal: kişisel erişim tokenının biçimi


def _scan(tmp_path: Path, line: str, name: str = "ayar.txt") -> subprocess.CompletedProcess[str]:
    (tmp_path / "scripts").mkdir()
    shutil.copy(SCRIPT, tmp_path / "scripts/check_secrets.sh")
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / name).write_text(line + "\n", encoding="utf-8")
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
