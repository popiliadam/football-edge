"""`shadow.yml`: yalnız pg_cron (0011), secret yalnız gölge ve rapor adımlarında, çıkış kodları
adıyla; haftalık gölge raporu (Faz 4 T0a) yalnız salı turunda."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

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


def test_only_the_shadow_and_report_steps_get_the_database() -> None:
    steps = _steps(SHADOW)
    index, report = _index_of(steps, COMMAND), _index_of(steps, REPORT)
    holders = [i for i, step in enumerate(steps) if "DATABASE_URL" in str(step.get("env", {}))]
    scan = _index_of(steps, "scripts/check_secrets.sh")

    assert index is not None and report is not None and holders == [index, report]
    assert scan is not None and scan < index < report


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


@pytest.mark.parametrize(("code", "named"), [(0, ""), (11, "ağırlığı"), (3, "beklenmedik")])
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
    opens = _index_of(steps, "scripts/ops_alert.py fail")

    assert index is not None and report is not None and opens is not None
    assert "if" not in steps[report] and "continue-on-error" not in steps[report]
    assert index < report < opens == len(steps) - 2
