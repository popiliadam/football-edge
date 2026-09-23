"""`collect-news.yml`de haber deposu senkronu (R172): toplamanın HEMEN ardından, adıyla kırmızı.

`news_items.first_seen_at` veritabanı saatidir; senkron toplamadan ayrı bir zamanlamayla koşsaydı
her haber o aralık kadar geç damgalanırdı. Workflow koşulmaz: adımlar YAML'dan okunur ve senkron
adımının `run:` gövdesi, `uv` yerine kayıt tutan bir sahteyle `bash -e` altında koşulur
(`test_collect_workflows.py` deseni).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from football_edge import collect
from tests.workflow_helpers import COLLECT_NEWS, _index_of, _steps

SYNC = "football_edge.features sync-news"
FAKE_UV = """\
#!/usr/bin/env bash
echo "$*" >> "$CALLS"
exit "$FAIL_CODE"
"""


def _sync_step() -> dict[str, Any]:
    steps = _steps(COLLECT_NEWS)
    index = _index_of(steps, SYNC)
    assert index is not None, "collect-news.yml haber deposunu senkronlamıyor"
    return steps[index]


def test_sync_runs_right_after_the_collector_and_before_the_alarm() -> None:
    steps = _steps(COLLECT_NEWS)
    collector = _index_of(steps, "football_edge.collect fetch-news")
    sync = _index_of(steps, SYNC)
    alarm = _index_of(steps, "ops_alert.py fail")

    assert collector is not None and sync is not None and alarm is not None
    assert sync == collector + 1, "senkron toplamanın HEMEN ardından koşmalı (R172)"
    assert sync < alarm, "senkron alarm adımından önce: kırmızısı alarmı açmalı"


def test_sync_step_gets_only_the_database_and_is_never_silenced() -> None:
    """Koşullu (`if:`) ya da `continue-on-error` bir senkron sessizce yeşil kalabilirdi."""
    step = _sync_step()

    assert step.get("env") == {"DATABASE_URL": "${{ secrets.DATABASE_URL }}"}
    assert "if" not in step
    assert not step.get("continue-on-error", False)


@pytest.mark.parametrize(
    ("code", "named"),
    [(0, ""), (collect.EXIT_SOURCE_FAILED, "sözleşme"), (1, "beklenmedik")],
    ids=["ok", "contract-7", "other-1"],
)
def test_a_red_sync_turns_the_run_red_by_name(tmp_path: Path, code: int, named: str) -> None:
    fake = tmp_path / "uv"
    fake.write_text(FAKE_UV, encoding="utf-8")
    fake.chmod(0o755)
    script = tmp_path / "step.sh"
    script.write_text(str(_sync_step()["run"]), encoding="utf-8")
    calls = tmp_path / "calls"
    calls.touch()
    env = {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "CALLS": str(calls),
        "FAIL_CODE": str(code),
    }

    result = subprocess.run(
        ["bash", "-e", str(script)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    errors = [line for line in result.stdout.splitlines() if line.startswith("::error::")]
    assert "python -m football_edge.features sync-news" in calls.read_text(encoding="utf-8")
    assert result.returncode == code
    if code == 0:
        assert errors == []
    else:
        assert any("sync-news" in line and named in line for line in errors), errors
