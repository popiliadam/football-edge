"""`sources-audit.yml`: aynı kalan robots.txt'in doğrulama tarihini bot tazeler, sapma alarm açar.

İş akışının içeriği okunur; commit/push adımının kabuk betiği ise sahte bir `git` ile gerçekten
koşturulur — depoya da ağa da çıkılmaz. Ölçülmeyen: git'in kendi birleştirme davranışı ve
workflow'un bir runner'da yeşil verdiği.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github/workflows/sources-audit.yml"
DRIFT = "scripts/robots_drift.py"
COMMIT_MESSAGE = "chore: robots yeniden doğrulandı"
MERGE_MESSAGE = "merge: origin/main — sources-audit botu"
MAIN_ONLY = "github.ref == 'refs/heads/main'"
# Sahte git'in kaydettiği biçim (`$*`): kabuk tırnakları düşmüş hâli.
FETCH = "fetch origin main"
MERGE = f"merge --no-edit -m {MERGE_MESSAGE} FETCH_HEAD"

# Sahte git: her çağrıyı kaydeder; `diff` FAKE_DIFF_EXIT döner, `push` ilk FAKE_REJECTS
# denemede reddedilir (seal.yml'in botu main'e araya çıpa commit'i sokmuş gibi).
FAKE_GIT = """\
#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_LOG"
for arg in "$@"; do
  case "$arg" in
    diff) exit "$FAKE_DIFF_EXIT" ;;
    push)
      echo push >> "$FAKE_PUSHES"
      [ "$(($(wc -l < "$FAKE_PUSHES")))" -gt "$FAKE_REJECTS" ]
      exit ;;
  esac
done
exit 0
"""


def _document() -> dict[str, Any]:
    return dict(yaml.safe_load(WORKFLOW.read_text(encoding="utf-8")))


def _job() -> dict[str, Any]:
    (job,) = _document()["jobs"].values()
    return dict(job)


def _steps() -> list[dict[str, Any]]:
    return list(_job()["steps"])


def _index_of(needle: str) -> int:
    steps = _steps()
    found = [index for index, step in enumerate(steps) if needle in str(step.get("run", ""))]
    assert found, f"sources-audit.yml'de `{needle}` koşan adım yok"
    return found[0]


def _condition(step: dict[str, Any]) -> str:
    """Adımın `if:` ifadesi; varsa `${{ }}` sarmalı soyulmuş."""
    text = str(step.get("if", "")).strip()
    if text.startswith("${{") and text.endswith("}}"):
        return text[3:-2].strip()
    return text


def _conjuncts(step: dict[str, Any]) -> set[str]:
    condition = _condition(step)
    assert "||" not in condition, condition
    return {part.strip() for part in condition.split("&&")}


def _commit_body() -> str:
    return str(_steps()[_index_of(COMMIT_MESSAGE)]["run"])


def test_drift_step_refreshes_the_verified_dates() -> None:
    assert "--refresh" in str(_steps()[_index_of(DRIFT)]["run"]).split()


def test_runs_queue_in_their_own_concurrency_group() -> None:
    """Üst üste binen iki tur aynı tarihi ayrı ayrı çekip birbirinin push'unu reddettirirdi.
    `odds-collect` değil: o grubu paylaşan workflow mühür turlarını kuyruktan düşürür."""
    assert _document().get("concurrency") == {"group": "sources-audit", "cancel-in-progress": False}


def test_checkout_takes_the_current_tip_of_the_ref() -> None:
    """Yeniden koşturulan eski bir tur varsayılan olarak TETİKLEYEN sha'yı alır: o günün bayat
    tarihlerini tazeler ve güncel main'le çakışıp kırmızı verir. Ref'in bugünkü ucu alınmalı."""
    (checkout,) = [step for step in _steps() if "actions/checkout" in str(step.get("uses", ""))]

    assert (checkout.get("with") or {}).get("ref") == "${{ github.ref }}"


def test_github_schedule_stays_the_daily_trigger() -> None:
    """PyYAML (YAML 1.1) `on:` anahtarını True'ya çevirir; iki yazım da okunur."""
    document = _document()
    triggers = dict(document.get("on") or document.get(True) or {})

    assert "schedule" in triggers, "günlük ölçüm ve tazeleme GitHub schedule'ıyla koşmalı"


