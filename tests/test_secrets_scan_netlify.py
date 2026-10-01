"""`scripts/check_secrets.sh` Netlify tokenını ve site DSN'ini de tanır (H5c).

Tarama geçici bir git deposunda koşturulur (git grep izlenen dosyaları okur). Ad=değer satırları
ve token parçalardan kurulur: kapının kendi taraması bu test dosyasını eşlemesin.

Ad=değer taraması YAML/JSON değerini, `--auth` bayrağını, küçük harfli adı ve Markdown'ı görmez
(inceleme I4); Netlify tokenı bu yüzden biçimiyle (`nfp_` + 36 alfasayısal) de aranır.

Taramalar eşleşen satırı değil yalnız `dosya:satır`ı basar (yeniden inceleme N3): satır secret'ın
kendisidir ve CI logu public. Tarama dokuz workflow'un ilk adımlarındandır; bulursa kırmızı
kalmalıdır.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.workflow_helpers import _index_of, _steps

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

    assert len(scans) >= 9, scans
    assert all(
        step == {"name": "Secret taraması", "run": "./scripts/check_secrets.sh"} for step in scans
    )


def _strings(node: Any) -> list[str]:
    """YAML ağacındaki bütün dize değerleri. Yorumlar ayrıştırmada düşer: yalnız yorumda geçen
    `secrets.` (ör. `ci.yml`in kapı adımı listesi) secret taşımak sayılmaz."""
    if isinstance(node, dict):
        return [text for value in node.values() for text in _strings(value)]
    if isinstance(node, list):
        return [text for value in node for text in _strings(value)]
    return [node] if isinstance(node, str) else []


def _reads_a_secret(node: Any) -> bool:
    """`${{ … secrets … }}` ifadesi var mı — çıplak kelime değil, ifade aranır. Bağlamın her
    biçimi sayılır: noktalı (`secrets.X`), indeksli (`secrets['X']`) ve bütün bağlam
    (`toJSON(secrets)`, bütün secret'lar)."""
    return any(
        re.search(r"\bsecrets\b", expression)
        for text in _strings(node)
        for expression in re.findall(r"\$\{\{(.*?)\}\}", text, flags=re.S)
    )


def _may_write_contents(document: dict[str, Any]) -> bool:
    """Workflow ya da herhangi bir iş `contents: write` (ya da `write-all`) taşıyor mu."""
    blocks = [document.get("permissions")] + [
        job.get("permissions") for job in document["jobs"].values()
    ]
    return any(
        block == "write-all" or (isinstance(block, dict) and block.get("contents") == "write")
        for block in blocks
    )


def test_every_workflow_that_reads_a_secret_or_writes_the_repo_runs_the_scan() -> None:
    """19b: sayım tek başına yetmez — yeni bir secret'lı workflow taramasız eklenirse sayı yine
    tutabilir. Kural ad listesiyle değil ÖZELLİKLE kurulur: secret okuyan ya da depoya yazma
    yetkisi alan her workflow taramayı koşar (depo PUBLIC; kaçan secret geri alınamaz).

    `ci.yml` kuralın dışında kalır çünkü özelliği taşımaz: secret okumaz
    (`test_ci_reads_no_repository_secret_at_all`) ve salt okunurdur; ayrıca kapısı taramayı
    `verify.sh`in `secrets` adımı olarak zaten koşar."""
    covered = {}
    for path in sorted((REPO / ".github/workflows").glob("*.y*ml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if _reads_a_secret(document) or _may_write_contents(document):
            covered[path.name] = any(
                "check_secrets.sh" in str(step.get("run", "")) for step in _steps(path)
            )

    assert covered, "hiçbir workflow secret okumuyor ya da yazmıyor — test kurgusu bayatlamış"
    missing = [name for name, scans in covered.items() if not scans]
    assert missing == [], f"secret okuyan ya da yazan ama taramayı koşmayan workflow: {missing}"


SCAN = "check_secrets.sh"
GIT_PUSH = re.compile(r"\bgit\b(?:\s+-c\s+\S+)*\s+push\b")


def _exposes(step: dict[str, Any]) -> bool:
    """Adım secret okuyor ya da depoya push'luyor mu (`git -c … push` de sayılır)."""
    return _reads_a_secret(step) or GIT_PUSH.search(str(step.get("run", ""))) is not None


def _needs(job: dict[str, Any]) -> set[str]:
    needs = job.get("needs", [])
    return {needs} if isinstance(needs, str) else set(needs)


def test_the_scan_runs_before_the_first_secret_or_push_of_its_job() -> None:
    """19b(1) SIRASI: tarama, taşıyan her işte secret okuyan ilk adımdan ve ilk `git push`tan
    ÖNCE koşar — sonraya taşınan tarama secret'ı ya da main'e yazmayı korumaz (son inceleme
    satır 2: `full-scan`de secret'lı adımdan, `sources-audit`te push adımından sonraya taşımak
    yeşil kalıyordu). Taramasız ama secret okuyan iş taramalı bir işe `needs` ile bağlıdır
    (`site.yml` `deploy` → `build`).

    Ölçmediği: iş düzeyi `env:`deki secret ve `if: always()`/`!cancelled()` adımlarının
    kırmızı taramadan sonra yine koşması (DEFERRED 19b kalanı)."""
    checked, broken = [], []
    for path in sorted((REPO / ".github/workflows").glob("*.y*ml")):
        jobs = yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]
        scanning = {name for name, job in jobs.items() if _index_of(job["steps"], SCAN) is not None}
        for name, job in jobs.items():
            steps = job["steps"]
            exposed = [index for index, step in enumerate(steps) if _exposes(step)]
            if not exposed:
                continue
            where = f"{path.name}:{name}"
            checked.append(where)
            scan = _index_of(steps, SCAN)
            if scan is None and not _needs(job) & scanning:
                broken.append(f"{where}: tarama yok, taramalı işe `needs` da yok")
            elif scan is not None and scan > exposed[0]:
                broken.append(f"{where}: tarama adım {scan}, ilk secret/push adım {exposed[0]}")

    assert checked, "hiçbir iş secret okumuyor ya da push'lamıyor — test kurgusu bayatlamış"
    assert broken == [], broken
