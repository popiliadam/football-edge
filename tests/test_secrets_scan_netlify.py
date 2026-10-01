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
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.workflow_helpers import _index_of, _logical_lines, _steps

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
    `continue-on-error`, `shell` ya da `||` olmadan — bulgu adımı ve koşuyu kırmızı yapar.
    Tek izinli ek `id: secret_scan`: taramadan sonra `always()`/`!cancelled()` ile koşan secret'lı
    ya da push'lu adım ona bağlanır (19b kalanı)."""
    scans = [
        step
        for path in sorted((REPO / ".github/workflows").glob("*.y*ml"))
        for step in _steps(path)
        if "check_secrets.sh" in str(step.get("run", ""))
    ]

    assert len(scans) >= 9, scans
    bare = {"name": "Secret taraması", "run": "./scripts/check_secrets.sh"}
    assert all(step in (bare, {**bare, "id": "secret_scan"}) for step in scans), scans


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
    (`toJSON(secrets)`, bütün secret'lar).

    Harf duyarsız (21k): GitHub'ın ifade ayrıştırıcısı bağlam ve fonksiyon adlarını
    `StringComparer.OrdinalIgnoreCase` sözlüklerinde arar (actions/runner
    `ExpressionParser.cs`: `ExtensionNamedValues`, `ExtensionFunctions`); `Secrets.X` ve
    `SECRETS['X']` aynı secret'ı okur.

    Yalnız `secrets` BAĞLAMI sayılır: `${{ github.token }}` ile `${{ secrets.GITHUB_TOKEN }}` aynı
    iş token'ıdır, ama ikincisi bu bekçide secret sayılır (M-4). Alarm adımlarının taramaya
    bağlanmaması `github.token` yazımına dayanır. `secrets.GITHUB_TOKEN`a geçen alarm adımı
    bağlama bekçisinde kırmızı verir; çare `github.token`a dönmektir, alarmı taramaya bağlamak
    DEĞİL — kırmızı tarama tam da alarmın açılması gereken turdur."""
    return any(
        re.search(r"\bsecrets\b", expression, flags=re.I)
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
# Değer alan genel git seçenekleri: alt komut değerden SONRA gelir (`git -C alt push`,
# `git -c "user.name=fe bot" push`). `--git-dir=x` gibi tek parçalı biçim tek token'dır.
GIT_VALUE_OPTIONS = frozenset(
    {
        "-c",
        "-C",
        "--git-dir",
        "--work-tree",
        "--namespace",
        "--super-prefix",
        "--config-env",
        # git.c `handle_options`: `--attr-source <ağaç>` değeri sonraki argv'den alır (N-12).
        "--attr-source",
    }
)
# Durum fonksiyonları. GitHub, `if:`te HERHANGİ biri geçiyorsa örtük `success() &&`i eklemez
# ("A default status check of success() is applied unless you include one of these functions"):
# `!success()` ve `success() || …` de kırmızı bir adımdan sonra koşabilir. Bağlam ve fonksiyon
# adları harf duyarsızdır (`_reads_a_secret`in notu) — `Always()` de sayılır.
STATUS_FUNCTION = re.compile(r"\b(?:success|always|cancelled|failure)\s*\(\s*\)", re.I)
# BASE'in push regex'i (oturum 10): ham metinde `git [-c x]… push`; tırnaklı dizeyi de görür
# (`bash -c 'git push'`, `eval`, `ssh host '… git push'`). Kabuk okumasıyla BİRLEŞİMİ alınır.
BASE_GIT_PUSH = re.compile(r"\bgit\b(?:\s+-c\s+\S+)*\s+push\b")
# Kaba kural (N-7): aynı mantıksal satırda `git` ve `push` sözcükleri, sırasız. Kabuk okumasının
# çözemediği biçimleri (`"$(git -c "a b" push)"` iç içe tırnağı, `$'push'`, takma ad, `$alt`,
# `xargs`) kırmızı verir; bedeli `git config push.default` gibi gürültüdür — kabul.
GIT_WORD = re.compile(r"\bgit\b")
PUSH_WORD = re.compile(r"\bpush\b")


def _git_subcommands(line: str) -> list[str]:
    """Satırdaki her `git` çağrısının alt komutu. Kabuk sözcüklerine bölünür (tırnaklı değer
    tek sözcük) ve genel seçenekler atlanır. Boşluk taşıyan sözcük (tırnaklı komut dizesi:
    `bash -c '…'`, `eval '…'`, `ssh host '…'`) BÜTÜNÜYLE, `$(…)`/`` `…` `` içindeki komut da
    AYRICA okunur — ikisi bağımsız (N-1b). Hiçbir metin atılmaz: `#` yorum sayılmaz
    (`${#a[@]}`, `https://x/a#b`, `\\` ile süren yorum satırı — N-1a, N-3). Kapanmamış
    tırnakla satır bölünemezse kaba okumaya düşer (`git` … `push` = push): yanlış pozitif
    gürültülüdür, kaçırılan push sessiz."""
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return ["push"] if re.search(r"\bgit\b.*\bpush\b", line) else []
    found = []
    for index, token in enumerate(tokens):
        if "$(" in token or "`" in token:
            inner = re.split(r"\$\(|`", token, maxsplit=1)[1]
            # Kapanan ters tırnak sözcüğe yapışır (`push``): boşluğa çevrilir.
            found.extend(_git_subcommands(inner.replace("`", " ")))
        if re.search(r"\s", token) and token != line:
            found.extend(_git_subcommands(token))
        if token.rsplit("/", 1)[-1] != "git":
            continue
        cursor = index + 1
        while cursor < len(tokens) and tokens[cursor].startswith("-"):
            cursor += 2 if tokens[cursor] in GIT_VALUE_OPTIONS else 1
        if cursor < len(tokens):
            found.append(tokens[cursor])
    return found


def _pushes(step: dict[str, Any]) -> bool:
    """Adımın betiği `git … push` koşuyor mu. Bekçi eşleştirmeden ÖNCE hiçbir metni atmaz
    (controller kararı, düzeltme turu 2): BASE regex'i HAM betiğe uygulanır — yorum dâhil,
    BASE'in kendisi gibi — ve iki katmanla birleşir: mantıksal satırda sırasız `git`+`push`
    sözcükleri (kaba kural, N-7) ve kabuk okuması (`\\` devamı birleşik). Katmanlar algı
    EKLER, hiçbir zaman çıkarmaz. Gürültü kırmızıdır ve kabul; sessizlik değil."""
    run = str(step.get("run", ""))
    return BASE_GIT_PUSH.search(run) is not None or any(
        (GIT_WORD.search(line) and PUSH_WORD.search(line)) or "push" in _git_subcommands(line)
        for line in _logical_lines(run)
    )


def _exposes(step: dict[str, Any]) -> bool:
    """Adım secret okuyor ya da depoya push'luyor mu."""
    return _reads_a_secret(step) or _pushes(step)


def _job_steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    """İşin adımları; yeniden kullanılabilir workflow çağrısında (`uses:`) adım yoktur."""
    return list(job.get("steps") or [])


def _job_level_secret(job: dict[str, Any]) -> bool:
    """İş düzeyinde secret: `env:` (taramadan ÖNCEKİ adımlar dâhil her adıma açılır),
    `container`/`services` kimlik bilgisi ve yeniden kullanılabilir workflow çağrısının
    `secrets:`i — `secrets: inherit` ifade taşımaz, anahtarın kendisi sayılır."""
    return "secrets" in job or _reads_a_secret({k: v for k, v in job.items() if k != "steps"})


def _needs(job: dict[str, Any]) -> set[str]:
    needs = job.get("needs", [])
    return {needs} if isinstance(needs, str) else set(needs)


def _conjuncts(condition: str) -> list[str]:
    """`if:` ifadesinin üst düzey `&&` terimleri (boşluk sadeleşmiş). Üst düzeyde `||` varsa
    boş liste: o zaman hiçbir terim tek başına koşulu bağlamaz."""
    text = condition.strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2]
    parts, depth, start, index = [], 0, 0, 0
    while index < len(text):
        if text[index] in "()":
            depth += 1 if text[index] == "(" else -1
        elif depth == 0 and text.startswith("||", index):
            return []
        elif depth == 0 and text.startswith("&&", index):
            parts.append(text[start:index])
            start = index + 2
        index += 1
    parts.append(text[start:])
    return [" ".join(part.split()) for part in parts]


