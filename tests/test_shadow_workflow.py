"""`shadow.yml`: yalnız pg_cron (0011), veritabanı secret'ı yalnız gölge, rapor, kademe 2
ve dilim sayacı adımlarında, çıkış kodları adıyla; haftalık gölge raporu (Faz 4 T0a) yalnız salı
turunda."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.jev_workflow_helpers import (
    JEV_CASE_IDS,
    JEV_CASES,
    JEV_SECRET,
    SWITCH,
    run_step,
    with_jev_key,
)
from tests.workflow_helpers import (
    REPO,
    _allow_list,
    _cron_jobs,
    _functions,
    _index_of,
    _steps,
    _triggers,
)

SHADOW = REPO / ".github/workflows/shadow.yml"
COMMAND = "football_edge.live shadow"
REPORT = "football_edge.live report"
FAKE_UV = """\
#!/usr/bin/env bash
echo "$*" >> "$CALLS"
exit "${FAIL_CODE:-0}"
"""
# Adım yalnız `date -u +%u` sorar: haftanın günü (1 pazartesi … 7 pazar) ortamdan gelir.
FAKE_DATE = """\
#!/usr/bin/env bash
echo "$WEEKDAY"
"""


def test_shadow_is_dispatched_by_pg_cron_after_the_decision_on_tuesday_and_friday() -> None:
    spec, command = _cron_jobs()["shadow-dispatch"]

    assert command == "select ops.dispatch_shadow()"
    assert spec == "35 12 * * 2,5"
    assert "ops.dispatch_workflow('shadow.yml')" in _functions()["dispatch_shadow"]
    assert "shadow.yml" in _allow_list()
    assert set(_triggers(SHADOW)) == {"workflow_dispatch"}


TIER2 = "football_edge.features tier2"
AFTER_SHADOW = (
    "${{ !cancelled() && steps.secret_scan.outcome == 'success' && "
    "steps.shadow.outcome == 'success' }}"
)
JEV2_OPEN_IF = "${{ !cancelled() && steps.tier2.outputs.jev == 'fail' }}"


def _at(steps: list[dict[str, Any]], needle: str) -> int:
    index = _index_of(steps, needle)
    assert index is not None, f"shadow.yml: {needle!r} adımı yok"
    return index


def test_only_the_database_steps_get_the_database() -> None:
    steps = _steps(SHADOW)
    shadow, report, tier2 = _at(steps, COMMAND), _at(steps, REPORT), _at(steps, TIER2)
    holders = [i for i, step in enumerate(steps) if "DATABASE_URL" in str(step.get("env", {}))]

    counter = _at(steps, "football_edge.features slice-status")
    assert holders == [shadow, report, tier2, counter]
    assert _at(steps, "scripts/check_secrets.sh") < shadow < report < tier2 < counter


def _fake_bin(tmp_path: Path) -> Path:
    for name, body in (("uv", FAKE_UV), ("date", FAKE_DATE)):
        fake = tmp_path / name
        fake.write_text(body, encoding="utf-8")
        fake.chmod(0o755)
    calls = tmp_path / "calls"
    calls.touch()
    return calls


def _run_report(
    tmp_path: Path, *, weekday: int, code: int
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    calls = _fake_bin(tmp_path)
    env = {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "CALLS": str(calls),
        "FAIL_CODE": str(code),
        "WEEKDAY": str(weekday),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
    }
    body = str(_steps(SHADOW)[_index_of(_steps(SHADOW), REPORT)]["run"])  # type: ignore[index]
    result = subprocess.run(
        ["bash", "-e", "-c", body], env=env, capture_output=True, text=True, timeout=30, check=False
    )
    return result, calls.read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize(
    ("code", "named"), [(0, ""), (9, "kilit"), (11, "ağırlığı"), (3, "beklenmedik")]
)
def test_the_tuesday_report_goes_to_the_step_summary_and_names_every_exit_code(
    tmp_path: Path, code: int, named: str
) -> None:
    result, calls = _run_report(tmp_path, weekday=2, code=code)

    errors = [line for line in result.stdout.splitlines() if line.startswith("::error::")]
    assert calls == [f"run python -m {REPORT} --out {tmp_path / 'summary.md'}"]
    assert result.returncode == code
    if code == 0:
        assert errors == []
    else:
        assert len(errors) == 1 and named in errors[0] and f"exit {code}" in errors[0], errors


@pytest.mark.parametrize("weekday", [1, 3, 4, 5, 6, 7])
def test_the_report_runs_only_on_the_tuesday_round(tmp_path: Path, weekday: int) -> None:
    """Cuma turu (5) ve elle tetiklenen başka günler raporu atlar: haftada bir rapor."""
    result, calls = _run_report(tmp_path, weekday=weekday, code=11)

    assert (result.returncode, calls) == (0, [])
    assert "salı turu değil" in result.stdout


@pytest.mark.parametrize(
    ("code", "named"), [(0, ""), (9, "kilit"), (11, "yapılandırması"), (3, "beklenmedik")]
)
def test_the_shadow_step_names_every_exit_code_and_keeps_the_run_red(
    tmp_path: Path, code: int, named: str
) -> None:
    fake = tmp_path / "uv"
    fake.write_text(FAKE_UV, encoding="utf-8")
    fake.chmod(0o755)
    calls = tmp_path / "calls"
    calls.touch()
    env = {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "CALLS": str(calls),
        "FAIL_CODE": str(code),
    }
    body = str(_steps(SHADOW)[_index_of(_steps(SHADOW), COMMAND)]["run"])  # type: ignore[index]

    result = subprocess.run(
        ["bash", "-e", "-c", body], env=env, capture_output=True, text=True, timeout=30, check=False
    )

    errors = [line for line in result.stdout.splitlines() if line.startswith("::error::")]
    assert calls.read_text(encoding="utf-8").splitlines() == [f"run python -m {COMMAND}"]
    assert result.returncode == code
    if code == 0:
        assert errors == []
    else:
        assert len(errors) == 1 and named in errors[0] and f"exit {code}" in errors[0], errors


@pytest.mark.parametrize("name", ["shadow.yml", "history.yml"])
def test_the_credit_free_workflows_never_receive_the_odds_api_key(name: str) -> None:
    """m10: gölge ve (cuma ek turu dahil) tarihsel senkron KREDİ harcamaz — anahtar hiç verilmez."""
    text = (REPO / ".github/workflows" / name).read_text(encoding="utf-8")

    assert "ODDS" + "_API_KEY" not in text


def test_a_red_shadow_step_skips_the_report_and_still_raises_the_alarm() -> None:
    """Review Focus: rapor adımı `if:` taşımaz (varsayılan `success()`): gölge adımı kırmızıysa
    rapor koşmaz, tur kırmızı kalır ve alarm son iki adımda açılır."""
    steps = _steps(SHADOW)
    index, report = _index_of(steps, COMMAND), _index_of(steps, REPORT)
    opens = _index_of(steps, "scripts/ops_alert.py fail --workflow shadow ")

    assert index is not None and report is not None and opens is not None
    assert "if" not in steps[report] and "continue-on-error" not in steps[report]
    assert index < report < opens == len(steps) - 2


def test_tier2_runs_after_the_report_even_when_the_report_is_red() -> None:
    """R180/R186: maç kümesi bu turun gölge satırlarıdır — gölge yeşilse kademe 2 koşar."""
    steps = _steps(SHADOW)
    step = steps[_at(steps, TIER2)]

    env = dict(step["env"])

    assert (step["id"], step["if"]) == ("tier2", AFTER_SHADOW)
    assert env.pop("DATABASE_URL") == "${{ secrets.DATABASE_URL }}"
    assert env in ({}, SWITCH), "ücret anahtarı ile JEV_ENABLED birlikte gelir (R177, I-5)"


@pytest.mark.parametrize(
    ("code", "enabled", "jev", "named"),
    JEV_CASES,
    ids=JEV_CASE_IDS,
)
def test_the_tier2_step_never_turns_the_shadow_run_red_and_names_every_jev_outcome(
    tmp_path: Path, code: int, enabled: str | None, jev: str, named: str
) -> None:
    steps = _steps(SHADOW)

    run = run_step(tmp_path, str(steps[_at(steps, TIER2)]["run"]), code=code, jev_enabled=enabled)

    assert (run.returncode, run.outputs) == (0, {"jev": jev})
    if jev == "ok":
        assert run.errors == ()
    else:
        assert len(run.errors) == 1 and named in run.errors[0] and f"exit {code}" in run.errors[0]


def test_a_hung_tier2_is_cut_before_the_job_timeout_and_opens_the_jev_alarm(
    tmp_path: Path,
) -> None:
    """İşin 45 dakikalık zaman aşımı işi İPTAL ederdi: shadow alarmı açılır, `jev-kademe2` adımları
    (`!cancelled()`) koşmazdı. Kademe 2 25 dakikada kesilir, 124 `jev=fail` olur (inceleme
    turu 1)."""
    steps = _steps(SHADOW)
    body = str(steps[_at(steps, TIER2)]["run"])

    run = run_step(tmp_path, body, code=124)

    assert f"timeout 25m uv run python -m {TIER2}" in body
    assert (run.returncode, run.outputs) == (0, {"jev": "fail"})
    assert len(run.errors) == 1 and "exit 124" in run.errors[0]


def test_the_jev_key_may_reach_only_the_tier2_step() -> None:
    """Yamasız ve yamalı (R177) belge: anahtar ya hiçbir adımda ya YALNIZ kademe 2'de."""
    document = yaml.safe_load(SHADOW.read_text(encoding="utf-8"))

    for candidate in (document, with_jev_key(document, TIER2)):
        steps = candidate["jobs"]["shadow"]["steps"]
        holders = [i for i, step in enumerate(steps) if JEV_SECRET in str(step.get("env", {}))]
        assert holders in ([], [_at(steps, TIER2)])


