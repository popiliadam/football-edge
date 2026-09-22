"""Kırmızı tur alarmı ve pg_cron dispatch bekçisi — `scripts/ops_alert.py`.

GitHub'a hiç çıkılmaz: `httpx.MockTransport` üstünde küçük bir sahte GitHub gelen istekleri
kaydeder ve kendi durumunu (issue, etiket, tur) günceller; assertion'lar o duruma bakar.
Betik, workflow adımının çağırdığı yoldan — `main(argv)` — sınanır.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

REPO = Path(__file__).resolve().parent.parent
REPOSITORY = "sahip/football-edge"
TOKEN = "test-token"
NOW = datetime(2026, 9, 22, 8, 15, tzinfo=UTC)
RUN_URL = "https://github.com/sahip/football-edge/actions/runs/42"
SEAL_ALARM = "🔴 seal kırmızı"
SNAPSHOT_ALARM = "🔴 snapshot kırmızı"
WATCHDOG_ALARM = "🔴 bekçi kırmızı"


def _load_script() -> ModuleType:
    """`scripts/` bir paket değil: workflow'un koştuğu dosya kendi yolundan yüklenir."""
    spec = importlib.util.spec_from_file_location("ops_alert", REPO / "scripts/ops_alert.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass, modülünü sys.modules'ta arar
    spec.loader.exec_module(module)
    return module


ops_alert = _load_script()


def _issue(number: int, title: str, *, state: str = "open", body: str = "") -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "labels": [{"name": "ops-alert"}],
    }


def _workflow_run(event: str, age: timedelta) -> dict[str, Any]:
    return {"event": event, "created_at": f"{NOW - age:%Y-%m-%dT%H:%M:%SZ}"}


@dataclass
class FakeGitHub:
    """Betiğin kullandığı REST uçlarının taklidi; tanımadığı istek 404 alır, sessiz geçmez.

    Gerçek GitHub'dan TEK kasıtlı farkı: olmayan etiketle issue açmayı 422 ile reddeder —
    "etiket yoksa önce oluştur" kuralı bu yoldan zorlanır.
    """

    issues: list[dict[str, Any]] = field(default_factory=list)
    labels: frozenset[str] = frozenset({"ops-alert"})
    runs: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    comments: list[tuple[int, str]] = field(default_factory=list)
    requests: list[tuple[str, str]] = field(default_factory=list)

    @property
    def writes(self) -> list[tuple[str, str]]:
        return [(method, path) for method, path in self.requests if method != "GET"]

    def issue(self, number: int) -> dict[str, Any]:
        return next(issue for issue in self.issues if issue["number"] == number)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        prefix = f"/repos/{REPOSITORY}/"
        path = request.url.path.removeprefix(prefix[:-1])
        self.requests.append((request.method, path))
        if request.url.host != "api.github.com" or not request.url.path.startswith(prefix):
            return httpx.Response(404, json={"message": "Not Found"})
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return httpx.Response(401, json={"message": "Bad credentials"})
        payload = json.loads(request.content) if request.content else {}
        return self._route(request.method, path.strip("/").split("/"), request.url.params, payload)

    def _route(
        self, method: str, parts: list[str], params: httpx.QueryParams, payload: dict[str, Any]
    ) -> httpx.Response:
        match method, parts:
            case "GET", ["issues"]:
                return self._list_issues(params)
            case "POST", ["issues"]:
                return self._open_issue(payload)
            case "PATCH", ["issues", number]:
                return self._edit_issue(int(number), payload)
            case "POST", ["issues", number, "comments"]:
                self.comments.append((int(number), payload["body"]))
                return httpx.Response(201, json={"id": len(self.comments)})
            case "GET", ["labels", name]:
                return httpx.Response(200 if name in self.labels else 404, json={"name": name})
            case "POST", ["labels"]:
                self.labels = self.labels | {payload["name"]}
                return httpx.Response(201, json={"name": payload["name"]})
            case "GET", ["actions", "workflows", workflow, "runs"]:
                return self._list_runs(workflow, params)
        return httpx.Response(404, json={"message": "Not Found"})

    def _list_issues(self, params: httpx.QueryParams) -> httpx.Response:
        state = params.get("state", "open")
        wanted = {name for name in params.get("labels", "").split(",") if name}
        listed = [
            issue
            for issue in self.issues
            if state in ("all", issue["state"])
            and wanted <= {label["name"] for label in issue["labels"]}
        ]
        return httpx.Response(200, json=listed)

    def _open_issue(self, payload: dict[str, Any]) -> httpx.Response:
        missing = sorted(set(payload.get("labels", [])) - self.labels)
        if missing:
            return httpx.Response(422, json={"message": f"etiket yok: {missing}"})
        issue = {
            "number": max((issue["number"] for issue in self.issues), default=0) + 1,
            "title": payload["title"],
            "body": payload.get("body", ""),
            "state": "open",
            "labels": [{"name": name} for name in payload.get("labels", [])],
        }
        self.issues = [*self.issues, issue]
        return httpx.Response(201, json=issue)

    def _edit_issue(self, number: int, payload: dict[str, Any]) -> httpx.Response:
        if all(issue["number"] != number for issue in self.issues):
            return httpx.Response(404, json={"message": "Not Found"})
        self.issues = [
            {**issue, **payload} if issue["number"] == number else issue for issue in self.issues
        ]
        return httpx.Response(200, json=self.issue(number))

    def _list_runs(self, workflow: str, params: httpx.QueryParams) -> httpx.Response:
        event = params.get("event")
        matching = [run for run in self.runs.get(workflow, []) if event in (None, run["event"])]
        newest_first = sorted(matching, key=lambda run: run["created_at"], reverse=True)
        page = newest_first[: int(params.get("per_page", 30))]
        return httpx.Response(200, json={"total_count": len(matching), "workflow_runs": page})


