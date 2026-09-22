"""`seal.yml`in çıpa adımı ve checkout'u (DEFERRED §10k): adımın kabuk gövdesi sahte bir
`git` ile koşulur.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from tests.workflow_helpers import SEAL, _steps

# ── Çıpa push'u: yalnız commit varsa, reddedilirse main birleştirilerek (DEFERRED §10k) ───────
# main'e sources-audit.yml'in botu ve insanlar da push'luyor: koşulsuz, tek denemelik push doğru
# bir mühür turunu kırmızıya çevirir ve o turun çıpası yayınlanmaz. Adımın `run:` gövdesi sahte
# bir `git` ile koşulur; git'in kendi birleştirmesi ve GitHub'ın reddi burada ölçülmez.

ANCHOR_COMMIT = "chore: zincir başı"
PUSH = ("-c", "http.version=HTTP/1.1", "push", "origin", "HEAD")
FETCH = ("fetch", "origin", "main")
MERGE = ("merge", "--no-edit", "-m", "merge: origin/main — seal botu", "FETCH_HEAD")

# Her çağrı bir satır, argümanlar US (\037) ile ayrı: tırnak hatası da kayıtta görünür.
# `diff --cached` FAKE_DIFF_EXIT döner (adım önce `add` eder, sahnelenmemiş fark kalmaz);
# `push` ilk FAKE_REJECTS denemede reddedilir, `merge` FAKE_MERGE_EXIT döner.
FAKE_GIT = """\
#!/usr/bin/env bash
printf '%s\\037' "$@" >> "$FAKE_LOG"
echo >> "$FAKE_LOG"
while [ "${1-}" = -c ]; do shift 2; done
case "${1-}" in
  diff)
    for arg; do
      case "$arg" in --cached | --staged) exit "$FAKE_DIFF_EXIT" ;; esac
    done ;;
  push)
    echo >> "$FAKE_PUSHES"
    [ "$(($(wc -l < "$FAKE_PUSHES")))" -gt "$FAKE_REJECTS" ] ;;
  merge) exit "$FAKE_MERGE_EXIT" ;;
