"""`history.yml`: dispatch-only, tek job, secret yalnız veritabanı adımlarında, alarm kuralları.

İzinli listeye (0008, controller Task 8) girince `tests/test_workflows.py`nin ALARMED testleri bu
dosyayı kendiliğinden kapsar; o güne kadar aynı kurallar burada, aynı fonksiyonlarla koşulur.
Senkron adımının kabuk gövdesi `uv` yerine bir sahteyle koşulur; runner'da yeşil verdiği ölçülmez.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from football_edge import collect
from tests import test_collect_workflows as collect_rules
from tests import test_workflows as workflow_rules
from tests.workflow_helpers import REPO, _index_of, _steps, _triggers

HISTORY = REPO / ".github/workflows/history.yml"
SYNC = "football_edge.history sync"
# DATABASE_URL'i alan adımlar, adlarıyla. Task 10 `selftest` adımını buraya ekler; başka hiçbir
# adım (checkout, secret taraması, üçüncü taraf setup-uv, `uv sync`, alarm) secret görmez.
DATABASE_STEPS: tuple[str, ...] = ("Senkron",)


def _document() -> dict[str, Any]:
    return dict(yaml.safe_load(HISTORY.read_text(encoding="utf-8")))


def _sync_index() -> int:
    index = _index_of(_steps(HISTORY), SYNC)
    assert index is not None, "history.yml senkronu hiç koşmuyor"
    return index


def test_history_is_dispatched_only_with_an_optional_boolean_all_input() -> None:
    """pg_cron yalnız `ref` gönderir: zorunlu girdi o turu reddettirirdi."""
    triggers = _triggers(HISTORY)

    assert set(triggers) == {"workflow_dispatch"}, f"beklenmeyen tetik: {sorted(triggers)}"
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"all"}
    spec = inputs["all"]
    assert (spec["type"], spec["default"], spec.get("required", False)) == ("boolean", False, False)


def test_history_is_a_single_job_so_the_shared_workflow_rules_can_read_it() -> None:
    """`workflow_helpers._steps` tek job varsayar; Task 10 selftest'i ADIM olarak ekler."""
    assert list(_document()["jobs"]) == ["history"]


def test_history_queues_in_its_own_concurrency_group() -> None:
    assert _document()["concurrency"] == {"group": "history", "cancel-in-progress": False}


def test_secrets_are_scanned_after_checkout_and_before_the_sync() -> None:
    steps = _steps(HISTORY)
    checkout = _index_of(steps, "actions/checkout", key="uses")
    scan = _index_of(steps, "scripts/check_secrets.sh")

    assert checkout is not None and scan is not None
    assert checkout < scan < _sync_index()


def test_only_the_database_steps_get_a_secret_and_only_the_database_one() -> None:
    """Secret workflow ya da job `env`ine taşınırsa secret taramasına, `setup-uv` eylemine,
    `uv sync`e ve alarm adımlarına da açılır. İzinli adımlar DATABASE_STEPS'te; senkron biri."""
    text = HISTORY.read_text(encoding="utf-8")
    steps = _steps(HISTORY)
    allowed = [index for index, step in enumerate(steps) if step.get("name") in DATABASE_STEPS]

    assert len(allowed) == len(DATABASE_STEPS), f"adı bulunamayan adım: {DATABASE_STEPS}"
    assert _sync_index() in allowed, "senkron adımı DATABASE_STEPS'te değil"
    assert sorted(set(collect_rules._secret_expressions(text))) == ["secrets.DATABASE_URL"]
    assert collect_rules._secret_paths(yaml.safe_load(text)) == [
        ("jobs", "history", "steps", index, "env", "DATABASE_URL") for index in allowed
    ]


RULES: tuple[Callable[[Path], None], ...] = (
    workflow_rules.test_red_run_opens_the_alarm_and_green_run_closes_it,
    workflow_rules.test_only_the_closing_step_may_fail_without_turning_the_run_red,
    workflow_rules.test_alarm_jobs_may_write_issues_and_read_runs,
)


@pytest.mark.parametrize("rule", RULES, ids=lambda rule: rule.__name__)
def test_history_already_obeys_the_alarm_rules_of_dispatched_workflows(
    rule: Callable[[Path], None],
) -> None:
    rule(HISTORY)


# `uv run python -m football_edge.history sync [--all]`un yerine geçer: argümanları kaydeder,
# `FAIL_CODE` ile döner.
FAKE_UV = """\
#!/usr/bin/env bash
echo "$*" >> "$CALLS"
exit "${FAIL_CODE:-0}"
"""


def _run_sync_step(tmp_path: Path, *, all_paths: str, code: int) -> tuple[int, list[str], str]:
    fake = tmp_path / "uv"
    fake.write_text(FAKE_UV, encoding="utf-8")
    fake.chmod(0o755)
    calls = tmp_path / "calls"
    calls.touch()
    env = {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "CALLS": str(calls),
        "FAIL_CODE": str(code),
        "ALL_PATHS": all_paths,
    }
    body = str(_steps(HISTORY)[_sync_index()]["run"])
    # `shell:` verilmemiş `run` adımını GitHub `bash -e {0}` ile koşar.
    result = subprocess.run(
        ["bash", "-e", "-c", body], env=env, capture_output=True, text=True, timeout=30, check=False
    )
    return result.returncode, calls.read_text(encoding="utf-8").splitlines(), result.stdout


@pytest.mark.parametrize(
    ("all_paths", "expected"),
    [("false", f"run python -m {SYNC}"), ("true", f"run python -m {SYNC} --all")],
    ids=["haftalik", "tam-yukleme"],
)
def test_the_all_input_alone_decides_whether_every_path_is_fetched(
    tmp_path: Path, all_paths: str, expected: str
) -> None:
    code, calls, out = _run_sync_step(tmp_path, all_paths=all_paths, code=0)

    assert (code, calls) == (0, [expected])
    assert "::error::" not in out


@pytest.mark.parametrize(
    ("code", "named"),
    [(collect.EXIT_SOURCE_FAILED, "exit 7"), (1, "beklenmedik")],
    ids=["kaynak", "beklenmedik"],
)
def test_a_red_sync_turns_the_run_red_and_names_the_failure(
    tmp_path: Path, code: int, named: str
) -> None:
    returned, _, out = _run_sync_step(tmp_path, all_paths="false", code=code)

    assert returned == code, "senkronun kodu yutuldu: alarm adımı kırmızıyı görmez"
    assert any(line.startswith("::error::") and named in line for line in out.splitlines()), out