def _bound(condition: str, term: str) -> bool:
    """`term` koşulun üst düzey bir `&&` terimi mi. Harf duyarsız: GitHub dizeleri ve bağlam
    adlarını harf duyarsız karşılaştırır."""
    return term.lower() in [part.lower() for part in _conjuncts(condition)]


def _overrides_success(condition: str) -> bool:
    """Koşul örtük `success()`i eziyor mu: bir durum fonksiyonu geçiyor ve bu, üst düzey tek
    `success()` terimi değil. `success() && x` ezmez; `!success()`, `success() || x`,
    `always()`, `!cancelled()`, `failure()` ezer (M-1)."""
    found = STATUS_FUNCTION.findall(condition)
    if not found:
        return False
    plain = [" ".join(part.split()).lower() for part in _conjuncts(condition)]
    return not (len(found) == 1 and "success()" in plain)


def _waits_for(job: dict[str, Any], need: str) -> bool:
    """İş, `need` başarısız olunca atlanıyor mu: `if:`i örtük `success()`i ezmiyorsa evet
    (başarısız ya da atlanmış `needs` işi atlatır); eziyorsa ancak
    `needs.<need>.result == 'success'` üst düzey bir terimse."""
    condition = str(job.get("if", ""))
    return not _overrides_success(condition) or _bound(
        condition, f"needs.{need}.result == 'success'"
    )


