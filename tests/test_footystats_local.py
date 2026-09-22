"""Mac'teki günlük footystats işi (RUNBOOK §3.9): betik ve launchd tanımı.

GitHub runner'ları footystats'tan 403 alıyor (DEFERRED 10r); iş Mac'te launchd ile koşar ve
sonucu `footystats-local.yml`e raporlar (R74). Betik sahte `git`/`uv`/`gh`/`osascript` ile,
kurulu bir KOPYASI üzerinden koşulur: bir Mac'te gerçekten koştuğu burada ölçülmez.
"""

from __future__ import annotations

import importlib.util
import os
import plistlib
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts/footystats_daily.sh"
DB_PASSWORD = "pw-sentinel-7c1"
DATABASE_URL = f"postgresql://collector:{DB_PASSWORD}@db.test:5432/postgres"
GIT = "git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=60"
FETCH = f"{GIT} fetch --quiet origin main"
COLLECT = "uv run --frozen python -m football_edge.collect fetch-footystats"
REPORT = (
    "gh workflow run footystats-local.yml --repo popiliadam/football-edge --ref main -f result="
)

# `git`, `uv`, `gh` ve `osascript`in yerine geçer: her çağrıyı araç, argümanlar ve ortamdaki
# sırlarla bir satıra yazar. `FAIL_MATCH` ile başlayan çağrı `FAIL_CODE` ile döner — yalnız ilk
# `FAIL_TIMES` kez (boşsa her seferinde): uyanıştan sonra geç gelen ağ böyle taklit edilir.
FAKE_TOOL = """\
#!/usr/bin/env bash
tool=$(basename "$0")
printf '%s %s|db=%s|token=%s|odds=%s\\n' "$tool" "$*" "${DATABASE_URL:-}" \\
  "${GITHUB_TOKEN:+var}" "${ODDS_API_KEY:+var}" >> "$CALLS"
if [ -n "$FAIL_MATCH" ] && [[ "$tool $*" == "$FAIL_MATCH"* ]]; then
  seen=$(awk -v p="$FAIL_MATCH" 'index($0, p) == 1' "$CALLS" | wc -l)
  if [ -z "$FAIL_TIMES" ] || [ "$seen" -le "$FAIL_TIMES" ]; then exit "$FAIL_CODE"; fi
fi
if [ "$tool" = git ] && [[ " $* " == *" clone "* ]]; then mkdir -p "${@: -1}/.git"; fi
"""


@dataclass(frozen=True)
class Run:
    code: int
    output: str
    calls: tuple[str, ...]
    installed: Path
    stamp: Path

    def commands(self) -> tuple[str, ...]:
        return tuple(call.split("|")[0] for call in self.calls)

    def call(self, prefix: str) -> str:
        return next(call for call in self.calls if call.startswith(prefix))


def _today() -> str:
    return f"{datetime.now(UTC):%Y-%m-%d}"


