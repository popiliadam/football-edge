"""`shadow.yml`: yalnız pg_cron (0011), secret yalnız gölge adımında, çıkış kodları adıyla."""

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
FAKE_UV = """\
#!/usr/bin/env bash
echo "$*" >> "$CALLS"
exit "${FAIL_CODE:-0}"
"""


def test_shadow_is_dispatched_by_pg_cron_after_the_decision_on_tuesday_and_friday() -> None:
    spec, command = _cron_jobs()["shadow-dispatch"]

    assert command == "select ops.dispatch_shadow()"
    assert spec == "35 12 * * 2,5"
    assert "ops.dispatch_workflow('shadow.yml')" in _functions()["dispatch_shadow"]
    assert "shadow.yml" in _allow_list()
    assert set(_triggers(SHADOW)) == {"workflow_dispatch"}


def test_only_the_shadow_step_gets_the_database() -> None:
    steps = _steps(SHADOW)
    index = _index_of(steps, COMMAND)
    holders = [i for i, step in enumerate(steps) if "DATABASE_URL" in str(step.get("env", {}))]

    assert index is not None and holders == [index]
    assert _index_of(steps, "scripts/check_secrets.sh") is not None
    assert _index_of(steps, "scripts/check_secrets.sh") < index  # type: ignore[operator]


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
