"""Kırmızı tur alarmı, pg_cron dispatch ve Odds API kredi bekçisi — `scripts/ops_alert.py`.

Ne GitHub'a ne Odds API'ye çıkılır: `httpx.MockTransport` üstünde küçük bir sahte GitHub gelen
istekleri kaydeder ve kendi durumunu (issue, etiket, tur) günceller; assertion'lar o duruma
bakar. Bekçinin kredi isteği host'una göre sahte bir Odds API'ye gider. Betik, workflow
adımının çağırdığı yoldan — `main(argv)` — sınanır.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
from collections.abc import Callable, Iterator
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
ODDS_KEY = "sahte-odds-anahtari-c5-0123456789"
# URL'de kodlanan karakter taşır (`+` → `%2B`): istekte düz ya da kırpılmış hâli hiç görünmez.
SYMBOL_KEY = "sahte+odds+anahtari+c5"
NOW = datetime(2026, 9, 22, 8, 15, tzinfo=UTC)
RUN_URL = "https://github.com/sahip/football-edge/actions/runs/42"
SEAL_ALARM = "🔴 seal kırmızı"
SNAPSHOT_ALARM = "🔴 snapshot kırmızı"
WATCHDOG_ALARM = "🔴 bekçi kırmızı"
MAC_ALARM = "🔴 footystats-local kırmızı"


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


@dataclass
class FakeOddsApi:
    """Kota harcamayan `GET /v4/sports`un taklidi: kalan kredi `x-requests-remaining`da, bu
    çağrının bedeli `x-requests-last`tedir (gerçek uçta 0).

    `None` verilen başlık hiç gönderilmez; `failure` verilirse her istek o yoldan düşer.
    Yanlış uç ya da anahtar, gerçek API gibi 401 alır — sessiz geçmez.
    """

    remaining: str | None = "200"
    last: str | None = "0"
    failure: Callable[[httpx.Request], httpx.Response] | None = None
    requests: list[httpx.Request] = field(default_factory=list)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.failure is not None:
            return self.failure(request)
        endpoint = (request.method, request.url.path) == ("GET", "/v4/sports")
        if not endpoint or request.url.params.get("apiKey") != ODDS_KEY:
            return httpx.Response(401, json={"message": "API key is not valid"})
        quota = {"x-requests-remaining": self.remaining, "x-requests-last": self.last}
        headers = {name: value for name, value in quota.items() if value is not None}
        return httpx.Response(200, headers=headers, json=[])


def _hosts(github: FakeGitHub, odds: FakeOddsApi) -> Callable[[httpx.Request], httpx.Response]:
    """Bekçi iki API'ye çıkar: istek, host'una göre ilgili taklide gider."""

    def route(request: httpx.Request) -> httpx.Response:
        return odds(request) if request.url.host == "api.the-odds-api.com" else github(request)

    return route


@pytest.fixture(autouse=True)
def _step_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runner `GITHUB_REPOSITORY`yi kendisi verir; `GITHUB_TOKEN`ı ve bekçinin `ODDS_API_KEY`ini
    adımın `env`i verir. Anahtar sahtedir: kabukta gerçeği tanımlı olsa bile ezilir."""
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("ODDS_API_KEY", ODDS_KEY)


@pytest.fixture(autouse=True)
def _http_log_levels() -> Iterator[None]:
    """`main` httpx/httpcore loglarını süreç genelinde kısar: bu, başka testlere taşmasın."""
    loggers = [logging.getLogger(name) for name in ("httpx", "httpcore")]
    levels = [logger.level for logger in loggers]
    yield
    for logger, level in zip(loggers, levels, strict=True):
        logger.setLevel(level)


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
# sınırın iki yanından sınanır: seal 59/61 dk, snapshot ve collect-daily 29/31 sa,
# collect-news 3 sa 59 dk/4 sa 1 dk, footystats-local (Mac'in kalp atışı, R74) 71/73 sa,
# history 7 gün 23 sa/8 gün 1 sa.

FRESH = {
    "seal.yml": [_workflow_run("workflow_dispatch", timedelta(minutes=59))],
    "snapshot.yml": [_workflow_run("workflow_dispatch", timedelta(hours=29))],
    "collect-daily.yml": [_workflow_run("workflow_dispatch", timedelta(hours=29))],
    "collect-news.yml": [_workflow_run("workflow_dispatch", timedelta(hours=3, minutes=59))],
    "footystats-local.yml": [_workflow_run("workflow_dispatch", timedelta(hours=71))],
    "history.yml": [_workflow_run("workflow_dispatch", timedelta(days=7, hours=23))],
}
STALE_SNAPSHOT = [_workflow_run("workflow_dispatch", timedelta(hours=31))]