def _run(
    tmp_path: Path,
    *,
    fail_match: str = "",
    fail_code: int = 1,
    fail_times: str = "",
    env_file_text: str = f"ODDS_API_KEY=odds-sentinel\nDATABASE_URL={DATABASE_URL}\n",
    stamp_text: str | None = None,
    clone_exists: bool = True,
    clone_script: str | None = None,
) -> Run:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("git", "uv", "gh", "osascript"):
        fake = bin_dir / tool
        fake.write_text(FAKE_TOOL, encoding="utf-8")
        fake.chmod(0o755)
    # launchd klonun DIŞINDAKİ kopyayı koşar; test de öyle yapar (depodaki dosyaya dokunulmaz).
    installed = tmp_path / "installed" / "footystats_daily.sh"
    installed.parent.mkdir()
    installed.write_bytes(SCRIPT.read_bytes())
    clone = tmp_path / "clone"
    if clone_exists:
        (clone / ".git").mkdir(parents=True)
    if clone_script is not None:
        (clone / "scripts").mkdir(parents=True)
        (clone / "scripts/footystats_daily.sh").write_text(clone_script, encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(env_file_text, encoding="utf-8")
    stamp = tmp_path / "state" / "footystats-last-run"
    if stamp_text is not None:
        stamp.parent.mkdir()
        stamp.write_text(stamp_text, encoding="utf-8")
    calls = tmp_path / "calls"
    calls.touch()
    env = {
        "PATH": f"{bin_dir}{os.pathsep}/usr/bin{os.pathsep}/bin",
        "HOME": str(tmp_path),
        "CALLS": str(calls),
        "FAIL_MATCH": fail_match,
        "FAIL_CODE": str(fail_code),
        "FAIL_TIMES": fail_times,
        "FOOTBALL_EDGE_CLONE": str(clone),
        "FOOTBALL_EDGE_ENV_FILE": str(env_file),
        "FOOTBALL_EDGE_STAMP": str(stamp),
        "FOOTBALL_EDGE_RETRY_DELAY": "0",
    }
    result = subprocess.run(
        ["bash", str(installed)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return Run(
        result.returncode,
        result.stdout + result.stderr,
        tuple(calls.read_text(encoding="utf-8").splitlines()),
        installed,
        stamp,
    )


def test_green_run_pulls_main_collects_reports_and_stamps_the_day(tmp_path: Path) -> None:
    """Sıra yük taşır: toplayıcı `main`in incelenmiş son hâlini koşar, yarım bir dalı değil."""
    run = _run(tmp_path)

    assert run.code == 0, run.output
    assert run.commands() == (
        FETCH,
        "git checkout --quiet --detach FETCH_HEAD",
        "git rev-parse --short HEAD",
        "uv sync --frozen --quiet",
        COLLECT,
        f"{REPORT}ok",
    )
    assert run.stamp.read_text(encoding="utf-8").strip() == _today()


def test_the_collector_gets_only_the_database_and_no_process_gets_a_token(tmp_path: Path) -> None:
    """GitHub'daki `collect-daily` ile aynı sınır: toplayıcı yalnız `DATABASE_URL`i görür (Odds
    anahtarı `.env`de dursa da); sır argümanda değil ortamda taşınır ve çıktıya düşmez. GitHub
    token'ı hiçbir sürecimize girmez: raporu `gh` kendi oturumuyla gönderir."""
    run = _run(tmp_path)

    assert run.call(COLLECT).endswith(f"|db={DATABASE_URL}|token=|odds=")
    assert run.call(REPORT).endswith("|db=|token=|odds=")
    assert not any(call.startswith("gh auth") for call in run.calls)
    assert DB_PASSWORD not in run.output
    assert all(DB_PASSWORD not in call.split("|")[0] for call in run.calls)


def test_a_red_collector_reports_fail_keeps_its_exit_code_and_still_stamps(
    tmp_path: Path,
) -> None:
    """Toplayıcı koştuysa bugünün denemesi budur (`collect-daily` gibi günde bir): kırmızı bir
    kaynak her dilimde yeniden istenmez."""
    run = _run(tmp_path, fail_match=COLLECT, fail_code=3)

    assert run.code == 3, run.output
    assert run.commands()[-1] == f"{REPORT}fail"
    assert f"{REPORT}ok" not in run.commands()
    assert run.stamp.read_text(encoding="utf-8").strip() == _today()


@pytest.mark.parametrize(
    "failing",
    [FETCH, "git checkout", "uv sync"],
    ids=["fetch", "checkout", "sync"],
)
def test_a_failure_before_collecting_reports_fail_and_leaves_the_day_open(
    tmp_path: Path, failing: str
) -> None:
    """Eski kodla toplanmaz; damga yazılmaz ki sonraki dilim yeniden denesin."""
    run = _run(tmp_path, fail_match=failing, fail_code=128)

    assert run.code != 0
    assert COLLECT not in run.commands()
    assert run.commands()[-1] == f"{REPORT}fail"
    assert not run.stamp.exists()


def test_fetch_is_retried_while_the_network_comes_back(tmp_path: Path) -> None:
    """launchd uykudan uyanınca kaçan turu hemen başlatır; ağ o an birkaç saniye yok olabilir."""
    run = _run(tmp_path, fail_match=FETCH, fail_code=128, fail_times="2")

    assert run.code == 0, run.output
    assert run.commands().count(FETCH) == 3
    assert COLLECT in run.commands()


def test_fetch_gives_up_after_six_attempts(tmp_path: Path) -> None:
    run = _run(tmp_path, fail_match=FETCH, fail_code=128)

    assert run.commands().count(FETCH) == 6
    assert run.commands()[-1] == f"{REPORT}fail"


def test_a_missing_clone_is_cloned_again(tmp_path: Path) -> None:
    run = _run(tmp_path, clone_exists=False)

    assert run.code == 0, run.output
    assert run.commands()[0] == (
        f"{GIT} clone --quiet https://github.com/popiliadam/football-edge.git {tmp_path / 'clone'}"
    )
    assert COLLECT in run.commands()


def test_without_github_the_run_stays_red_and_says_so_on_this_mac(tmp_path: Path) -> None:
    """Rapor iletilemiyorsa günlüğe yazılır ve bu Mac'te bildirim çıkar; kalp atışı eksik
    kalır, bekçi onu 72 saatte yakalar."""
    run = _run(tmp_path, fail_match="gh workflow run", fail_code=1)

    assert run.code == 0, "rapor gitmedi diye toplanan veri kırmızı sayılmaz"
    assert "GitHub'a iletilemedi" in run.output
    assert any(call.startswith("osascript -e display notification") for call in run.calls)


def test_a_missing_database_url_stops_before_collecting(tmp_path: Path) -> None:
    run = _run(tmp_path, env_file_text="ODDS_API_KEY=odds-sentinel\n")

    assert run.code != 0
    assert COLLECT not in run.commands()
    assert "DATABASE_URL" in run.output
    assert run.commands()[-1] == f"{REPORT}fail"


@pytest.mark.parametrize(
    "line",
    [
        f'DATABASE_URL="{DATABASE_URL}"',
        f"DATABASE_URL='{DATABASE_URL}'",
        f"DATABASE_URL={DATABASE_URL}\r",
    ],
    ids=["çift-tırnak", "tek-tırnak", "crlf"],
)
def test_the_database_url_reaches_the_collector_bare(tmp_path: Path, line: str) -> None:
    run = _run(tmp_path, env_file_text=f"{line}\n")

    assert run.code == 0, run.output
    assert run.call(COLLECT).endswith(f"|db={DATABASE_URL}|token=|odds=")


def test_a_day_that_already_ran_is_skipped_quietly(tmp_path: Path) -> None:
    """launchd günde dört kez ve oturum açılışında çağırır; tur UTC günü başına bir kez koşar."""
    run = _run(tmp_path, stamp_text=f"{_today()}\n")

    assert run.code == 0, run.output
    assert run.calls == ()


def test_yesterdays_stamp_does_not_skip_today(tmp_path: Path) -> None:
    run = _run(tmp_path, stamp_text="2000-01-01\n")

    assert COLLECT in run.commands()


def test_the_installed_copy_follows_main_from_the_next_run(tmp_path: Path) -> None:
    """Koşan kopya `main`in gerisindeyse kendini günceller. Yeni içerik bu turu değil
    sonrakini etkiler: `mv` dizin girdisini değiştirir, koşan bash eski dosyayı okumayı sürer."""
    newer = "#!/usr/bin/env bash\n# main'deki yeni sürüm\n"

    run = _run(tmp_path, clone_script=newer)

    assert run.code == 0, run.output
    assert run.installed.read_text(encoding="utf-8") == newer
    assert COLLECT in run.commands(), "bu tur eski (koşan) sürümle tamamlanmalıydı"
    assert "betik main'e güncellendi" in run.output


def test_an_up_to_date_copy_is_left_alone(tmp_path: Path) -> None:
    run = _run(tmp_path, clone_script=SCRIPT.read_text(encoding="utf-8"))

    assert run.code == 0, run.output
    assert "betik main'e güncellendi" not in run.output


# ── launchd tanımı ve kurulum ────────────────────────────────────────────────────────────────


def _load_installer() -> ModuleType:
    """`scripts/` bir paket değil: kurulum betiği kendi yolundan yüklenir."""
    path = REPO / "scripts/install_footystats_agent.py"
    spec = importlib.util.spec_from_file_location("install_footystats_agent", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass, modülünü sys.modules'ta arar
    spec.loader.exec_module(module)
    return module


installer = _load_installer()
HOME = Path("/Users/someone")
ENV_FILE = HOME / "dev/football-edge/.env"
TOOLS = {
    "uv": "/Users/someone/.local/bin/uv",
    "gh": "/opt/homebrew/bin/gh",
    "git": "/usr/bin/git",
}
BASE = "/Users/someone/.local/share/football-edge"


def test_agent_runs_the_installed_script_from_outside_its_clone() -> None:
    """Koşan betik klonun İÇİNDE değil: betiğin ilk işi o klonda `git checkout`; bash betiği
    okurken dosya değişirse koşan tur yarı eski yarı yeni satırlar çalıştırır."""
    plan = installer.plan(home=HOME, env_file=ENV_FILE, which=TOOLS.get)
    plist = plan.plist
    env = plist["EnvironmentVariables"]

    assert plist["Label"] == "com.popiliadam.football-edge.footystats"
    assert plist["ProgramArguments"] == ["/bin/bash", f"{BASE}/bin/footystats_daily.sh"]
    assert env["FOOTBALL_EDGE_CLONE"] == f"{BASE}/collector"
    assert not plist["ProgramArguments"][1].startswith(env["FOOTBALL_EDGE_CLONE"])
    assert env["FOOTBALL_EDGE_ENV_FILE"] == str(ENV_FILE)
    assert env["FOOTBALL_EDGE_STAMP"] == f"{BASE}/state/footystats-last-run"
    log = "/Users/someone/Library/Logs/football-edge/footystats.log"
    assert plist["StandardOutPath"] == plist["StandardErrorPath"] == log
    assert plan.plist_path == HOME / f"Library/LaunchAgents/{installer.LABEL}.plist"
    plistlib.dumps(plist)


def test_agent_gets_four_chances_a_day_and_one_at_login() -> None:
    """Mac 10:40'ta kapalı ya da uykudaysa gün kaybolmasın: sonraki dilim ya da oturum açılışı
    telafi eder; betiğin UTC-gün damgası turu yine günde bire indirir."""
    plist = installer.plan(home=HOME, env_file=ENV_FILE, which=TOOLS.get).plist

    assert plist["StartCalendarInterval"] == [
        {"Hour": hour, "Minute": 40} for hour in (10, 14, 18, 22)
    ]
    assert plist["RunAtLoad"] is True


def test_agent_path_reaches_every_tool_the_script_calls() -> None:
    """launchd'nin varsayılan PATH'i `/usr/bin:/bin:/usr/sbin:/sbin`: `uv` ve `gh` orada yok."""
    plist = installer.plan(home=HOME, env_file=ENV_FILE, which=TOOLS.get).plist
    directories = plist["EnvironmentVariables"]["PATH"].split(":")

    assert {"/Users/someone/.local/bin", "/opt/homebrew/bin", "/usr/bin", "/bin"} <= set(
        directories
    )


def test_agent_environment_is_an_allowlist_without_secrets() -> None:
    """plist düz bir dosyadır (`~/Library/LaunchAgents`): sır yalnız `.env`in YOLU olarak girer.
    Yasak listesi yeni bir sır adını (ör. `GH_TOKEN`) kaçırırdı; izin listesi kaçırmaz."""
    plist = installer.plan(home=HOME, env_file=ENV_FILE, which=TOOLS.get).plist

    assert set(plist["EnvironmentVariables"]) == {
        "PATH",
        "FOOTBALL_EDGE_CLONE",
        "FOOTBALL_EDGE_ENV_FILE",
        "FOOTBALL_EDGE_STAMP",
    }


@dataclass
class Launchctl:
    """`subprocess.run`un yerine geçer: komutları kaydeder, `git clone` klasörü oluşturur,
    `bootstrap` ilk `bootstrap_failures` çağrıda düşer."""

    bootstrap_failures: int = 0
    commands: list[list[str]] = field(default_factory=list)

    def __call__(self, command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        if command[:2] == ["git", "clone"]:
            (Path(command[-1]) / ".git").mkdir(parents=True)
        failed = command[1:2] == ["bootstrap"] and self.bootstrap_failures > 0
        if failed:
            self.bootstrap_failures -= 1
        return subprocess.CompletedProcess(command, 5 if failed else 0, "", "")


def _apply(tmp_path: Path, launchctl: Launchctl) -> Any:
    plan = installer.plan(home=tmp_path, env_file=tmp_path / ".env", which=TOOLS.get)
    installer.apply(plan, run=launchctl, sleep=lambda _seconds: None)
    return plan


def test_apply_clones_copies_writes_and_loads_in_that_order(tmp_path: Path) -> None:
    launchctl = Launchctl()

    plan = _apply(tmp_path, launchctl)

    domain = f"gui/{os.getuid()}"
    assert launchctl.commands == [
        ["git", "clone", "--quiet", installer.REPO_URL, str(plan.clone)],
        ["launchctl", "bootout", f"{domain}/{installer.LABEL}"],
        ["launchctl", "bootstrap", domain, str(plan.plist_path)],
        ["launchctl", "print", f"{domain}/{installer.LABEL}"],
    ]
    assert plan.script.read_bytes() == SCRIPT.read_bytes()
    assert plan.script.stat().st_mode & 0o777 == 0o755
    assert plistlib.loads(plan.plist_path.read_bytes()) == plan.plist
    assert plan.log.parent.is_dir()
    assert Path(plan.plist["EnvironmentVariables"]["FOOTBALL_EDGE_STAMP"]).parent.is_dir()


def test_apply_keeps_an_existing_clone(tmp_path: Path) -> None:
    (tmp_path / ".local/share/football-edge/collector/.git").mkdir(parents=True)
    launchctl = Launchctl()

    _apply(tmp_path, launchctl)

    assert not [command for command in launchctl.commands if command[:2] == ["git", "clone"]]


def test_apply_retries_a_bootstrap_racing_the_previous_bootout(tmp_path: Path) -> None:
    """`bootout` asenkron bitebilir; hemen ardından gelen `bootstrap` `5: Input/output error`
    ile düşebilir."""
    launchctl = Launchctl(bootstrap_failures=2)

    _apply(tmp_path, launchctl)

    assert [command[1] for command in launchctl.commands if command[0] == "launchctl"] == [
        "bootout",
        "bootstrap",
        "bootstrap",
        "bootstrap",
        "print",
    ]


def test_apply_gives_up_when_bootstrap_keeps_failing(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="bootstrap"):
        _apply(tmp_path, Launchctl(bootstrap_failures=99))


@dataclass
class Recorder:
    """Gerçek kurulumun yerine geçer: `main()` testleri `git clone` ve `launchctl`e ulaşamaz."""

    plans: list[object] = field(default_factory=list)

    def __call__(self, plan: object) -> None:
        self.plans.append(plan)


def _env_file(tmp_path: Path) -> Path:
    path = tmp_path / "secrets" / ".env"
    path.parent.mkdir()
    path.write_text(f"DATABASE_URL={DATABASE_URL}\n", encoding="utf-8")
    return path


def test_install_applies_the_plan_once_with_a_resolved_env_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Göreli `--env-file` launchd'ye göreli gitseydi, işin çalışma dizininden çözülürdü."""
    home, recorder = tmp_path / "home", Recorder()
    env_file = _env_file(tmp_path)
    monkeypatch.chdir(tmp_path)

    code = installer.main(
        ["--env-file", "secrets/.env"], home=home, which=TOOLS.get, install=recorder
    )

    assert code == 0
    expected = installer.plan(home=home, env_file=env_file.resolve(), which=TOOLS.get)
    assert recorder.plans == [expected]


def test_dry_run_installs_and_writes_nothing(tmp_path: Path) -> None:
    home, recorder = tmp_path / "home", Recorder()
    env_file = _env_file(tmp_path)

    code = installer.main(
        ["--dry-run", "--env-file", str(env_file)], home=home, which=TOOLS.get, install=recorder
    )

    assert code == 0
    assert recorder.plans == []
    assert not home.exists()


def test_a_missing_env_file_stops_before_installing(tmp_path: Path) -> None:
    recorder = Recorder()

    with pytest.raises(SystemExit, match="DATABASE_URL"):
        installer.main(
            ["--env-file", str(tmp_path / "yok.env")],
            home=tmp_path / "home",
            which=TOOLS.get,
            install=recorder,
        )
    assert recorder.plans == []


def test_a_missing_tool_is_named_instead_of_installing_a_broken_agent(tmp_path: Path) -> None:
    without_gh = {name: path for name, path in TOOLS.items() if name != "gh"}
    recorder = Recorder()

    with pytest.raises(SystemExit, match="gh"):
        installer.main(
            ["--env-file", str(_env_file(tmp_path))],
            home=tmp_path / "home",
            which=without_gh.get,
            install=recorder,
        )
    assert recorder.plans == []