@pytest.fixture(autouse=True)
def _github_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runner `GITHUB_REPOSITORY`yi kendisi verir; `GITHUB_TOKEN`ı adımın `env`i verir."""
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)


def _main(handler: Callable[[httpx.Request], httpx.Response], *argv: str) -> int:
    code: int = ops_alert.main(list(argv), transport=httpx.MockTransport(handler), now=NOW)
    return code


def _fail(fake: FakeGitHub) -> int:
    return _main(fake, "fail", "--workflow", "seal", "--run-url", RUN_URL)


def _ok(fake: FakeGitHub) -> int:
    return _main(fake, "ok", "--workflow", "seal", "--run-url", RUN_URL)


# ── fail: kırmızı tur ───────────────────────────────────────────────────────────────────────


def test_fail_opens_a_labelled_alarm_with_the_run_link_and_utc_time() -> None:
    """Açık alarm yoksa issue AÇILIR: oluşturma bildirimi depo sahibine gider. Başka
    workflow'un ve bekçinin açık alarmları bu turun alarmı sayılmaz, dokunulmaz."""
    others = [
        _issue(1, SNAPSHOT_ALARM, body="snapshot turu"),
        _issue(2, WATCHDOG_ALARM, body="bekçi teşhisi"),
    ]
    fake = FakeGitHub(issues=list(others))

    assert _fail(fake) == 0

    assert fake.writes == [("POST", "/issues")], "tam olarak bir issue açılmalıydı"
    opened = fake.issue(3)
    assert opened["title"] == SEAL_ALARM
    assert opened["state"] == "open"
    assert [label["name"] for label in opened["labels"]] == ["ops-alert"]
    assert RUN_URL in opened["body"], "gövde kırmızı tura bağlanmıyor"
    assert "2026-09-22 08:15 UTC" in opened["body"], "gövde UTC zamanını taşımıyor"
    assert fake.issues[:2] == others, "başka bir alarma dokunuldu"


def test_fail_creates_the_missing_label_before_opening_the_alarm() -> None:
    fake = FakeGitHub(labels=frozenset())

    assert _fail(fake) == 0

    assert fake.writes == [("POST", "/labels"), ("POST", "/issues")]
    assert "ops-alert" in fake.labels