def _guarded_jobs(jobs: dict[str, dict[str, Any]]) -> set[str]:
    """Kırmızı taramada secret'a ulaşamayan işler: taramayı kendisi koşan iş (tarama çıplak,
    bulguda iş düşer) ve böyle bir işin başarısını DOĞRUDAN ya da zincirle bekleyen iş
    (`notify` → `deploy` → `build`)."""
    guarded = {name for name, job in jobs.items() if _index_of(_job_steps(job), SCAN) is not None}
    while True:
        joined = {
            name
            for name, job in jobs.items()
            if name not in guarded
            and any(need in guarded and _waits_for(job, need) for need in _needs(job))
        }
        if not joined:
            return guarded
        guarded = guarded | joined


def _workflows() -> dict[str, dict[str, Any]]:
    return {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted((REPO / ".github/workflows").glob("*.y*ml"))
    }


def _order_violations(workflows: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    """(denetlenen işler, ihlaller). Secret okuyan ya da push'layan her iş: taramayı ilk maruz
    adımdan ÖNCE koşar ya da taramalı bir işin başarısını bekler. İş düzeyi secret taramalı
    işte her zaman ihlaldir — taramadan önceki adımlara da açılır."""
    checked, broken = [], []
    for file, document in workflows.items():
        jobs = document["jobs"]
        guarded = _guarded_jobs(jobs)
        for name, job in jobs.items():
            steps = _job_steps(job)
            exposed = [index for index, step in enumerate(steps) if _exposes(step)]
            job_level = _job_level_secret(job)
            if not exposed and not job_level:
                continue
            where = f"{file}:{name}"
            checked.append(where)
            scan = _index_of(steps, SCAN)
            if scan is None and name not in guarded:
                broken.append(f"{where}: tarama yok, taramalı bir işin başarısını da beklemiyor")
            elif scan is not None and job_level:
                broken.append(f"{where}: iş düzeyi secret taramadan önceki adımlara da açılır")
            elif scan is not None and scan > exposed[0]:
                broken.append(f"{where}: tarama adım {scan}, ilk secret/push adım {exposed[0]}")
    return checked, broken


def _unbound_after_scan(workflows: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    """(denetlenen adımlar, ihlaller). Taramayı taşıyan işte taramadan SONRA gelen ve `if:`i
    örtük `success()`i ezen (`always()`, `!cancelled()`, `failure()`, `!success()`) her adım,
    secret okuyorsa
    (iş düzeyi `env:` dâhil) ya da push'luyorsa `steps.<tarama id>.outcome == 'success'`
    terimini üst düzey `&&` ile taşır. `outcome`: `continue-on-error` uygulanmadan önceki sonuç."""
    checked, broken = [], []
    for file, document in workflows.items():
        for name, job in document["jobs"].items():
            steps = _job_steps(job)
            scan = _index_of(steps, SCAN)
            if scan is None:
                continue
            scan_id = steps[scan].get("id")
            term = f"steps.{scan_id or '<id>'}.outcome == 'success'"
            job_level = _job_level_secret(job)
            for index, step in enumerate(steps[scan + 1 :], start=scan + 1):
                condition = str(step.get("if", ""))
                if not _overrides_success(condition) or not (job_level or _exposes(step)):
                    continue
                where = f"{file}:{name} adım {index} ({step.get('name', '?')})"
                checked.append(where)
                if scan_id is None or not _bound(condition, term):
                    broken.append(
                        f"{where}: `{condition}` kırmızı taramadan sonra da koşar — secret ya da "
                        f"push'luysa taramaya `id` ver ve `{term}` ile bağla. Adım bir ALARMSA "
                        "bağlama (kırmızı taramada açılmalı): `secrets.GITHUB_TOKEN` yerine "
                        "`github.token` yaz, metindeki `git push`u yeniden ifade et (N-5)"
                    )
    return checked, broken


def test_the_scan_runs_before_the_first_secret_or_push_of_its_job() -> None:
    """19b(1) SIRASI: tarama, taşıyan her işte secret okuyan ilk adımdan ve ilk `git push`tan
    ÖNCE koşar — sonraya taşınan tarama secret'ı ya da main'e yazmayı korumaz (son inceleme
    satır 2). Taramasız ama secret okuyan iş taramalı bir işin başarısını bekler (`site.yml`
    `deploy` → `build`); iş düzeyi `if: always()` taşıyan iş beklemiş sayılmaz (21k).

    Ölçmediği: betiğin dışından gelen push (`"$GIT" push`, `gh api`, üçüncü taraf eylem),
    `run:` dışındaki secret kullanımı yalnız `${{ }}` ifadesiyle görülür; `if:`e secret
    GitHub'ın kendisi tarafından yasaktır."""
    checked, broken = _order_violations(_workflows())

    assert checked, "hiçbir iş secret okumuyor ya da push'lamıyor — test kurgusu bayatlamış"
    assert broken == [], broken


def test_after_a_red_scan_no_step_that_reads_a_secret_or_pushes_runs() -> None:
    """19b kalanı (son inceleme F1): sıra tek başına yetmez — `always()`/`!cancelled()`/`failure()`
    koşullu adım kırmızı taramadan SONRA da koşar. Bugün iki tane: seal `Bekçi` (`ODDS_API_KEY`)
    ve sources-audit `Tazelenen tarihleri commit'le` (`git push`). İkisi de taramanın başarısına
    bağlı; yeşil turda terim doğrudur ve davranış değişmez. Secret okumayan adımlar (alarm,
    `Mühür turunun sonucunu yansıt`, robots ölçümü) bağlanmaz: kırmızı turu görünür kılarlar."""
    checked, broken = _unbound_after_scan(_workflows())

    assert checked, "taramadan sonra koşulu örtük `success()`i ezen maruz adım yok — kurgu bayat"
    assert broken == [], broken


# ── Bekçilerin kendisi: sentetik workflow'lar ─────────────────────────────────────────────
# Gerçek dokuz workflow bugün temiz; bekçinin KAÇIŞ biçimlerini görüp görmediği ancak sentetik
# girdiyle ölçülür (DEFERRED 21k: eski bekçi bu biçimlerin hepsinde yeşil kalıyordu).

SCAN_STEP = {"name": "Secret taraması", "id": "secret_scan", "run": "./scripts/check_secrets.sh"}
SECRET_STEP = {"env": {"PAT": "${{ secrets.PAT }}"}, "run": "./yayinla"}
BOUND = "steps.secret_scan.outcome == 'success'"


def _one(*steps: dict[str, Any], **keys: Any) -> dict[str, Any]:
    """Tek işli sentetik workflow."""
    return {"sentetik.yml": {"jobs": {"is": {**keys, "steps": list(steps)}}}}


def _chain(**jobs: dict[str, Any]) -> dict[str, Any]:
    """Taramalı `build` işi + verilen işler."""
    return {"sentetik.yml": {"jobs": {"build": {"steps": [SCAN_STEP, SECRET_STEP]}, **jobs}}}


ORDER_RED = {
    "git-c-tirnakli-deger": _one({"run": 'git -c "user.name=fe bot" push origin HEAD'}, SCAN_STEP),
    "git-C-dizin": _one({"run": "git -C alt push"}, SCAN_STEP),
    "git-satir-devami": _one({"run": "git \\\n  push origin HEAD"}, SCAN_STEP),
    "git-komut-ikamesi": _one({"run": 'cikti="$(git -C alt push 2>&1)"'}, SCAN_STEP),
    "buyuk-harf-Secrets": _one({"env": {"PAT": "${{ Secrets.PAT }}"}, "run": "x"}, SCAN_STEP),
    "buyuk-harf-SECRETS-indeks": _one(
        {"env": {"PAT": "${{ SECRETS['PAT'] }}"}, "run": "x"}, SCAN_STEP
    ),
    "is-env-taramali-is": _one(SCAN_STEP, {"run": "x"}, env={"PAT": "${{ secrets.PAT }}"}),
    "is-env-taramasiz-is": _one({"run": "x"}, env={"PAT": "${{ secrets.PAT }}"}),
    "is-always-needs": _chain(
        deploy={"needs": "build", "if": "${{ always() }}", "steps": [SECRET_STEP]}
    ),
    "is-not-cancelled-needs": _chain(
        deploy={
            "needs": ["build"],
            "if": "!cancelled() && github.ref == 'refs/heads/main'",
            "steps": [SECRET_STEP],
        }
    ),
    "is-failure-needs": _chain(
        deploy={"needs": "build", "if": "failure()", "steps": [SECRET_STEP]}
    ),
    "yeniden-kullanilabilir-needs-yok": {
        "sentetik.yml": {
            "jobs": {"cagri": {"uses": "./.github/workflows/x.yml", "secrets": "inherit"}}
        }
    },
}

ORDER_RED_R1 = {
    # Düzeltme turu 1 (I-1): tırnaklı komut dizesindeki push BASE regex'inde yakalanıyordu.
    "bash-c-tirnakli": _one({"run": "bash -c 'git push origin HEAD'"}, SCAN_STEP),
    "eval-tirnakli": _one({"run": "eval 'git push origin HEAD'"}, SCAN_STEP),
    "ssh-uzak-komut": _one({"run": "ssh host 'cd repo && git push'"}, SCAN_STEP),
    "kapanmamis-tirnak": _one({"run": 'git -C alt push "yarim'}, SCAN_STEP),
    # BASE'in hiç görmediği biçim: tırnaklı dizede `-C` (yalnız kabuk okuması yakalar).
    "bash-c-git-C": _one({"run": "bash -c 'git -C alt push'"}, SCAN_STEP),
    # Ters tırnak sözcüğe yapışır (`` `git ``): yalnız ikame dalı ayırır.
    "ters-tirnak-ikamesi": _one({"run": 'cikti="`git -C alt push`"'}, SCAN_STEP),
    # Düzeltme turu 2 (N-1, N-3): bash yorumu `\` ile sürdürmez — sonraki satır koşar.
    "yorum-devami": _one({"run": "# eski: git commit -m x \\\ngit push origin HEAD"}, SCAN_STEP),
    "yorum-devami-C": _one({"run": "# not \\\ngit -C site push"}, SCAN_STEP),
    "bash-c-ikameli": _one(
        {"run": 'bash -c "git -C site push origin $(git rev-parse HEAD)"'}, SCAN_STEP
    ),
    "sh-c-ters-tirnakli": _one({"run": 'sh -c "git --no-pager push origin `cat ref`"'}, SCAN_STEP),
    "kelime-ici-diyez": _one({"run": "n=${#dosyalar[@]}; git -C site push"}, SCAN_STEP),
    "url-diyez": _one({"run": "curl -s https://x/a#b && git -C site push"}, SCAN_STEP),
    # Düzeltme turu 3 (N-7): `"$(…)"` içinde iç içe çift tırnak — shlex dış tırnağı kapanmış sayar.
    "ikame-ic-tirnak-c": _one(
        {"run": 'cikti="$(git -c "user.name=fe bot" push origin HEAD 2>&1)"'}, SCAN_STEP
    ),
    "ikame-ic-tirnak-C": _one({"run": 'cikti="$(git -C "alt dizin" push 2>&1)"'}, SCAN_STEP),
    # N-8: bash `\⏎`yi SİLER (kelime ortasında da); `\\⏎` satır devamı değildir.
    "kelime-ortasi-devam": _one({"run": "git -C site pu\\\nsh origin HEAD"}, SCAN_STEP),
    "kacisli-ters-bolu": _one({"run": "echo yol\\\\\ngit -C site push"}, SCAN_STEP),
    # N-12/N-13: ANSI-C tırnağı, `--attr-source <ağaç>`, takma ad, değişkende alt komut, xargs.
    "ansi-c-tirnak": _one({"run": "git -C site $'push' origin HEAD"}, SCAN_STEP),
    "attr-source": _one({"run": "git --attr-source HEAD push origin HEAD"}, SCAN_STEP),
    "takma-ad": _one({"run": "git -c alias.yolla=push yolla origin HEAD"}, SCAN_STEP),
    "degiskende-alt-komut": _one({"run": "alt=push; git -C site $alt origin HEAD"}, SCAN_STEP),
    "xargs-ile": _one({"run": "echo push | xargs git -C site"}, SCAN_STEP),
    # I-3: taramasız bir işi beklemek korumaz.
    "needs-taramasiz-is": {
        "sentetik.yml": {
            "jobs": {
                "lint": {"steps": [{"run": "ruff check"}]},
                "deploy": {"needs": "lint", "steps": [SECRET_STEP]},
            }
        }
    },
    # M-1: `success()` de bir durum fonksiyonu; üst düzey tek terim değilse örtük success() yok.
    "is-not-success-needs": _chain(
        deploy={"needs": "build", "if": "${{ !success() }}", "steps": [SECRET_STEP]}
    ),
}
ORDER_RED = {**ORDER_RED, **ORDER_RED_R1}

ORDER_CLEAN = {
    "bugunku-bot-push": _one(
        SCAN_STEP, {"run": "until git -c http.version=HTTP/1.1 push origin HEAD; do"}
    ),
    "push-kelimesi-git-degil": _one({"run": 'echo "::warning::push reddedildi"'}, SCAN_STEP),
    "git-fetch": _one({"run": "git fetch origin main"}, SCAN_STEP),
    "zincirli-needs": _chain(
        deploy={"needs": "build", "steps": [SECRET_STEP]},
        notify={"needs": "deploy", "steps": [SECRET_STEP]},
    ),
    "is-always-bagli": _chain(
        deploy={
            "needs": "build",
            "if": "${{ always() && needs.build.result == 'success' }}",
            "steps": [SECRET_STEP],
        }
    ),
    "yeniden-kullanilabilir-needs": _chain(
        cagri={"needs": "build", "uses": "./.github/workflows/x.yml", "secrets": "inherit"}
    ),
}

ORDER_CLEAN = {
    **ORDER_CLEAN,
    "is-acik-success-needs": _chain(
        deploy={
            "needs": "build",
            "if": "success() && github.ref == 'refs/heads/main'",
            "steps": [SECRET_STEP],
        }
    ),
}

BINDING_RED = {
    "always-secret": _one(SCAN_STEP, {**SECRET_STEP, "if": "always()"}),
    "not-cancelled-push": _one(
        SCAN_STEP, {"if": "${{ !cancelled() }}", "run": "git push origin HEAD"}
    ),
    "failure-secret": _one(SCAN_STEP, {**SECRET_STEP, "if": "failure()"}),
    # `&&`, `||`dan sıkı bağlar: `always() || (x && bağ)` — `&&` ile bölünce bağ terim gibi görünür.
    "ust-duzey-veya": _one(
        SCAN_STEP, {**SECRET_STEP, "if": f"always() || github.event_name == 'schedule' && {BOUND}"}
    ),
    "taramanin-id-si-yok": _one(
        {"name": "Secret taraması", "run": "./scripts/check_secrets.sh"},
        {**SECRET_STEP, "if": f"${{{{ !cancelled() && {BOUND} }}}}"},
    ),
    "is-env-always": _one(
        SCAN_STEP, {"if": "always()", "run": "echo"}, env={"PAT": "${{ secrets.PAT }}"}
    ),
}

BINDING_RED = {
    **BINDING_RED,
    "not-success-secret": _one(SCAN_STEP, {**SECRET_STEP, "if": "${{ !success() }}"}),
    "success-veya-secret": _one(
        SCAN_STEP, {**SECRET_STEP, "if": "success() || github.event_name == 'schedule'"}
    ),
}

BINDING_CLEAN = {
    "bagli-bekci": _one(
        SCAN_STEP,
        {
            **SECRET_STEP,
            "if": f"${{{{ !cancelled() && {BOUND} && github.event_name == 'schedule' }}}}",
        },
    ),
    "ortuk-success": _one(SCAN_STEP, SECRET_STEP),
    "secretsiz-yansitma": _one(
        SCAN_STEP,
        {
            "if": "always() && steps.seal.outputs.code != '0'",
            "env": {"SEAL_CODE": "${{ steps.seal.outputs.code }}"},
            "run": "exit 1",
        },
    ),
    "alarm-github-token": _one(
        SCAN_STEP,
        {
            "if": "${{ failure() || cancelled() }}",
            "env": {"GITHUB_TOKEN": "${{ github.token }}"},
            "run": "x",
        },
    ),
}


BINDING_CLEAN = {
    **BINDING_CLEAN,
    # `&&`ın içindeki parantezli `||` üst düzey değildir: bağ yine üst düzey bir terim.
    "parantezli-durum": _one(
        SCAN_STEP, {**SECRET_STEP, "if": f"(failure() || cancelled()) && {BOUND}"}
    ),
    # GitHub dizeleri harf duyarsız karşılaştırır.
    "buyuk-harf-deger": _one(
        SCAN_STEP, {**SECRET_STEP, "if": "always() && steps.secret_scan.outcome == 'Success'"}
    ),
    "acik-success": _one(SCAN_STEP, {**SECRET_STEP, "if": "success() && github.ref == 'x'"}),
}


@pytest.mark.parametrize("workflows", ORDER_RED.values(), ids=ORDER_RED.keys())
def test_the_order_guard_sees_every_escape_shape(workflows: dict[str, Any]) -> None:
    _, broken = _order_violations(workflows)

    assert broken, "kaçış biçimi sıra bekçisinden yeşil geçti"


@pytest.mark.parametrize("workflows", ORDER_CLEAN.values(), ids=ORDER_CLEAN.keys())
def test_the_order_guard_stays_quiet_on_safe_shapes(workflows: dict[str, Any]) -> None:
    _, broken = _order_violations(workflows)

    assert broken == []


@pytest.mark.parametrize("workflows", BINDING_RED.values(), ids=BINDING_RED.keys())
def test_the_binding_guard_sees_a_step_that_outlives_a_red_scan(workflows: dict[str, Any]) -> None:
    _, broken = _unbound_after_scan(workflows)

    assert broken, "kırmızı taramadan sonra koşan maruz adım bekçiden yeşil geçti"


@pytest.mark.parametrize("workflows", BINDING_CLEAN.values(), ids=BINDING_CLEAN.keys())
def test_the_binding_guard_stays_quiet_on_safe_shapes(workflows: dict[str, Any]) -> None:
    _, broken = _unbound_after_scan(workflows)

    assert broken == []


@pytest.mark.parametrize(
    "run",
    [
        "git push origin HEAD",
        "until git -c http.version=HTTP/1.1 push origin HEAD; do",
        "bash -c 'git push origin HEAD'",
        "eval 'git push origin HEAD'",
        "ssh host 'cd repo && git push'",
        'durum="git push reddedildi"',
        "# git push origin HEAD",
        "# eski: git commit -m x \\\ngit push origin HEAD",
        # Ham metinde satır aşan eşleşme (BASE'in `\s+`i satır sonunu da yer): gürültü, BASE gördü.
        "git -c a=b\npush",
    ],
    ids=[
        "duz",
        "bot",
        "bash-c",
        "eval",
        "ssh",
        "atama-icinde",
        "yorum",
        "yorum-devami",
        "satir-asiri",
    ],
)
def test_push_detection_covers_everything_the_base_regex_saw(run: str) -> None:
    """I-1/N-1: kabuk okuması BASE regex'inin (oturum 10) gördüğü hiçbir biçimi kaçırmaz — BASE
    regex'i HAM metne (yorum dâhil, hiçbir şey atılmadan) uygulanır ve kabuk okumasıyla birleşir.
    `atama-icinde` ve `yorum` push değildir: birleşimin bedeli olan gürültü, sessiz kaçış değil."""
    assert BASE_GIT_PUSH.search(run), "vaka BASE'in gördüğü biçim değil — kurgu bayat"
    assert _pushes({"run": run})


@pytest.mark.parametrize(
    "run",
    [
        'git -c "user.name=fe bot" push origin HEAD',
        "git -C alt push",
        'cikti="$(git -C alt push 2>&1)"',
        'cikti="`git -C alt push`"',
        "bash -c 'git -C alt push'",
        'bash -c "git -C site push origin $(git rev-parse HEAD)"',
        'sh -c "git --no-pager push origin `cat ref`"',
        "n=${#dosyalar[@]}; git -C site push",
        "curl -s https://x/a#b && git -C site push",
        "# not \\\ngit -C site push",
        "git --attr-source HEAD push origin HEAD",
        "git -C site pu\\\nsh origin HEAD",
        "echo yol\\\\\ngit -C site push",
        "gi''t -C site pu\"\"sh",
        'git -C alt push "yarim',
    ],
    ids=[
        "c-tirnakli-deger",
        "C-dizin",
        "komut-ikamesi",
        "ters-tirnak",
        "bash-c-git-C",
        "bash-c-ikameli",
        "sh-c-ters-tirnakli",
        "kelime-ici-diyez",
        "url-diyez",
        "yorum-devami-C",
        "attr-source",
        "kelime-ortasi-devam",
        "kacisli-ters-bolu",
        "tirnakla-bolunmus-sozcuk",
        "kapanmamis-tirnak",
    ],
)
def test_the_shell_reading_alone_sees_each_shape(run: str) -> None:
    """Kabuk okuması tek başına (BASE ve kaba kural OLMADAN) bu biçimleri görür: birleşimin her
    katmanı ayrı pinlidir — kaba kural katmanın bozulmasını örtmesin. `tirnakla-bolunmus-sozcuk`
    (`gi''t … pu""sh`) yalnız bu katmanın gördüğü biçimdir."""
    assert any("push" in _git_subcommands(line) for line in _logical_lines(run))
