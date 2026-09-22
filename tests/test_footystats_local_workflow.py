"""`footystats-local.yml`: Mac'teki işin sonucunu GitHub'a taşıyan rapor workflow'u (R74).

Yerel iş alarmı kendi `gh` token'ıyla açsaydı GitHub, kişinin kendi eylemi olduğu için
bildirim göndermezdi. Rapor workflow'u alarmı `github.token` (github-actions) kimliğiyle açar
ve kapatır; her tetiklemesi bekçi için bir kalp atışıdır (RUNBOOK §3.9).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from datetime import timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from tests.workflow_helpers import REPO, _steps, _triggers

REPORT = REPO / ".github/workflows/footystats-local.yml"


def _job() -> dict[str, Any]:
    document = yaml.safe_load(REPORT.read_text(encoding="utf-8"))
    (job,) = document["jobs"].values()
    return dict(job)


def _step(name: str) -> dict[str, Any]:
    return next(step for step in _steps(REPORT) if step.get("name") == name)


def test_only_a_dispatch_with_an_ok_or_fail_result_triggers_it() -> None:
    """Başka tetik yok: `schedule` ya da `push` bir sonuç bildirmeden alarmı kapatırdı."""
    triggers = _triggers(REPORT)
    result = triggers["workflow_dispatch"]["inputs"]["result"]

    assert set(triggers) == {"workflow_dispatch"}
    assert result["type"] == "choice"
    assert result["options"] == ["ok", "fail"]
    assert result["required"] is True


def test_the_result_opens_or_closes_the_footystats_local_alarm() -> None:
    opens, closes = _step("Alarm aç"), _step("Alarm kapat")

    assert opens["if"] == "inputs.result == 'fail'"
    assert "ops_alert.py fail --workflow footystats-local" in opens["run"]
    assert closes["if"] == "inputs.result == 'ok'"
    assert "ops_alert.py ok --workflow footystats-local" in closes["run"]
    assert closes.get("continue-on-error") is True


def test_the_input_never_reaches_a_shell() -> None:
    """Girdi yalnız `if:` koşulunda okunur; `run:` gövdesine `${{ }}` ile girseydi kabuğa
    yorumlanacak metin olarak inerdi (workflow enjeksiyonu)."""
    bodies = [str(step.get("run", "")) for step in _steps(REPORT)]

    assert not [body for body in bodies if re.search(r"\$\{\{[^}]*inputs", body)]


def test_it_holds_no_secret_and_only_the_issue_permission() -> None:
    text = REPORT.read_text(encoding="utf-8")

    assert "secrets." not in text
    assert _job()["permissions"] == {"contents": "read", "issues": "write"}


def _ops_alert() -> ModuleType:
    """`scripts/` bir paket değil: bekçi kendi yolundan yüklenir (bkz. test_ops_alert.py)."""
    # Ad benzersiz: test_ops_alert.py'nin `sys.modules["ops_alert"]` kaydını ezmesin.
    spec = importlib.util.spec_from_file_location(
        "ops_alert_heartbeat", REPO / "scripts/ops_alert.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass, modülünü sys.modules'ta arar
    spec.loader.exec_module(module)
    return module


def test_the_watchdog_counts_its_dispatches_as_the_macs_heartbeat() -> None:
    """Mac günlerce kapalı kalırsa (ya da launchd işi durursa) hiçbir tur kırmızı olmaz; bunu
    yalnız rapor tetiklemelerinin yaşı gösterir. Eşik 72 sa: bir hafta sonu kapalı kalan Mac
    alarm üretmez, bir hafta kapalı kalan üretir."""
    watched = {trigger.workflow: trigger for trigger in _ops_alert().TRIGGERS}
    trigger = watched.get(REPORT.name)

    assert trigger is not None, "bekçi footystats-local.yml'i izlemiyor"
    assert trigger.event == "workflow_dispatch"
    assert trigger.max_age == timedelta(hours=72)
    assert trigger.alarm == "footystats-local", "kalp atışı bekçi alarmını paylaşmamalı"


def test_report_path_is_what_the_local_job_dispatches() -> None:
    """Workflow yeniden adlandırılır da betik eski adı tetiklemeyi sürdürürse GitHub her raporu
    404'le reddeder: alarm da kalp atışı da hiç gelmez."""
    script = (REPO / "scripts/footystats_daily.sh").read_text(encoding="utf-8")

    assert f'REPORT="{Path(REPORT).name}"' in script
    assert 'gh workflow run "$REPORT"' in script


def test_a_running_report_is_never_cancelled() -> None:
    """Koşan bir rapor iptal edilseydi alarm yarıda açılır ya da kapanırdı. Kuyruktaki eski rapor
    yenisi gelince düşer (GitHub grupta tek bekleyen tur tutar): son durum en yeni rapordur."""
    document = yaml.safe_load(REPORT.read_text(encoding="utf-8"))

    assert document["concurrency"] == {"group": "footystats-local", "cancel-in-progress": False}
