"""`collect-news.yml` kademe 1 adımı (Plan 2 R177, R179, R186; I-4…I-7).

Kademe 1 `sync-news`ten hemen sonra koşar; Jev arızası haber turunu kırmızı yapmaz, `jev-kademe1`
alarmını açar; anahtarsız 17 "Jev kapalı" yeşildir, `JEV_ENABLED=1` iken kırmızıdır (alarm).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.jev_workflow_helpers import AFTER_FETCH, JEV_CASE_IDS, JEV_CASES, SWITCH, run_step
from tests.workflow_helpers import COLLECT_NEWS, _index_of, _steps

TIER1 = "football_edge.features tier1"
OPEN = "scripts/ops_alert.py fail --workflow jev-kademe1 "
CLOSE = "scripts/ops_alert.py ok --workflow jev-kademe1 "
OPEN_IF = "${{ !cancelled() && steps.tier1.outputs.jev == 'fail' }}"
CLOSE_IF = "${{ !cancelled() && steps.tier1.outputs.jev == 'ok' }}"


def _at(steps: list[dict[str, Any]], needle: str) -> int:
    index = _index_of(steps, needle)
    assert index is not None, f"collect-news.yml: {needle!r} adımı yok"
    return index


def _tier1_body() -> str:
    steps = _steps(COLLECT_NEWS)
    return str(steps[_at(steps, TIER1)]["run"])


def test_tier1_runs_right_after_sync_and_even_after_a_failed_source() -> None:
    steps = _steps(COLLECT_NEWS)
    fetch = _at(steps, "football_edge.collect fetch-news")
    sync = _at(steps, "football_edge.features sync-news")
    tier1 = _at(steps, TIER1)

    assert (sync, tier1) == (fetch + 1, fetch + 2)
    assert steps[fetch]["id"] == "fetch"
    assert steps[tier1]["id"] == "tier1"
    assert steps[tier1]["if"] == AFTER_FETCH
    assert "continue-on-error" not in steps[tier1]


def test_tier1_gets_the_database_and_at_most_the_paid_switch() -> None:
    """Anahtar ücret yamasıyla gelir (R177); o güne dek adım anahtarsız koşar ve 17 = Jev kapalı.
    Yama testlere dokunmaz: test iki hâli de (yamasız / yamalı) kabul eder; anahtar ve
    `JEV_ENABLED` yalnız BİRLİKTE gelir (I-5)."""
    steps = _steps(COLLECT_NEWS)
    env = dict(steps[_at(steps, TIER1)]["env"])

    assert env.pop("DATABASE_URL") == "${{ secrets.DATABASE_URL }}"
    assert env in ({}, SWITCH)


@pytest.mark.parametrize(("code", "enabled", "jev", "named"), JEV_CASES, ids=JEV_CASE_IDS)
def test_the_tier1_step_never_turns_the_news_run_red_and_names_every_jev_outcome(
    tmp_path: Path, code: int, enabled: str | None, jev: str, named: str
) -> None:
    run = run_step(tmp_path, _tier1_body(), code=code, jev_enabled=enabled)

    assert run.calls == (f"run python -m {TIER1}",)
    assert run.returncode == 0, "Jev arızası haber turunu kırmızı yapmamalı (R179)"
    assert run.outputs == {"jev": jev}
    if jev == "ok":
        assert run.errors == ()
    else:
        assert len(run.errors) == 1 and named in run.errors[0] and f"exit {code}" in run.errors[0]


def test_jev_off_is_written_to_the_run_summary(tmp_path: Path) -> None:
    run = run_step(tmp_path, _tier1_body(), code=17)

    assert "Jev kapalı" in run.summary


def test_a_failed_jev_step_opens_its_own_alarm_before_the_news_alarm() -> None:
    steps = _steps(COLLECT_NEWS)
    tier1, opens, closes = _at(steps, TIER1), _at(steps, OPEN), _at(steps, CLOSE)
    news_opens = _at(steps, "scripts/ops_alert.py fail --workflow collect-news ")

    assert tier1 < opens < closes < news_opens
    assert (steps[opens]["if"], steps[closes]["if"]) == (OPEN_IF, CLOSE_IF)
    assert steps[closes].get("continue-on-error") is True
    for index in (opens, closes):
        env = steps[index]["env"]
        assert env["GITHUB_TOKEN"] == "${{ github.token }}"
        assert str(env["RUN_URL"]).endswith("/actions/runs/${{ github.run_id }}")


def test_the_news_run_has_room_for_the_capped_tier1() -> None:
    """40 çağrı × gecikme + toplama: 10 dakika yetmez (Task 5 gecikmeyi ölçer)."""
    document = yaml.safe_load(COLLECT_NEWS.read_text(encoding="utf-8"))
    assert document["jobs"]["collect"]["timeout-minutes"] == 20