def test_a_failed_tier2_opens_the_jev_kademe2_alarm_before_the_shadow_alarm() -> None:
    steps = _steps(SHADOW)
    tier2 = _at(steps, TIER2)
    opens = _at(steps, "scripts/ops_alert.py fail --workflow jev-kademe2 ")
    closes = _at(steps, "scripts/ops_alert.py ok --workflow jev-kademe2 ")

    assert tier2 < opens < closes < _at(steps, "scripts/ops_alert.py fail --workflow shadow ")
    assert steps[opens]["if"] == JEV2_OPEN_IF


SLICE = "football_edge.features slice-status"


def test_slice_status_goes_to_the_summary_right_after_tier2() -> None:
    steps = _steps(SHADOW)
    tier2, counter = _at(steps, TIER2), _at(steps, SLICE)

    assert counter == tier2 + 1
    assert steps[counter]["if"] == AFTER_SHADOW
    assert steps[counter]["env"] == {"DATABASE_URL": "${{ secrets.DATABASE_URL }}"}
    assert '--out "$GITHUB_STEP_SUMMARY"' in str(steps[counter]["run"])


@pytest.mark.parametrize(("code", "named"), [(0, ""), (1, "beklenmedik")])
def test_the_slice_step_names_its_exit_code(tmp_path: Path, code: int, named: str) -> None:
    steps = _steps(SHADOW)

    run = run_step(tmp_path, str(steps[_at(steps, SLICE)]["run"]), code=code)

    assert run.returncode == code
    if code == 0:
        assert run.errors == ()
    else:
        assert len(run.errors) == 1 and named in run.errors[0] and f"exit {code}" in run.errors[0]


def test_a_hung_slice_status_is_cut_before_the_job_timeout_and_named(tmp_path: Path) -> None:
    """Asılı bir sayaç işin 45 dakikasını yerse iş İPTAL olur ve `!cancelled()` Jev alarm adımları
    atlanır: 5 dakikada kesilir, 124 adıyla kırmızı (inceleme 7)."""
    steps = _steps(SHADOW)
    body = str(steps[_at(steps, SLICE)]["run"])

    run = run_step(tmp_path, body, code=124)

    assert f"timeout 5m uv run python -m {SLICE}" in body
    assert run.returncode == 124
    assert len(run.errors) == 1 and "5 dakikada kesildi" in run.errors[0]
    assert "exit 124" in run.errors[0]