def _watchdog(fake: FakeGitHub, odds: FakeOddsApi | None = None, *argv: str) -> int:
    """Kredisi verilmeyen tur yeterli krediyle (200) koşar: tetik testleri krediye bakmaz."""
    wire = _hosts(fake, odds if odds is not None else FakeOddsApi())
    return _main(wire, "watchdog", "--run-url", RUN_URL, *argv)


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
    ("workflow", "age", "needles"),
    [
        (
            "collect-daily.yml",
            timedelta(hours=31),
            ("son tur 31 sa 0 dk önce", "eşik 30 sa 0 dk", "collect-daily-dispatch"),
        ),
        (
            "collect-news.yml",
            timedelta(hours=4, minutes=1),
            ("son tur 4 sa 1 dk önce", "eşik 4 sa 0 dk", "collect-news-dispatch"),
        ),
    ],
    ids=["collect-daily", "collect-news"],
)
def test_a_stale_collect_trigger_is_named_in_the_watchdog_alarm(
    workflow: str, age: timedelta, needles: tuple[str, ...]
) -> None:
    """Toplayıcıların tek tetiği pg_cron'dur (0005): durursa geriye bu alarm kalır."""
    fake = FakeGitHub(runs={**FRESH, workflow: [_workflow_run("workflow_dispatch", age)]})

    assert _watchdog(fake) == 0

    (alarm,) = fake.issues
    assert alarm["title"] == WATCHDOG_ALARM
    for needle in (f"{workflow}: ", *needles):
        assert needle in alarm["body"], f"gövdede teşhis eksik: {needle!r}"


def test_collect_triggers_just_inside_their_thresholds_are_read_and_stay_fresh() -> None:
    """FRESH, toplayıcıları eşiklerinin hemen içinde tutar (29 sa, 3 sa 59 dk). Okunmamış bir
    tetik de alarm yazmaz: turların GERÇEKTEN sorulduğu ayrıca doğrulanır."""
    fake = FakeGitHub(runs=FRESH)

    assert _watchdog(fake) == 0

    assert fake.writes == [], "eşiğin içindeki toplayıcı alarm yazdı"
    asked = {path for method, path in fake.requests if method == "GET"}
    for workflow in ("collect-daily.yml", "collect-news.yml", "footystats-local.yml"):
        assert f"/actions/workflows/{workflow}/runs" in asked, f"{workflow} izlenmiyor"


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


@pytest.mark.parametrize(
    ("runs", "needles"),
    [
        (
            [_workflow_run("workflow_dispatch", timedelta(hours=73))],
            ("son workflow_dispatch turu 73 sa 0 dk önce", "eşik 72 sa 0 dk", "RUNBOOK §3.9"),
        ),
        ([], ("footystats-local.yml: hiç workflow_dispatch turu yok",)),
    ],
    ids=["73-sa", "hic-rapor"],
)
def test_a_silent_mac_opens_its_own_alarm_not_the_watchdogs(
    runs: list[dict[str, Any]], needles: tuple[str, ...]
) -> None:
    """Mac'in kalp atışı (R74) bekçi alarmını PAYLAŞMAZ: tatilde açık kalan bir bekçi alarmı,
    sonradan ölen bir mühür tetiğini yalnız gövde güncellemesiyle, yani bildirimsiz bırakırdı."""
    fake = FakeGitHub(runs={**FRESH, "footystats-local.yml": runs})

    assert _watchdog(fake) == 0

    (alarm,) = fake.issues
    assert alarm["title"] == MAC_ALARM
    for needle in needles:
        assert needle in alarm["body"], f"gövdede teşhis eksik: {needle!r}"


