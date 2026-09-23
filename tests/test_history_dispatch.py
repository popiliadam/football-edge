from __future__ import annotations

import re

from tests.workflow_helpers import REPO, _allow_list, _cron_jobs, _functions, _triggers

HISTORY = REPO / ".github/workflows/history.yml"


def test_history_is_triggered_by_pg_cron_alone() -> None:
    """Taban haftalık tazelenir; GitHub'ın `schedule`ı güvenilmez (0003): tek tetik pg_cron."""
    _, command = _cron_jobs().get("history-dispatch", ("", ""))

    assert command == "select ops.dispatch_history()", "history.yml hiç tetiklenmiyor"
    assert "ops.dispatch_workflow('history.yml')" in _functions().get("dispatch_history", "")
    assert "history.yml" in _allow_list(), "izinli listede yok: her dispatch reddedilir"
    assert "schedule" not in _triggers(HISTORY), "history.yml GitHub'dan da tetikleniyor"


def test_history_dispatch_runs_weekly_outside_time_critical_minutes() -> None:
    """Haftada bir, salı: football-data ana ligleri pazartesi akşamı, ek ligleri salı sabahı
    günceller (Last-Modified, 2026-09-22 ölçümü). Dakika mühür ve snapshot dakikalarından ayrı:
    zaman-kritik tetik dakikasını paylaşmaz."""
    jobs = _cron_jobs()
    seal_period = re.fullmatch(r"\*/(\d+)", jobs["seal-dispatch"][0].split()[0])
    assert seal_period is not None, f"seal zamanlaması okunamadı: {jobs['seal-dispatch'][0]!r}"
    taken = {
        *range(0, 60, int(seal_period.group(1))),
        int(jobs["snapshot-dispatch"][0].split()[0]),
    }
    minute, hour, day, month, weekday = jobs["history-dispatch"][0].split()

    assert re.fullmatch(r"\d+", minute) and int(minute) not in taken, (minute, sorted(taken))
    assert re.fullmatch(r"\d+", hour), hour
    assert (day, month, weekday) == ("*", "*", "2"), "haftada bir, salı değil"


def test_history_is_also_synced_on_friday_before_the_friday_decision() -> None:
    """R132: cuma kararından önce taban bir kez daha tazelenir; aynı fonksiyon, ayrı iş."""
    spec, command = _cron_jobs()["history-dispatch-friday"]
    minute, hour, day, month, weekday = spec.split()

    assert command == "select ops.dispatch_history()"
    assert (minute, hour, day, month, weekday) == ("50", "9", "*", "*", "5")