def test_fail_only_edits_the_body_of_an_alarm_that_is_already_open() -> None:
    """Kırmızı sürerken her tur (15 dakikada bir) yeni issue ya da yorum açsaydı her biri
    bildirim olurdu — gürültü gerçek alarmı gömer. Gövde düzenlemesi bildirim üretmez."""
    fake = FakeGitHub(issues=[_issue(7, SEAL_ALARM, body="eski tur")])

    assert _fail(fake) == 0

    assert fake.writes == [("PATCH", "/issues/7")], "açık alarm varken yeni kayıt yazıldı"
    assert RUN_URL in fake.issue(7)["body"], "gövde son tura işaret etmiyor"
    assert fake.issue(7)["state"] == "open"
    assert len(fake.issues) == 1


# ── ok: yeşil tur ───────────────────────────────────────────────────────────────────────────


def test_ok_comments_and_closes_the_open_alarm() -> None:
    fake = FakeGitHub(issues=[_issue(7, SEAL_ALARM)])

    assert _ok(fake) == 0

    assert fake.comments == [(7, f"yeşile döndü: {RUN_URL}")]
    assert fake.issue(7)["state"] == "closed"


def test_ok_without_an_open_alarm_writes_nothing() -> None:
    """Yeşil turların neredeyse hepsi bu yoldan geçer: hiçbir yazma yok. Başka workflow'un
    açık alarmı da, bu workflow'un kapanmış eski alarmı da olduğu gibi kalır."""
    fake = FakeGitHub(issues=[_issue(3, SEAL_ALARM, state="closed"), _issue(5, SNAPSHOT_ALARM)])

    assert _ok(fake) == 0

    assert fake.writes == []
    assert fake.issue(5)["state"] == "open"


# ── watchdog: pg_cron tetikleri canlı mı? ───────────────────────────────────────────────────
# Bekçinin raporu KENDİ issue'sudur (`🔴 bekçi kırmızı`) ve adım bayat tetikte de 0 döner:
# seal job'ını düşürseydi seal'in sonraki yeşil turu (≤15 dk) alarmı geri alırdı. Eşikler
# sınırın iki yanından sınanır (59/61 dk, 29/31 sa).

FRESH = {
    "seal.yml": [_workflow_run("workflow_dispatch", timedelta(minutes=59))],
    "snapshot.yml": [_workflow_run("workflow_dispatch", timedelta(hours=29))],
}
STALE_SNAPSHOT = [_workflow_run("workflow_dispatch", timedelta(hours=31))]


def _watchdog(fake: FakeGitHub) -> int:
    return _main(fake, "watchdog", "--run-url", RUN_URL)


def test_fresh_watchdog_without_an_open_alarm_writes_nothing() -> None:
    fake = FakeGitHub(runs=FRESH)

    assert _watchdog(fake) == 0
    assert fake.writes == []


def test_stale_dispatch_opens_the_watchdog_alarm_and_the_step_stays_green() -> None:
    """Taze bir `schedule` turu ölü dispatch'i ÖRTMEZ — bekçinin kendi turu da schedule'dır.
    Teşhis gövdededir; açık seal alarmına dokunulmaz."""
    seal_runs = [
        _workflow_run("schedule", timedelta(minutes=1)),
        _workflow_run("workflow_dispatch", timedelta(minutes=61)),
    ]
    seal_alarm = _issue(1, SEAL_ALARM, body="seal turu")
    fake = FakeGitHub(issues=[seal_alarm], runs={**FRESH, "seal.yml": seal_runs})

    assert _watchdog(fake) == 0, "bayat tetik seal job'ını düşürüyor"

    assert fake.writes == [("POST", "/issues")], "tam olarak bir issue açılmalıydı"
    alarm = fake.issue(2)
    assert alarm["title"] == WATCHDOG_ALARM
    assert [label["name"] for label in alarm["labels"]] == ["ops-alert"]
    for needle in ("seal.yml", "1 sa 1 dk", "eşik 1 sa 0 dk", "pg_cron dispatch", "RUNBOOK §3"):
        assert needle in alarm["body"], f"gövdede teşhis eksik: {needle!r}"
    assert RUN_URL in alarm["body"], "alarm bekçi turuna bağlanmıyor"
    assert fake.issue(1) == seal_alarm, "bekçi seal alarmına dokundu"