def test_a_dead_seal_trigger_still_notifies_while_the_mac_is_away() -> None:
    """Mac'in alarmı zaten açıkken mühür tetiği ölürse bekçi alarmı YENİ bir issue olarak açılır
    (bildirim üretir); Mac'in alarmına yalnız gövde düzenlemesi düşer."""
    mac_alarm = _issue(3, MAC_ALARM, body="Mac raporlamıyor")
    runs = {
        **FRESH,
        "seal.yml": [_workflow_run("workflow_dispatch", timedelta(minutes=61))],
        "footystats-local.yml": [_workflow_run("workflow_dispatch", timedelta(hours=100))],
    }
    fake = FakeGitHub(issues=[mac_alarm], runs=runs)

    assert _watchdog(fake) == 0

    assert ("POST", "/issues") in fake.writes, "bekçi alarmı açılmadı"
    watchdog_alarm = next(issue for issue in fake.issues if issue["title"] == WATCHDOG_ALARM)
    assert "seal.yml" in watchdog_alarm["body"]
    assert "footystats-local.yml" not in watchdog_alarm["body"]


def test_a_fresh_heartbeat_leaves_the_macs_alarm_to_its_ok_report() -> None:
    """Açık Mac alarmı kırmızı bir toplayıcı raporundan da gelebilir: onu kapatmak yalnız işin
    yeşil (`ok`) raporunun işidir. Bekçi taze kalp atışında ona dokunmaz."""
    mac_alarm = _issue(3, MAC_ALARM, body="fetch-footystats exit 3")
    fake = FakeGitHub(issues=[mac_alarm], runs=FRESH)

    assert _watchdog(fake) == 0

    assert fake.issue(3) == mac_alarm
    assert fake.writes == []


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
    """Bekçi alarmını YALNIZ tüm tetikleri taze bulan bir bekçi turu kapatır."""
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


# ── watchdog: Odds API kredisi ──────────────────────────────────────────────────────────────
# Kredi tükenince mühür turu `EXIT_QUOTA_EXHAUSTED` (2) verir; o an mühür çoktan kaçmıştır.
# Bekçi kalanı kota harcamayan `/v4/sports`un `x-requests-remaining` başlığından önceden okur
# ve sorunu kendi alarmına yazar. Eşik sınırın iki yanından sınanır (60/59).


@pytest.mark.parametrize("remaining", ["200", "60"], ids=["bol", "esikte"])
def test_enough_credit_is_measured_and_stays_out_of_the_diagnosis(remaining: str) -> None:
    fake, odds = FakeGitHub(runs=FRESH), FakeOddsApi(remaining=remaining)

    assert _watchdog(fake, odds) == 0

    assert fake.writes == [], "yeterli kredi alarm yazdı"
    (request,) = odds.requests  # ölçülmemiş kredi "yeterli" sayılamaz
    assert (request.method, request.url.path) == ("GET", "/v4/sports"), "kota harcayan uç"
    assert request.url.params.get("apiKey") == ODDS_KEY
    assert "authorization" not in request.headers, "GitHub token'ı Odds API'ye gitti"


