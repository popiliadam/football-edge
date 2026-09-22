#!/usr/bin/env python3
"""Kırmızı `seal`/`snapshot` turları için GitHub issue alarmı ve pg_cron dispatch bekçisi.

    fail --workflow <ad> --run-url <url>   `🔴 <ad> kırmızı` issue'sunu açar; açıksa
                                           yalnız gövdesini son tura göre günceller
    ok   --workflow <ad> --run-url <url>   açık alarmı "yeşile döndü" yorumuyla kapatır
    watchdog                               dispatch ya da snapshot bayatsa exit 1

`GITHUB_TOKEN` ve `GITHUB_REPOSITORY` ortamdan okunur. Prosedür: docs/RUNBOOK.md §3.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

API = "https://api.github.com"
LABEL = "ops-alert"


@dataclass(frozen=True)
class Trigger:
    """Bekçinin tazeliğini ölçtüğü tetik: `workflow`un en son turu `max_age`den eski olmamalı."""

    workflow: str
    event: str | None  # None: tetik türü ne olursa olsun en son tur
    max_age: timedelta
    hint: str


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


def _json(response: httpx.Response) -> Any:
    response.raise_for_status()
    return response.json()


def _title(workflow: str) -> str:
    return f"🔴 {workflow} kırmızı"


def _numbers(numbers: list[int]) -> str:
    return ", ".join(f"#{number}" for number in numbers)


def _open_alarms(client: httpx.Client, workflow: str) -> list[int]:
    """Bu workflow'un AÇIK alarmları; başlık tam eşleşir, başka workflow'unki sayılmaz."""
    params = {"state": "open", "labels": LABEL, "per_page": "100"}
    issues: list[dict[str, Any]] = _json(client.get("/issues", params=params))
    return [int(issue["number"]) for issue in issues if issue.get("title") == _title(workflow)]


def _ensure_label(client: httpx.Client) -> None:
    response = client.get(f"/labels/{LABEL}")
    if response.status_code != httpx.codes.NOT_FOUND:
        response.raise_for_status()
        return
    label = {"name": LABEL, "color": "b60205", "description": "seal/snapshot kırmızı tur alarmı"}
    _json(client.post("/labels", json=label))


def raise_alarm(client: httpx.Client, workflow: str, run_url: str, now: datetime) -> str:
    """Açık alarm yoksa etiketli issue açar; varsa YALNIZ gövdesini günceller.

    Yeni issue ve yorum bildirim üretir, gövde düzenlemesi üretmez: kırmızı sürerken her
    turun (15 dakikada bir) e-postası gerçek alarmı gürültüye gömerdi.
    """
    body = (
        f"Son kırmızı tur: {run_url}\n"
        f"Zaman: {now:%Y-%m-%d %H:%M} UTC\n\n"
        "Yeşil bir tur bu issue'yu kendiliğinden kapatır. Prosedür: docs/RUNBOOK.md §3.\n"
    )
    numbers = _open_alarms(client, workflow)
    for number in numbers:
        _json(client.patch(f"/issues/{number}", json={"body": body}))
    if numbers:
        return f"alarm güncellendi: {_title(workflow)} {_numbers(numbers)}\n"
    _ensure_label(client)
    issue = {"title": _title(workflow), "body": body, "labels": [LABEL]}
    opened: dict[str, Any] = _json(client.post("/issues", json=issue))
    return f"alarm açıldı: {_title(workflow)} #{opened['number']}\n"


def clear_alarm(client: httpx.Client, workflow: str, run_url: str) -> str:
    """Açık alarm varsa "yeşile döndü" yorumu yazıp kapatır; yoksa hiçbir şey yazmaz."""
    numbers = _open_alarms(client, workflow)
    for number in numbers:
        comment = {"body": f"yeşile döndü: {run_url}"}
        _json(client.post(f"/issues/{number}/comments", json=comment))
        closing = {"state": "closed", "state_reason": "completed"}
        _json(client.patch(f"/issues/{number}", json=closing))
    if not numbers:
        return f"açık alarm yok: {_title(workflow)}\n"
    return f"alarm kapandı: {_title(workflow)} {_numbers(numbers)}\n"


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


def watchdog(client: httpx.Client, now: datetime) -> list[str]:
    """Bayat tetiklerin satırları; boş liste iki tetiğin de canlı olduğu demektir."""
    return [line for trigger in TRIGGERS if (line := _staleness(client, trigger, now)) is not None]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="seal/snapshot alarmı ve dispatch bekçisi")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("fail", "ok"):
        command = commands.add_parser(name)
        command.add_argument("--workflow", required=True)
        command.add_argument("--run-url", required=True)
    commands.add_parser("watchdog")
    return parser


def _execute(args: argparse.Namespace, client: httpx.Client, now: datetime) -> int:
    if args.command == "fail":
        sys.stdout.write(raise_alarm(client, args.workflow, args.run_url, now))
        return 0
    if args.command == "ok":
        sys.stdout.write(clear_alarm(client, args.workflow, args.run_url))
        return 0
    problems = watchdog(client, now)
    # `::error::` satırı turun özet sayfasına düşer: alarmdaki bağlantıyı açan hemen görür.
    report = "".join(f"::error::{line}\n" for line in problems)
    sys.stdout.write(report or "bekçi: dispatch ve snapshot taze\n")
    return 1 if problems else 0


def main(
    argv: Sequence[str] | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
    now: datetime | None = None,
) -> int:
    args = _parser().parse_args(argv)
    env = {name: os.environ.get(name, "") for name in ("GITHUB_TOKEN", "GITHUB_REPOSITORY")}
    missing = [name for name, value in env.items() if not value]
    if missing:
        sys.stderr.write(f"HATA: ortamda yok: {', '.join(missing)}\n")
        return 2
    try:
        with _client(env["GITHUB_REPOSITORY"], env["GITHUB_TOKEN"], transport) as client:
            return _execute(args, client, now or datetime.now(UTC))
    except httpx.HTTPError as error:
        # Alarm yolu düştüyse adım da düşer: sessizce "tamam" sayılmaz.
        sys.stderr.write(f"HATA: GitHub API çağrısı düştü — {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