def test_stale_snapshot_is_named_in_the_watchdog_alarm() -> None:
    fake = FakeGitHub(runs={**FRESH, "snapshot.yml": STALE_SNAPSHOT})

    assert _watchdog(fake) == 0

    (alarm,) = fake.issues
    assert alarm["title"] == WATCHDOG_ALARM
    for needle in ("snapshot.yml", "31 sa 0 dk", "eşik 30 sa 0 dk"):
        assert needle in alarm["body"], f"gövdede teşhis eksik: {needle!r}"


@pytest.mark.parametrize(
    ("workflow", "runs"),
    [
        ("seal.yml", []),
        ("seal.yml", [_workflow_run("schedule", timedelta(minutes=1))]),
        ("snapshot.yml", []),
    ],
    ids=["seal-hic-tur", "seal-yalniz-schedule", "snapshot-hic-tur"],
)
def test_a_trigger_that_never_ran_opens_the_watchdog_alarm(
    workflow: str, runs: list[dict[str, Any]]
) -> None:
    """Hiç koşmamış tetik "bayat değil" sayılmaz: en bayat tetik odur."""
    fake = FakeGitHub(runs={**FRESH, workflow: runs})

    assert _watchdog(fake) == 0

    (alarm,) = fake.issues
    assert alarm["title"] == WATCHDOG_ALARM
    assert f"{workflow}: hiç" in alarm["body"]


def test_stale_watchdog_only_edits_the_body_of_its_open_alarm() -> None:
    fake = FakeGitHub(
        issues=[_issue(4, WATCHDOG_ALARM, body="eski teşhis")],
        runs={**FRESH, "snapshot.yml": STALE_SNAPSHOT},
    )

    assert _watchdog(fake) == 0

    assert fake.writes == [("PATCH", "/issues/4")], "açık bekçi alarmı varken yeni kayıt yazıldı"
    assert "snapshot.yml" in fake.issue(4)["body"], "gövde son teşhise işaret etmiyor"
    assert fake.issue(4)["state"] == "open"


def test_fresh_watchdog_closes_its_own_alarm_and_leaves_the_seal_alarm() -> None:
    """Bekçi alarmını YALNIZ iki tetiği de taze bulan bir bekçi turu kapatır."""
    fake = FakeGitHub(issues=[_issue(4, WATCHDOG_ALARM), _issue(5, SEAL_ALARM)], runs=FRESH)

    assert _watchdog(fake) == 0

    assert fake.comments == [(4, f"yeşile döndü: {RUN_URL}")]
    assert fake.issue(4)["state"] == "closed"
    assert fake.issue(5)["state"] == "open", "bekçi seal alarmını kapattı"


def test_green_seal_run_leaves_the_watchdog_alarm_open() -> None:
    """Seal'in yeşili snapshot'ın ölümünü ölçmez, bekçi alarmını kapatamaz: maçları yalnız
    snapshot kaydeder ve ölü snapshot mühürleri "kaçan" raporu bile vermeden susturur."""
    fake = FakeGitHub(issues=[_issue(4, WATCHDOG_ALARM)])

    assert _ok(fake) == 0

    assert fake.writes == []
    assert fake.issue(4)["state"] == "open"


# ── Hata yolları: alarm düşerse adım da düşer, sessizce "tamam" demez ──────────────────────


@pytest.mark.parametrize("missing", ["GITHUB_TOKEN", "GITHUB_REPOSITORY"])
def test_missing_environment_fails_before_calling_github(
    missing: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(missing)
    fake = FakeGitHub()

    assert _fail(fake) == 2
    assert fake.requests == []
    assert missing in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["fail", "--workflow", "seal", "--run-url", RUN_URL],
        ["ok", "--workflow", "seal", "--run-url", RUN_URL],
        ["watchdog", "--run-url", RUN_URL],
    ],
    ids=["fail", "ok", "watchdog"],
)
def test_a_github_error_fails_the_step_with_a_named_message(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Bekçi bayat tetikte bile 0 döner; ama GitHub API'nin kendisi düşerse her alt komut
    düşer — bozuk alarm yolu yeşil görünmemeli."""

    def down(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"message": "Bad Gateway"})

    assert _main(down, *argv) == 1
    assert "GitHub" in capsys.readouterr().err
