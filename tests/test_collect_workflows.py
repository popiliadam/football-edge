"""Faz 1 toplayıcı workflow'ları: tetik yalnız pg_cron, sıklık sabit, secret yalnız toplama
adımında; kırmızı bir toplayıcı ötekileri durdurmadan turu kırmızıya çevirir.

Toplama adımının kabuk gövdesi `uv` yerine bir sahteyle koşulur; bir runner'da yeşil verdiği
burada ölçülmez.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from football_edge import collect
from tests.workflow_helpers import (
    COLLECT_DAILY,
    COLLECT_NEWS,
    COLLECTORS,
    REPO,
    _cron_jobs,
    _functions,
    _index_of,
    _steps,
    _triggers,
)

# ── Faz 1 toplayıcıları da pg_cron'dan (db/migrations/0005) ──────────────────────────────────
# Toplayıcılar yalnız elle koşuyordu: hiç koşmayan toplayıcı hiçbir şey toplamaz ve kaçan bir
# gözlem, kapanış oranı gibi, sonradan üretilemez.


def _wrapper(path: Path) -> str:
    """Toplayıcı workflow'unun sarmalayıcısı: `collect-news.yml` → `dispatch_collect_news`."""
    return "dispatch_" + path.stem.replace("-", "_")


@pytest.mark.parametrize("path", COLLECTORS, ids=lambda path: path.name)
def test_collectors_are_triggered_by_pg_cron_alone(path: Path) -> None:
    """GitHub'ın `schedule`ı seyrek ve gecikmeli koşar (0003); ikinci bir tetik aynı turu iki kez
    koşar ve kaynağa iki kat istek gider. Tek tetik `<ad>-dispatch` işi ve onun sarmalayıcısı."""
    _, command = _cron_jobs().get(f"{path.stem}-dispatch", ("", ""))

    assert command == f"select ops.{_wrapper(path)}()", (
        f"{path.stem}-dispatch işinin komutu {command!r}: {path.name} hiç tetiklenmiyor"
    )
    assert f"ops.dispatch_workflow('{path.name}')" in _functions().get(_wrapper(path), ""), (
        f"ops.{_wrapper(path)}() {path.name}'i tetiklemiyor"
    )
    assert "schedule" not in _triggers(path), f"{path.name} GitHub'dan da tetikleniyor"


# Saat alanı: günlük tur günde bir kez (tek bir saat), haber iki saatte bir.
CADENCE = {COLLECT_DAILY: r"\d+", COLLECT_NEWS: r"\*/2"}


@pytest.mark.parametrize("path", CADENCE, ids=lambda path: path.name)
def test_collector_dispatch_cadence_is_pinned(path: Path) -> None:
    """Varlık yetmez: `'*/2 * * * *'` gibi bir yazım hatası haber kaynağını günde 720 kez çağırır
    ve yukarıdaki test yeşil kalırdı. Dakika tek bir sayıdır ve mühürün ya da snapshot'ın dakikası
    değildir (zaman-kritik tetik dakikasını paylaşmaz); tur her gün koşar."""
    jobs = _cron_jobs()
    seal_period = re.fullmatch(r"\*/(\d+)", jobs["seal-dispatch"][0].split()[0])
    assert seal_period is not None, f"seal zamanlaması okunamadı: {jobs['seal-dispatch'][0]!r}"
    taken = {
        *range(0, 60, int(seal_period.group(1))),
        int(jobs["snapshot-dispatch"][0].split()[0]),
    }
    spec, _ = jobs[f"{path.stem}-dispatch"]
    minute, hour, *days = spec.split()

    assert re.fullmatch(r"\d+", minute) and int(minute) not in taken, (
        f"{path.name}: dakika {minute!r} tek bir sayı değil ya da mühür/snapshot dakikası "
        f"{sorted(taken)}"
    )
    assert re.fullmatch(CADENCE[path], hour) and days == ["*", "*", "*"], (
        f"{path.name}: zamanlama {spec!r} — beklenen saat alanı {CADENCE[path]!r}, her gün"
    )


def _secret_expressions(text: str) -> list[str]:
    """Metindeki `${{ … }}` ifadelerinden secret okuyanlar (`secrets.X` ya da `secrets['X']`).
    Çıplak kelime aranmaz: `./scripts/check_secrets.sh` adımı da "secrets" içerir."""
    return [
        expression.strip()
        for expression in re.findall(r"\$\{\{(.*?)\}\}", text, flags=re.S)
        if re.search(r"\bsecrets\b", expression)
    ]


