#!/usr/bin/env python3
"""Kırmızı workflow turları için GitHub issue alarmı; pg_cron tetik ve Odds API kredi bekçisi.

    fail --workflow <ad> --run-url <url>   `🔴 <ad> kırmızı` issue'sunu açar; açıksa
                                           yalnız gövdesini son tura göre günceller
    ok   --workflow <ad> --run-url <url>   açık alarmı "yeşile döndü" yorumuyla kapatır
    watchdog --run-url <url> [--min-credits N]
                                           `TRIGGERS`teki bir tetik bayatsa ya da Odds API
                                           kredisi N'nin (varsayılan 60) altında, ölçülemez
                                           ya da ölçümü ücretliyse `🔴 bekçi kırmızı`yı açar
                                           ya da günceller, hepsi yolundaysa kapatır; iki
                                           durumda da exit 0. Kendi başlığı olan tetik
                                           (Mac'in kalp atışı) bayatlığını o başlıkta açar,
                                           kapatmayı o işin `ok` raporuna bırakır

Her komut yalnız kendi başlığındaki alarma dokunur. GitHub API'nin kendisi düşerse exit 1.
`GITHUB_TOKEN` ve `GITHUB_REPOSITORY` ortamdan okunur; bekçi `ODDS_API_KEY`i de okur ve onu
hiçbir çıktıya yazmaz. Prosedür: docs/RUNBOOK.md §3.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

API = "https://api.github.com"
ODDS_API = "https://api.the-odds-api.com/v4"
LABEL = "ops-alert"
WATCHDOG = "bekçi"
# `run_seal` 5, `run_snapshot` 10 kredinin altında turu kendisi keser (rounds.py): eşik o
# tabanların üstündedir ki haber kredi bitmeden gelsin.
MIN_CREDITS = 60


@dataclass(frozen=True)
class Trigger:
    """Bekçinin tazeliğini ölçtüğü tetik: `workflow`un en son turu `max_age`den eski olmamalı.

    `alarm` bayatlığın yazıldığı başlık. Varsayılan bekçinin kendi alarmı; kendi başlığı olan
    bir tetik (Mac'in kalp atışı) onu paylaşmaz: açık kalan bekçi alarmı, sonradan ölen başka
    bir tetiği yalnız gövde düzenlemesiyle, yani bildirimsiz bırakırdı.
    """

    workflow: str
    event: str | None  # None: tetik türü ne olursa olsun en son tur
    max_age: timedelta
    hint: str
    alarm: str = WATCHDOG


TRIGGERS = (
    # Yalnız `workflow_dispatch`: bekçinin kendi turu `schedule`dır ve dispatch'i örterdi.
    Trigger(
        workflow="seal.yml",
        event="workflow_dispatch",
        max_age=timedelta(minutes=60),
        hint="pg_cron dispatch durmuş olabilir: token iptal/API hatası — RUNBOOK §3.3",
    ),
    Trigger(
        workflow="snapshot.yml",
        event=None,
        max_age=timedelta(hours=30),
        hint="pg_cron snapshot-dispatch durmuş olabilir — RUNBOOK §3.3",
    ),
    # Toplayıcıların TEK tetiği pg_cron'dur (0005): her turları dispatch turudur. Eşik = kadans
    # + pay: günlük (07:10) 30 sa, iki saatte bir (:07) 4 sa.
    Trigger(
        workflow="collect-daily.yml",
        event=None,
        max_age=timedelta(hours=30),
        hint="pg_cron collect-daily-dispatch durmuş olabilir — RUNBOOK §3.3",
    ),
    Trigger(
        workflow="collect-news.yml",
        event=None,
        max_age=timedelta(hours=4),
        hint="pg_cron collect-news-dispatch durmuş olabilir — RUNBOOK §3.3",
    ),
    # Mac'teki footystats işi her turdan sonra bu rapor workflow'unu tetikler (R74): kalp atışı.
    # 72 sa: hafta sonu kapalı kalan bir Mac alarm üretmez, bir hafta kapalı kalan üretir.
    Trigger(
        workflow="footystats-local.yml",
        event="workflow_dispatch",
        max_age=timedelta(hours=72),
        hint="Mac'teki footystats işi raporlamıyor: Mac kapalı, launchd işi durmuş ya da gh "
        "oturumu düşmüş — RUNBOOK §3.9",
        alarm="footystats-local",
    ),
    # Tarihsel taban haftalık (0008, salı 09:50): eşik bir hafta + pay.
    Trigger(
        workflow="history.yml",
        event=None,
        max_age=timedelta(days=8),
        hint="pg_cron history-dispatch durmuş olabilir — RUNBOOK §3.3",
    ),
)


def _client(repository: str, token: str, transport: httpx.BaseTransport | None) -> httpx.Client:
    return httpx.Client(
        base_url=f"{API}/repos/{repository}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "football-edge-ops-alert",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=20.0,
        transport=transport,
    )


def _odds_client(transport: httpx.BaseTransport | None) -> httpx.Client:
    # GitHub istemcisinden AYRI: onun `Authorization` başlığı üçüncü tarafa gitmemeli.
    return httpx.Client(timeout=20.0, transport=transport)


def _json(response: httpx.Response) -> Any:
    response.raise_for_status()
    return response.json()


def _title(name: str) -> str:
    return f"🔴 {name} kırmızı"


def _numbers(numbers: list[int]) -> str:
    return ", ".join(f"#{number}" for number in numbers)


def _open_alarms(client: httpx.Client, name: str) -> list[int]:
    """Bu adın AÇIK alarmları; başlık tam eşleşir, başka alarmın issue'su sayılmaz."""
    params = {"state": "open", "labels": LABEL, "per_page": "100"}
    issues: list[dict[str, Any]] = _json(client.get("/issues", params=params))
    return [int(issue["number"]) for issue in issues if issue.get("title") == _title(name)]


def _ensure_label(client: httpx.Client) -> None:
    response = client.get(f"/labels/{LABEL}")
    if response.status_code != httpx.codes.NOT_FOUND:
        response.raise_for_status()
        return
    label = {"name": LABEL, "color": "b60205", "description": "kırmızı tur ve bekçi alarmı"}
    _json(client.post("/labels", json=label))


def raise_alarm(client: httpx.Client, name: str, body: str) -> str:
    """Açık alarm yoksa etiketli issue açar; varsa YALNIZ gövdesini günceller.

    Yeni issue ve yorum bildirim üretir, gövde düzenlemesi üretmez: kırmızı sürerken her
    turun (15 dakikada bir) e-postası gerçek alarmı gürültüye gömerdi.
    """
    numbers = _open_alarms(client, name)
    for number in numbers:
        _json(client.patch(f"/issues/{number}", json={"body": body}))
    if numbers:
        return f"alarm güncellendi: {_title(name)} {_numbers(numbers)}\n"
    _ensure_label(client)
    issue = {"title": _title(name), "body": body, "labels": [LABEL]}
    opened: dict[str, Any] = _json(client.post("/issues", json=issue))
    return f"alarm açıldı: {_title(name)} #{opened['number']}\n"


def clear_alarm(client: httpx.Client, name: str, run_url: str) -> str:
    """Açık alarm varsa "yeşile döndü" yorumu yazıp kapatır; yoksa hiçbir şey yazmaz."""
    numbers = _open_alarms(client, name)
    for number in numbers:
        comment = {"body": f"yeşile döndü: {run_url}"}
        _json(client.post(f"/issues/{number}/comments", json=comment))
        closing = {"state": "closed", "state_reason": "completed"}
        _json(client.patch(f"/issues/{number}", json=closing))
    if not numbers:
        return f"açık alarm yok: {_title(name)}\n"
    return f"alarm kapandı: {_title(name)} {_numbers(numbers)}\n"


def _red_run_body(run_url: str, now: datetime) -> str:
    return (
        f"Son kırmızı tur: {run_url}\n"
        f"Zaman: {now:%Y-%m-%d %H:%M} UTC\n\n"
        "Yeşil bir tur bu issue'yu kendiliğinden kapatır. Prosedür: docs/RUNBOOK.md §3.\n"
    )


def _last_run(client: httpx.Client, trigger: Trigger) -> datetime | None:
    event = {"event": trigger.event} if trigger.event is not None else {}
    params = {"per_page": "1", **event}
    payload: dict[str, Any] = _json(
        client.get(f"/actions/workflows/{trigger.workflow}/runs", params=params)
    )
    runs: list[dict[str, Any]] = payload.get("workflow_runs") or []
    return datetime.fromisoformat(str(runs[0]["created_at"])) if runs else None


def _duration(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    return f"{minutes // 60} sa {minutes % 60} dk"


def _staleness(client: httpx.Client, trigger: Trigger, now: datetime) -> str | None:
    """Bayat tetik için adlandırılmış satır, taze için None. Hiç koşmamış tetik en bayatıdır."""
    kind = f"{trigger.event} turu" if trigger.event is not None else "tur"
    last = _last_run(client, trigger)
    if last is None:
        return f"{trigger.workflow}: hiç {kind} yok — {trigger.hint}"
    if now - last <= trigger.max_age:
        return None
    return (
        f"{trigger.workflow}: son {kind} {_duration(now - last)} önce "
        f"(eşik {_duration(trigger.max_age)}) — {trigger.hint}"
    )


def stale_by_alarm(client: httpx.Client, now: datetime) -> dict[str, list[str]]:
    """Bayat tetiklerin satırları, yazılacakları alarm başlığına göre; boş sözlük tüm tetiklerin
    canlı olduğu demektir."""
    grouped: dict[str, list[str]] = {}
    for trigger in TRIGGERS:
        line = _staleness(client, trigger, now)
        if line is not None:
            grouped[trigger.alarm] = [*grouped.get(trigger.alarm, []), line]
    return grouped


def _redact(text: str, api_key: str) -> str:
    """Anahtarı düz ve kırpılmış hâliyle, bir de URL sorgusundaki `apikey=` değeri olarak —
    harf büyüklüğü ve kodlaması ne olursa olsun — gizler.

    Satır sonuyla dolgulu secret'ın çıplak hâli durum satırında, kodlanmış hâli bir
    yönlendirmenin küçük harfli yankısında görünebilir. Boşluk dizesi gizlenmez: raporu bozardı.
    """
    for secret in (api_key, api_key.strip()):
        if secret.strip():
            text = text.replace(secret, "***")
    return re.sub(r"(?i)(apikey=)[^&\s'\"]+", r"\1***", text)


def _cost(headers: httpx.Headers) -> str | None:
    """Ölçümün kendi bedeli: ücretsiz sanılan uç kredi yiyorsa bekçi onu her turda tüketir."""
    last = headers.get("x-requests-last")
    if last is None or last == "0":
        return None
    return (
        f"Odds API: kredi ölçümü ücretli: x-requests-last={last} — /v4/sports ücretsiz sanılıyordu"
    )


def _remaining(headers: httpx.Headers, min_credits: int) -> str | None:
    try:
        remaining = int(headers["x-requests-remaining"])
    except (KeyError, ValueError):
        return "Odds API: kredi ÖLÇÜLEMEDİ — x-requests-remaining başlığı yok ya da sayı değil"
    if remaining >= min_credits:
        return None
    return (
        f"Odds API: kredi az: {remaining} kaldı (eşik {min_credits}) — tükenince mühür turu "
        "EXIT_QUOTA_EXHAUSTED (2) ile kapanır ve mühür kaçar"
    )


def odds_credits(client: httpx.Client, api_key: str, min_credits: int) -> list[str]:
    """Kredi sorunlarının satırları: az, ölçülemeyen ya da ücretli ölçülen kredi. Boş liste:
    kredi ölçüldü, yeterli ve ölçüm ücretli görünmüyor.

    Satırlar PUBLIC issue'ya yazılır ve GitHub'ın secret maskelemesi issue'yu kapsamaz;
    httpx'in hata mesajı ise isteğin URL'sini, yani anahtarı taşır. İstekteki anahtar
    kırpılmaz: bekçi, seal'in düşeceği gibi düşmeli.
    """
    if not api_key:
        return ["Odds API: kredi ÖLÇÜLEMEDİ — ODDS_API_KEY ortamda yok"]
    try:
        response = client.get(f"{ODDS_API}/sports", params={"apiKey": api_key})
        response.raise_for_status()
    except httpx.HTTPError as error:
        # Tek satır: `::warning::` ve gövdedeki madde ilk satır sonunda biter.
        reason = " ".join(_redact(f"{type(error).__name__}: {error}", api_key).split())
        return [f"Odds API: kredi ÖLÇÜLEMEDİ — {reason}"]
    lines = (_cost(response.headers), _remaining(response.headers, min_credits))
    return [line for line in lines if line is not None]


def _watchdog_body(
    problems: list[str], run_url: str, now: datetime, *, closer: str | None = None
) -> str:
    diagnosis = "".join(f"- {line}\n" for line in problems)
    closing = (
        f"Bu issue'yu {closer} kapatır.\n"
        if closer is not None
        else "Bu issue'yu yalnız teşhisi boş bir bekçi turu kapatır: tetikler taze, kredi eşikte\n"
        "ya da üstünde, ölçüm ücretli görünmüyor. Seal'in yeşil turu kapatmaz.\n"
    )
    return (
        f"Teşhis:\n{diagnosis}\n"
        f"Bekçi turu: {run_url}\n"
        f"Zaman: {now:%Y-%m-%d %H:%M} UTC\n\n"
        f"{closing}Prosedür: docs/RUNBOOK.md §3.6.\n"
    )


def report_watchdog(client: httpx.Client, run_url: str, now: datetime, credit: list[str]) -> str:
    """Sorun varsa bekçinin KENDİ alarmını açar ya da günceller, yoksa onu kapatır.

    Sorun: bayat tetik ya da `credit` satırı (az, ölçülemeyen ya da ücretli ölçülen kredi).
    Seal alarmına dokunmaz ve seal job'ını düşürmez: düşürseydi seal'in sonraki yeşil turu
    (≤15 dk) alarmı geri alırdı ve ölü bir snapshot her yedek turda yeniden unutulurdu.
    """
    stale = stale_by_alarm(client, now)
    # Kendi başlığı olan tetik yalnız AÇILIR: kapatmak o işin yeşil raporunun işidir (açık alarm
    # kırmızı bir toplayıcı raporundan da gelebilir; taze kalp atışı onu örtmemeli).
    own = "".join(
        raise_alarm(
            client, name, _watchdog_body(lines, run_url, now, closer="işin bir sonraki `ok` raporu")
        )
        for name, lines in stale.items()
        if name != WATCHDOG
    )
    problems = [*stale.get(WATCHDOG, []), *credit]
    if not problems:
        healthy = "bekçi: kendi tetikleri taze, Odds API kredisi yeterli\n"
        return own + healthy + clear_alarm(client, WATCHDOG, run_url)
    # `::warning::` turun özet sayfasına düşer; adım bilerek yeşil kalır.
    warnings = "".join(f"::warning::{line}\n" for line in problems)
    return own + warnings + raise_alarm(client, WATCHDOG, _watchdog_body(problems, run_url, now))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="kırmızı tur alarmı; tetik ve kredi bekçisi")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("fail", "ok"):
        command = commands.add_parser(name)
        command.add_argument("--workflow", required=True)
        command.add_argument("--run-url", required=True)
    watch = commands.add_parser("watchdog")
    watch.add_argument("--run-url", required=True)
    watch.add_argument("--min-credits", type=int, default=MIN_CREDITS)
    return parser


def _execute(
    args: argparse.Namespace, client: httpx.Client, odds: httpx.Client, now: datetime
) -> str:
    if args.command == "fail":
        return raise_alarm(client, args.workflow, _red_run_body(args.run_url, now))
    if args.command == "ok":
        return clear_alarm(client, args.workflow, args.run_url)
    credit = odds_credits(odds, os.environ.get("ODDS_API_KEY", ""), args.min_credits)
    return report_watchdog(client, args.run_url, now, credit)


def main(
    argv: Sequence[str] | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
    now: datetime | None = None,
) -> int:
    # httpx her isteği INFO'da URL'siyle, yani sorgudaki anahtarla loglar: log yapılandırılırsa
    # sızmasın. httpcore'un DEBUG ayrıntısı da aynı sebeple kısılır.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    args = _parser().parse_args(argv)
    env = {name: os.environ.get(name, "") for name in ("GITHUB_TOKEN", "GITHUB_REPOSITORY")}
    missing = [name for name, value in env.items() if not value]
    if missing:
        sys.stderr.write(f"HATA: ortamda yok: {', '.join(missing)}\n")
        return 2
    try:
        with (
            _client(env["GITHUB_REPOSITORY"], env["GITHUB_TOKEN"], transport) as client,
            _odds_client(transport) as odds,
        ):
            sys.stdout.write(_execute(args, client, odds, now or datetime.now(UTC)))
    except httpx.HTTPError as error:
        # Alarm yolu düştüyse adım da düşer: sessizce "tamam" sayılmaz.
        sys.stderr.write(f"HATA: GitHub API çağrısı düştü — {error}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