@pytest.mark.parametrize(
    ("remaining", "argv", "line"),
    [
        ("59", (), "kredi az: 59 kaldı (eşik 60)"),
        ("40", (), "kredi az: 40 kaldı (eşik 60)"),
        ("80", ("--min-credits", "100"), "kredi az: 80 kaldı (eşik 100)"),
    ],
    ids=["esigin-alti", "az", "min-credits"],
)
def test_low_credit_opens_the_watchdog_alarm_and_the_step_stays_green(
    remaining: str, argv: tuple[str, ...], line: str, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGitHub(runs=FRESH)

    assert _watchdog(fake, FakeOddsApi(remaining=remaining), *argv) == 0, "kredi job'ı düşürdü"

    (alarm,) = fake.issues
    assert alarm["title"] == WATCHDOG_ALARM
    assert f"Odds API: {line}" in alarm["body"], "gövdede kredi teşhisi yok"
    assert f"::warning::Odds API: {line}" in capsys.readouterr().out, "tur özetinde uyarı yok"


def test_low_credit_keeps_the_open_watchdog_alarm_open() -> None:
    """Tetikler taze diye alarm kapanmaz: onu yalnız her şeyi yolunda bulan bekçi turu kapatır."""
    fake = FakeGitHub(issues=[_issue(4, WATCHDOG_ALARM, body="eski teşhis")], runs=FRESH)

    assert _watchdog(fake, FakeOddsApi(remaining="40")) == 0

    assert fake.writes == [("PATCH", "/issues/4")], "kredi az iken alarm kapandı ya da çoğaldı"
    assert fake.issue(4)["state"] == "open"
    assert "kredi az: 40 kaldı (eşik 60)" in fake.issue(4)["body"]


@pytest.mark.parametrize("remaining", [None, "bilinmiyor"], ids=["baslik-yok", "sayi-degil"])
def test_an_unreadable_credit_header_is_named_unmeasured(remaining: str | None) -> None:
    """Ölçülemeyen kredi "yeterli" sayılmaz: bekçi onu adıyla alarma yazar."""
    fake = FakeGitHub(runs=FRESH)

    assert _watchdog(fake, FakeOddsApi(remaining=remaining)) == 0

    (alarm,) = fake.issues
    assert alarm["title"] == WATCHDOG_ALARM
    for needle in ("Odds API: kredi ÖLÇÜLEMEDİ", "x-requests-remaining"):
        assert needle in alarm["body"], f"gövdede teşhis eksik: {needle!r}"


@pytest.mark.parametrize("value", [None, ""], ids=["tanimsiz", "bos-secret"])
def test_a_missing_key_is_named_unmeasured_without_a_request(
    value: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tanımsız repo secret'ı adımın `env`ine boş dize olarak gelir: o da "anahtar yok"tur."""
    if value is None:
        monkeypatch.delenv("ODDS_API_KEY")
    else:
        monkeypatch.setenv("ODDS_API_KEY", value)
    fake, odds = FakeGitHub(runs=FRESH), FakeOddsApi()

    assert _watchdog(fake, odds) == 0

    assert odds.requests == [], "anahtarsız istek atıldı"
    (alarm,) = fake.issues
    for needle in ("Odds API: kredi ÖLÇÜLEMEDİ", "ODDS_API_KEY"):
        assert needle in alarm["body"], f"gövdede teşhis eksik: {needle!r}"


def _unauthorized(request: httpx.Request) -> httpx.Response:
    return httpx.Response(401, json={"message": "API key is not valid"})


def _connection_lost(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError(f"bağlantı koptu: {request.url}", request=request)


def _echoes_the_key(request: httpx.Request) -> httpx.Response:
    raise httpx.ProxyError(f"vekil reddetti: {request.url.params['apiKey']}", request=request)


def _key_in_reason_phrase(request: httpx.Request) -> httpx.Response:
    # Sunucu anahtarı durum satırında yankılar; durum satırı satır sonu taşıyamaz.
    echoed = request.url.params["apiKey"].strip()
    return httpx.Response(401, extensions={"reason_phrase": f"Invalid key {echoed}".encode()})


def _redirect_with_lowercase_apikey(request: httpx.Request) -> httpx.Response:
    # httpx yönlendirmeyi izlemez ama `Location`ı hata mesajına koyar.
    query = request.url.query.decode().replace("apiKey=", "apikey=")
    location = f"https://api.the-odds-api.com/v4/sports/?{query}"
    return httpx.Response(302, headers={"Location": location})


def _url_form(secret: str) -> str:
    """Anahtarın istek sorgusundaki hâli — httpx'in kendi kodlaması."""
    return str(httpx.QueryParams({"apiKey": secret})).partition("=")[2]


@pytest.mark.parametrize(
    ("secret", "failure", "reason"),
    [
        (ODDS_KEY, _unauthorized, "401 Unauthorized"),
        (ODDS_KEY, _connection_lost, "ConnectError"),
        (f"{ODDS_KEY}\n", _unauthorized, "401 Unauthorized"),
        (ODDS_KEY, _echoes_the_key, "ProxyError"),
        (f"{ODDS_KEY}\n", _key_in_reason_phrase, "401 Invalid key"),
        (f"{SYMBOL_KEY}\n", _redirect_with_lowercase_apikey, "302 Found"),
        (" ", _unauthorized, "401 Unauthorized"),
    ],
    ids=[
        "http-401",
        "ag-hatasi",
        "satir-sonlu-secret",
        "duz-anahtar",
        "durum-satirinda-kirpilmis-anahtar",
        "yonlendirmede-kucuk-harf-apikey",
        "yalniz-bosluk-secret",
    ],
)
def test_a_failed_credit_request_is_named_without_leaking_the_key(
    secret: str,
    failure: Callable[[httpx.Request], httpx.Response],
    reason: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """httpx'in hata mesajı isteğin URL'sini, yani sorgudaki anahtarı taşır ve httpx her isteği
    INFO'da URL'siyle loglar. Satır sonuyla yapıştırılmış secret URL'de `%0A` olur, çıplak hâli
    durum satırında görünebilir; kodlanan karakter taşıyan anahtar yönlendirmenin küçük harfli
    `apikey=` yankısına düşer. Teşhis PUBLIC issue'ya yazılır ve GitHub'ın secret maskelemesi
    issue'yu kapsamaz: anahtar hiçbir yoldan — log dâhil — çıkmamalı. İstekteki anahtar
    KIRPILMAZ: bekçi seal'in düşeceği gibi düşmeli. Hata yine adıyla, tek satırda raporlanır;
    yalnız boşluktan oluşan secret raporu bozmaz."""
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("ODDS_API_KEY", secret)
    fake, odds = FakeGitHub(runs=FRESH), FakeOddsApi(failure=failure)

    assert _watchdog(fake, odds) == 0, "kredi hatası job'ı düşürdü"

    (request,) = odds.requests
    assert request.url.params["apiKey"] == secret, "istekteki anahtar kırpıldı"
    out = capsys.readouterr()
    written = json.dumps([fake.issues, fake.comments], ensure_ascii=False)
    channels = {"stdout": out.out, "stderr": out.err, "GitHub": written, "log": caplog.text}
    bare = secret.strip()
    for form in {form for form in (bare, _url_form(bare)) if form}:
        for channel, text in channels.items():
            assert form not in text, f"anahtar {channel} yoluyla sızdı: {form!r}"
    for name in ("httpx", "httpcore"):
        level = logging.getLogger(name).getEffectiveLevel()
        assert level >= logging.WARNING, f"{name} INFO/DEBUG loglar: istek URL'si anahtarı taşır"
    (alarm,) = fake.issues
    for needle in ("Odds API: kredi ÖLÇÜLEMEDİ", reason):
        assert needle in alarm["body"], f"gövdede teşhis eksik: {needle!r}"
    for printed in out.out.splitlines():
        assert printed.startswith(("::warning::", "alarm ")), f"uyarı satırı bölündü: {printed!r}"


@pytest.mark.parametrize("last", ["0", None], ids=["ucretsiz", "baslik-yok"])
def test_a_free_or_unreported_measurement_stays_out_of_the_diagnosis(last: str | None) -> None:
    fake, odds = FakeGitHub(runs=FRESH), FakeOddsApi(last=last)

    assert _watchdog(fake, odds) == 0

    assert len(odds.requests) == 1, "kredi ölçülmedi"
    assert fake.writes == [], "ücretsiz ölçüm alarm yazdı"


def test_a_charged_measurement_is_named_in_the_watchdog_alarm(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Her yanıt kendi bedelini `x-requests-last`te taşır. Ücretsiz sanılan uç kredi yiyorsa
    bekçi her turda sessizce kredi tüketirdi: ölçümün bedeli teşhise girer."""
    fake = FakeGitHub(runs=FRESH)

    assert _watchdog(fake, FakeOddsApi(last="1")) == 0

    line = "kredi ölçümü ücretli: x-requests-last=1 — /v4/sports ücretsiz sanılıyordu"
    (alarm,) = fake.issues
    assert f"Odds API: {line}" in alarm["body"], "gövdede ölçümün bedeli yok"
    assert f"::warning::Odds API: {line}" in capsys.readouterr().out, "tur özetinde uyarı yok"


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


def test_every_watched_workflow_exists() -> None:
    """Bekçi depoda olmayan bir workflow'un tur listesini sorarsa GitHub 404 döner, bekçi adımı
    ve onunla seal turu düşer. Ad değişikliği ya da silinen workflow runner'da değil CI'da
    yakalansın."""
    missing = [
        trigger.workflow
        for trigger in ops_alert.TRIGGERS
        if not (REPO / ".github/workflows" / trigger.workflow).is_file()
    ]

    assert missing == [], f"bekçi olmayan workflow'u izliyor (GitHub 404 → adım düşer): {missing}"


def test_a_stale_history_trigger_is_named_in_the_watchdog_alarm() -> None:
    """Tarihsel tabanın tek tetiği pg_cron'dur (0008, haftada bir): durursa geriye bu alarm kalır.
    FRESH onu eşiğin hemen içinde tutar (7 gün 23 sa); bir saat sonrası bayattır."""
    stale = [_workflow_run("workflow_dispatch", timedelta(days=8, hours=1))]
    fake = FakeGitHub(runs={**FRESH, "history.yml": stale})

    assert _watchdog(fake) == 0

    (alarm,) = fake.issues
    assert alarm["title"] == WATCHDOG_ALARM
    for needle in ("history.yml: ", "history-dispatch"):
        assert needle in alarm["body"], f"gövdede teşhis eksik: {needle!r}"