def _secret_paths(node: Any, path: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    """Ayrıştırılmış belgede secret ifadesi taşıyan her değerin yolu (yorumlar belgede yok)."""
    if isinstance(node, dict):
        return [
            found for key, value in node.items() for found in _secret_paths(value, (*path, key))
        ]
    if isinstance(node, list):
        return [
            found
            for index, value in enumerate(node)
            for found in _secret_paths(value, (*path, index))
        ]
    return [path] if _secret_expressions(str(node)) else []


# Veritabanına yazan adımlar: toplayıcı ve collect-news'te hemen ardından haber deposu (R172).
DATABASE_STEPS = {
    COLLECT_DAILY: ("football_edge.collect",),
    COLLECT_NEWS: ("football_edge.collect", "football_edge.features sync-news"),
}


@pytest.mark.parametrize("path", COLLECTORS, ids=lambda path: path.name)
def test_only_the_collector_step_gets_a_secret_and_only_the_database_one(path: Path) -> None:
    """Toplayıcılar ücretli API çağırmaz: `ODDS_API_KEY` verilen bir workflow kredi harcayabilir ve
    pg_cron onu kimse bakmadan koşar. `DATABASE_URL` de YALNIZ veritabanına yazan adımların
    (toplama; collect-news'te ayrıca haber deposu senkronu) `env`inde durur: workflow ya da job
    `env`ine taşınırsa secret taramasına, üçüncü taraf `setup-uv` eylemine, `uv sync`e ve alarm
    adımlarına da açılır."""
    text = path.read_text(encoding="utf-8")
    secrets = sorted(set(_secret_expressions(text)))
    document = yaml.safe_load(text)
    ((job_id, job),) = document["jobs"].items()
    expected = [
        ("jobs", job_id, "steps", _index_of(job["steps"], needle), "env", "DATABASE_URL")
        for needle in DATABASE_STEPS[path]
    ]
    reached = _secret_paths(document)

    assert secrets == ["secrets.DATABASE_URL"], f"{path.name} beklenmeyen secret okuyor: {secrets}"
    assert reached == expected, (
        f"{path.name}: secret'ın ulaştığı yerler {reached} — yalnız {expected} olmalı"
    )


# `uv run python -m football_edge.collect <alt komut>`un yerine geçer: alt komutu kaydeder,
# `FAIL_COMMAND` için `FAIL_CODE` ile döner.
FAKE_UV = """\
#!/usr/bin/env bash
for command; do :; done
echo "$command" >> "$CALLS"
[ "$command" != "$FAIL_COMMAND" ] || exit "$FAIL_CODE"
"""


def _collect_run_body(path: Path) -> str:
    return next(
        str(step["run"]) for step in _steps(path) if "football_edge.collect" in str(step.get("run"))
    )


@pytest.mark.parametrize(
    ("path", "failing", "code", "named"),
    [
        (COLLECT_DAILY, None, 0, ""),
        (COLLECT_DAILY, "fetch-tff", collect.EXIT_SOURCE_FAILED, "kaynak"),
        (COLLECT_DAILY, "fetch-venues", 1, "beklenmedik"),
        (COLLECT_NEWS, None, 0, ""),
        (COLLECT_NEWS, "fetch-news", collect.EXIT_SOURCE_FAILED, "kaynak"),
        (COLLECT_NEWS, "fetch-news", 1, "beklenmedik"),
    ],
    ids=[
        "daily-ok",
        "daily-tff-7",
        "daily-venues-1",
        "news-ok",
        "news-7",
        "news-1",
    ],
)
def test_a_red_collector_does_not_stop_the_others_and_turns_the_run_red(
    tmp_path: Path, path: Path, failing: str | None, code: int, named: str
) -> None:
    """Workflow koşulmaz: toplama adımının `run:` gövdesi, `uv` yerine kayıt tutan bir sahteyle,
    GitHub'ın `shell:` verilmemiş adımı koştuğu `bash -e` altında koşulur. Bir kaynağın arızası
    ötekilerin gözlemini kaçırtmamalı; düşen toplayıcı turu kırmızıya çevirmeli ve `::error::`
    satırında (turun özetine düşer) adıyla görünmeli."""
    fake = tmp_path / "uv"
    fake.write_text(FAKE_UV, encoding="utf-8")
    fake.chmod(0o755)
    script = tmp_path / "step.sh"
    script.write_text(_collect_run_body(path), encoding="utf-8")
    calls = tmp_path / "calls"
    calls.touch()
    env = {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "CALLS": str(calls),
        "FAIL_COMMAND": failing or "",
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

    ran = calls.read_text(encoding="utf-8").split()
    errors = [line for line in result.stdout.splitlines() if line.startswith("::error::")]
    assert ran == list(COLLECTORS[path]), f"{path.name}: koşan alt komutlar {ran}"
    assert (result.returncode == 0) == (failing is None), (
        f"{path.name}: düşen {failing or 'yok'}, adımın çıkışı {result.returncode}"
    )
    if failing is None:
        assert errors == [], f"{path.name}: yeşil turda hata satırı: {errors}"
    else:
        assert any(failing in line and named in line for line in errors), (
            f"{path.name}: {failing} (exit {code}) adıyla ({named!r}) raporlanmıyor: {errors}"
        )


WORKFLOWS = REPO / ".github/workflows"


def _run_bodies(path: Path) -> list[str]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        str(step.get("run", ""))
        for job in document["jobs"].values()
        for step in job.get("steps", [])
    ]


def test_footystats_is_not_collected_on_github_hosted_runners() -> None:
    """İlk canlı `collect-daily` turunda (2026-09-22, run 35710579845) footystats'ın altı lig
    sayfasının altısı da 403 döndü; aynı kod ve aynı kimlik Mac'ten 200 alıyor. Cloudflare
    veri merkezi IP'lerini geri çeviriyor. Kimliği değiştirmek (R2) ya da bot korumasını
    aşmak seçenek değil: iş Mac'te koşar (RUNBOOK §3.9). GitHub'a geri eklenirse tur her gün
    kırmızı kalır ve açık alarm tff/venues arızalarını bildirimsiz bırakır (DEFERRED 10h).
    """
    offenders = [
        path.name
        for path in sorted(WORKFLOWS.glob("*.yml"))
        if any("fetch-footystats" in body for body in _run_bodies(path))
    ]
    assert offenders == [], f"footystats GitHub runner'ında koşturuluyor: {offenders}"