esac
"""


def _anchor_run_body() -> str:
    return next(
        str(step["run"]) for step in _steps(SEAL) if ANCHOR_COMMIT in str(step.get("run", ""))
    )


def _run_anchor_step(
    tmp_path: Path, *, changed: bool, rejects: int, merge_fails: bool = False
) -> tuple[int, list[tuple[str, ...]], str]:
    """Çıpa adımını sahte `git` ile koşturur: (çıkış kodu, git çağrıları, stdout)."""
    fake = tmp_path / "bin/git"
    fake.parent.mkdir()
    fake.write_text(FAKE_GIT, encoding="utf-8")
    fake.chmod(0o755)
    script = tmp_path / "step.sh"
    script.write_text(_anchor_run_body(), encoding="utf-8")
    log = tmp_path / "git.log"
    # Ortamdan GIT_* taşınmaz: sahte git dışında hiçbir şey gerçek bir depoya dokunamaz.
    env = {
        "PATH": f"{fake.parent}{os.pathsep}{os.environ['PATH']}",
        "FAKE_LOG": str(log),
        "FAKE_PUSHES": str(tmp_path / "pushes"),
        "FAKE_DIFF_EXIT": "1" if changed else "0",
        "FAKE_REJECTS": str(rejects),
        "FAKE_MERGE_EXIT": "1" if merge_fails else "0",
    }
    # `shell:` verilmemiş `run` adımını GitHub `bash -e {0}` ile koşar.
    result = subprocess.run(
        ["bash", "-e", str(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    lines = log.read_text(encoding="utf-8").split("\n") if log.is_file() else []
    calls = [tuple(line.split("\x1f")[:-1]) for line in lines if line]
    return result.returncode, calls, result.stdout


def _git_command(call: tuple[str, ...]) -> str:
    """`git -c k=v push …` → `push`."""
    rest = list(call)
    while rest[:1] == ["-c"]:
        rest = rest[2:]
    return rest[0] if rest else ""


def _sync_calls(calls: list[tuple[str, ...]]) -> list[str]:
    """Ağa ya da geçmişe dokunan çağrıların sırası: beklenen argümanlarla yapılanlar adıyla,
    ötekiler `git …` biçiminde ham hâliyle — argümansız `git fetch` bir adla karışmasın."""
    names = {PUSH: "push", FETCH: "fetch", MERGE: "merge"}
    return [
        names.get(call, "git " + " ".join(call))
        for call in calls
        if _git_command(call) in {"push", "fetch", "pull", "merge", "rebase", "reset"}
    ]


def test_unchanged_anchor_makes_no_commit_and_no_network_call(tmp_path: Path) -> None:
    """publish-head baş değişmediyse dosyaya dokunmaz. Commit'siz push'un yayınlayacağı bir şey
    yoktur, ama main ilerlediyse reddedilir ve doğru bir turu kırmızıya çevirir."""
    code, calls, _ = _run_anchor_step(tmp_path, changed=False, rejects=0)
    commands = [_git_command(call) for call in calls]

    assert code == 0
    assert "diff" in commands, "adım değişikliği hiç sormadı — test kurgusu bayatlamış"
    assert set(commands) <= {"config", "add", "diff"}, f"commit yokken yerel olmayan çağrı: {calls}"


def test_changed_anchor_is_committed_and_pushed_once(tmp_path: Path) -> None:
    code, calls, _ = _run_anchor_step(tmp_path, changed=True, rejects=0)
    commands = [_git_command(call) for call in calls]
    commits = [call for call in calls if _git_command(call) == "commit"]

    assert code == 0
    assert _sync_calls(calls) == ["push"]
    assert len(commits) == 1 and commits[0][:-1] == ("commit", "-m"), commits
    assert re.fullmatch(rf"{ANCHOR_COMMIT} \d{{4}}-\d{{2}}-\d{{2}}", commits[0][-1]), commits
    assert ("add", "ledger/") in calls, f"çıpa dizini sahnelenmiyor: {calls}"
    assert calls.index(("add", "ledger/")) < commands.index("commit") < commands.index("push")


@pytest.mark.parametrize("rejects", [1, 2])
def test_a_rejected_anchor_push_merges_main_and_pushes_again(tmp_path: Path, rejects: int) -> None:
    """Sınır üç push: ikinci ret de birleştirilip üçüncü kez denenir."""
    code, calls, _ = _run_anchor_step(tmp_path, changed=True, rejects=rejects)

    assert code == 0, f"{rejects} retten sonra tur kırmızı: çıpa yayınlanmadı"
    assert _sync_calls(calls) == ["push", *["fetch", "merge", "push"] * rejects]


def test_anchor_push_gives_up_red_after_three_rejections(tmp_path: Path) -> None:
    code, calls, stdout = _run_anchor_step(tmp_path, changed=True, rejects=99)

    assert code != 0, "üç kez reddedilen push turu yeşil bıraktı: çıpa yayınlanmadı"
    assert _sync_calls(calls) == ["push", *["fetch", "merge", "push"] * 2]
    assert any(line.startswith("::error::") for line in stdout.splitlines()), stdout


def test_a_failed_anchor_merge_turns_the_step_red_without_pushing_again(tmp_path: Path) -> None:
    """Çakışan birleştirmeyi insan çözer: yarım birleştirme push'lanmaz."""
    code, calls, _ = _run_anchor_step(tmp_path, changed=True, rejects=1, merge_fails=True)

    assert code != 0
    assert _sync_calls(calls) == ["push", "fetch", "merge"]


def _rewrites_history(call: tuple[str, ...]) -> list[str]:
    """Çağrının force ya da rebase argümanları; `pull` ayarla rebase'e dönebildiği için sayılır."""
    return [
        arg
        for arg in call
        if arg in ("pull", "rebase", "--mirror")
        or arg.startswith(("--force", "--rebase", "+"))
        or re.fullmatch(r"-[a-zA-Z]*f[a-zA-Z]*", arg)
    ]


@pytest.mark.parametrize(
    ("changed", "rejects", "merge_fails"),
    [(False, 0, False), (True, 0, False), (True, 1, False), (True, 99, False), (True, 1, True)],
    ids=["unchanged", "accepted", "rejected-once", "always-rejected", "merge-fails"],
)
def test_no_anchor_git_call_forces_or_rebases(
    tmp_path: Path, changed: bool, rejects: int, merge_fails: bool
) -> None:
    """main'e başkaları da push'luyor: force onların commit'ini siler. Rebase değil merge: turun
    commit'i yazıldığı hâliyle kalır."""
    _, calls, _ = _run_anchor_step(
        tmp_path, changed=changed, rejects=rejects, merge_fails=merge_fails
    )

    assert calls, "adım git'i hiç çağırmadı — test kurgusu bayatlamış"
    assert [call for call in calls if _rewrites_history(call)] == []


def test_seal_checks_out_the_current_tip_of_the_ref() -> None:
    """Kuyrukta bekleyen ya da yeniden koşturulan tur varsayılan olarak TETİKLEYEN sha'yı alır:
    önceki turun çıpa commit'i o tabanda yoktur, bugünün çıpası birleştirmede çakışır ve tur
    kırmızı verir. Tur ref'in bugünkü ucunu almalı."""
    (checkout,) = [
        step for step in _steps(SEAL) if str(step.get("uses", "")).startswith("actions/checkout")
    ]

    assert (checkout.get("with") or {}).get("ref") == "${{ github.ref }}"