def test_drift_step_runs_even_after_a_red_offline_contract() -> None:
    """Tarih 30 günü aşmışsa çevrimdışı adım kırmızıdır; tazeleme de atlanırsa o tarih bir daha
    hiç tazelenmez ve kapı elle düzeltilene dek kırmızı kalır."""
    steps = _steps()
    contract = _index_of("football_edge.collect sources-audit")
    drift = _index_of(DRIFT)

    assert contract < drift
    assert _condition(steps[drift]) == "!cancelled()"


def test_commit_step_follows_the_drift_step_even_when_it_is_red_and_only_on_main() -> None:
    """Sapan bir kaynak turu kırmızı yapar; aynı kalanların tazelenen tarihi yine yazılmalı.
    Başka bir dala elle tetiklenen tur ise ne main'e ne o dala bot commit'i atar."""
    drift = _index_of(DRIFT)
    commit = _index_of(COMMIT_MESSAGE)

    assert drift < commit
    assert _conjuncts(_steps()[commit]) == {"!cancelled()", "github.ref == 'refs/heads/main'"}


def test_commit_step_commits_only_the_registry_under_the_bot_identity() -> None:
    body = _commit_body()

    assert "git add config/sources.yaml" in body
    assert not re.search(r"git add (-A|--all|\.)", body), "bot kayıt defteri dışında dosya ekliyor"
    assert f'git commit -m "{COMMIT_MESSAGE} $(date -u +%F)"' in body
    assert 'git config user.name "football-edge-bot"' in body


def test_no_push_is_forced_and_a_rejection_is_merged_not_rebased() -> None:
    """main'e seal.yml'in botu da çıpa push'luyor: force onun commit'ini silerdi, rebase de
    geçmişi yeniden yazar. Reddedilen push main'i BİRLEŞTİRİR — deponun `<tür>: <açıklama>`
    biçiminde bir mesajla (git'in varsayılanı "Merge branch 'main' of …" değil)."""
    runs = "\n".join(str(step.get("run", "")) for step in _steps())
    git_lines = re.findall(r"\bgit\b[^\n]*", runs)
    pushes = [line for line in git_lines if "push" in line.split()]

    assert pushes, "push adımı yok"
    for line in pushes:
        tokens = line.split()
        assert not [t for t in tokens if t in ("-f", "--mirror") or t.startswith(("--force", "+"))]
    assert not [line for line in git_lines if re.search(r"\b(pull|rebase)\b", line)], git_lines
    assert f"git {FETCH}" in runs
    assert f'git merge --no-edit -m "{MERGE_MESSAGE}" FETCH_HEAD' in runs
    assert re.fullmatch(r"[a-z]+: \S.*", MERGE_MESSAGE)


def _run_commit_step(tmp_path: Path, *, changed: bool, rejects: int) -> tuple[int, list[str]]:
    """Commit/push adımını sahte `git` ile koşturur; (çıkış kodu, git çağrıları) döner."""
    fake = tmp_path / "bin/git"
    fake.parent.mkdir()
    fake.write_text(FAKE_GIT, encoding="utf-8")
    fake.chmod(0o755)
    log = tmp_path / "git.log"
    # Ortamdan GIT_* taşınmaz: sahte git dışında hiçbir şey gerçek bir depoya dokunamaz.
    env = {
        "PATH": f"{fake.parent}{os.pathsep}{os.environ.get('PATH', '')}",
        "FAKE_LOG": str(log),
        "FAKE_PUSHES": str(tmp_path / "pushes"),
        "FAKE_DIFF_EXIT": "1" if changed else "0",
        "FAKE_REJECTS": str(rejects),
    }
    # `shell:` verilmemiş `run` adımını GitHub `bash -e {0}` ile koşar.
    result = subprocess.run(
        ["bash", "-e", "-c", _commit_body()],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    calls = log.read_text(encoding="utf-8").splitlines() if log.is_file() else []
    return result.returncode, calls


def _is_push(call: str) -> bool:
    return "push" in call.split()


def _sync_calls(calls: list[str]) -> list[str]:
    """push/fetch/merge çağrılarının sırası. fetch ve merge yalnız tam argümanlarıyla sayılır."""
    names = {FETCH: "fetch", MERGE: "merge"}
    return [
        "push" if _is_push(call) else names[call]
        for call in calls
        if _is_push(call) or call in names
    ]


def test_unchanged_dates_make_no_commit(tmp_path: Path) -> None:
    code, calls = _run_commit_step(tmp_path, changed=False, rejects=0)

    assert code == 0
    assert calls == ["diff --quiet -- config/sources.yaml"]


def test_a_rejected_push_merges_main_with_a_conventional_message_and_retries(
    tmp_path: Path,
) -> None:
    code, calls = _run_commit_step(tmp_path, changed=True, rejects=1)

    assert code == 0
    assert _sync_calls(calls) == ["push", "fetch", "merge", "push"]
    commit = next(i for i, c in enumerate(calls) if c.startswith("commit "))
    assert re.fullmatch(rf"commit -m {COMMIT_MESSAGE} \d{{4}}-\d{{2}}-\d{{2}}", calls[commit])
    assert (
        calls.index("add config/sources.yaml")
        < commit
        < min(i for i, c in enumerate(calls) if _is_push(c))
    )


def test_push_gives_up_red_after_three_rejections(tmp_path: Path) -> None:
    code, calls = _run_commit_step(tmp_path, changed=True, rejects=99)

    assert code != 0, "üç kez reddedilen push turu yeşil bıraktı: tarih main'e yazılmadı"
    assert _sync_calls(calls) == ["push", "fetch", "merge", "push", "fetch", "merge", "push"]


def test_job_may_write_contents_and_issues_and_read_runs() -> None:
    """Job düzeyindeki `permissions:` üst düzeyi tamamen ezer: listelenmeyen izin `none` olur."""
    permissions = _job().get("permissions") or {}

    assert permissions == {"contents": "write", "issues": "write", "actions": "read"}
    assert _document().get("permissions") == {"contents": "read"}, (
        "yazma yetkisi workflow geneline açılmamalı"
    )


@pytest.mark.parametrize(
    ("command", "status"),
    [("fail", {"failure()", "cancelled()"}), ("ok", {"success()"})],
    ids=["alarm-aç", "alarm-kapat"],
)
def test_red_run_opens_the_alarm_and_green_run_closes_it_on_main_only(
    command: str, status: set[str]
) -> None:
    """`failure()`/`success()` yalnız önceki adımları görür: alarm adımları job'ın son iki
    adımıdır. Zaman aşımı turu iptal eder ve `failure()` yanlış döner — `cancelled()` o yüzden.
    Yalnız main: başka dala elle tetiklenen yeşil tur main'in açık alarmını kapatmamalı."""
    steps = _steps()
    index = _index_of(f"scripts/ops_alert.py {command} --workflow sources-audit ")
    step = steps[index]
    conjuncts = {part.strip() for part in _condition(step).split("&&")}

    assert index == len(steps) - (2 if command == "fail" else 1)
    assert MAIN_ONLY in conjuncts, f"alarm main dışında da çalışıyor: {_condition(step)!r}"
    (rest,) = conjuncts - {MAIN_ONLY}
    if "||" in rest:
        # `&&`, `||`dan sıkı bağlar: parantezsiz yazılırsa main koşulu yalnız son dala uyar.
        assert rest.startswith("(") and rest.endswith(")"), rest
        rest = rest[1:-1]
    assert {part.strip() for part in rest.split("||")} == status
    env = step.get("env") or {}
    assert env.get("GITHUB_TOKEN") == "${{ github.token }}"
    assert str(env.get("RUN_URL", "")).endswith("/actions/runs/${{ github.run_id }}")
    assert '--run-url "$RUN_URL"' in str(step["run"])


def test_only_the_closing_step_may_fail_without_turning_the_run_red() -> None:
    """Kapatma düşerse (ör. GitHub 502) yeşil tur kırmızıya dönmez; push ya da alarm açma
    düşerse tur kırmızı kalmalı ki bozuk yol görünsün."""
    steps = _steps()
    tolerant = [index for index, step in enumerate(steps) if step.get("continue-on-error")]

    assert tolerant == [len(steps) - 1]
    assert steps[-1]["continue-on-error"] is True
