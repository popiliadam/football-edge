"""Mac'teki günlük footystats işi (RUNBOOK §3.9): betik ve launchd tanımı.

GitHub runner'ları footystats'tan 403 alıyor (DEFERRED 10r); iş Mac'te launchd ile koşar.
Betik sahte `git`/`uv`/`gh` ile koşulur: bir Mac'te gerçekten koştuğu burada ölçülmez.
"""

from __future__ import annotations

import importlib.util
import os
import plistlib
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts/footystats_daily.sh"
DB_PASSWORD = "pw-sentinel-7c1"
DATABASE_URL = f"postgresql://collector:{DB_PASSWORD}@db.test:5432/postgres"
TOKEN = "gho-sentinel-token-42"
COLLECT = "uv run --frozen python -m football_edge.collect fetch-footystats"
ALARM = "uv run --frozen python scripts/ops_alert.py"

# `git`, `uv` ve `gh`in yerine geçer: her çağrıyı araç, argümanlar ve ortamdaki sırlarla bir
# satıra yazar; `FAIL_MATCH` ile başlayan çağrı `FAIL_CODE` ile döner.
FAKE_TOOL = """\
#!/usr/bin/env bash
tool=$(basename "$0")
printf '%s %s|db=%s|token=%s|odds=%s\\n' "$tool" "$*" "${DATABASE_URL:-}" \\
  "${GITHUB_TOKEN:+var}" "${ODDS_API_KEY:+var}" >> "$CALLS"
if [ -n "$FAIL_MATCH" ] && [[ "$tool $*" == "$FAIL_MATCH"* ]]; then exit "$FAIL_CODE"; fi
if [ "$tool" = gh ]; then
  [ -z "${GH_FAIL:-}" ] || exit 1
  printf '%s\\n' "$TOKEN"
fi
"""


@dataclass(frozen=True)
class Run:
    code: int
    output: str
    calls: tuple[str, ...]

    def commands(self) -> tuple[str, ...]:
        return tuple(call.split("|")[0] for call in self.calls)

    def call(self, prefix: str) -> str:
        return next(call for call in self.calls if call.startswith(prefix))


def _run(
    tmp_path: Path,
    *,
    fail_match: str = "",
    fail_code: int = 1,
    gh_fail: bool = False,
    env_file_text: str = f"ODDS_API_KEY=odds-sentinel\nDATABASE_URL={DATABASE_URL}\n",
) -> Run:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("git", "uv", "gh"):
        fake = bin_dir / tool
        fake.write_text(FAKE_TOOL, encoding="utf-8")
        fake.chmod(0o755)
    clone = tmp_path / "clone"
    clone.mkdir()
    env_file = tmp_path / ".env"
    env_file.write_text(env_file_text, encoding="utf-8")
    calls = tmp_path / "calls"
    calls.touch()
    env = {
        "PATH": f"{bin_dir}{os.pathsep}/usr/bin{os.pathsep}/bin",
        "HOME": str(tmp_path),
        "CALLS": str(calls),
        "TOKEN": TOKEN,
        "FAIL_MATCH": fail_match,
        "FAIL_CODE": str(fail_code),
        "FOOTBALL_EDGE_CLONE": str(clone),
        "FOOTBALL_EDGE_ENV_FILE": str(env_file),
        "FOOTBALL_EDGE_LOG": str(tmp_path / "footystats.log"),
        **({"GH_FAIL": "1"} if gh_fail else {}),
    }
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return Run(
        result.returncode,
        result.stdout + result.stderr,
        tuple(calls.read_text(encoding="utf-8").splitlines()),
    )


def test_green_run_pulls_main_before_collecting_and_clears_the_alarm(tmp_path: Path) -> None:
    """Sıra yük taşır: toplayıcı `main`in incelenmiş son hâlini koşar, yarım bir dalı değil."""
    run = _run(tmp_path)

    assert run.code == 0, run.output
    assert run.commands()[:5] == (
        "git fetch --quiet origin main",
        "git checkout --quiet --detach FETCH_HEAD",
        "git rev-parse --short HEAD",
        "uv sync --frozen --quiet",
        COLLECT,
    )
    assert run.commands()[5] == "gh auth token"
    assert run.commands()[6].startswith(f"{ALARM} ok --workflow footystats-local --run-url ")


def test_the_collector_gets_only_the_database_and_the_alarm_only_the_token(tmp_path: Path) -> None:
    """GitHub'daki `collect-daily` ile aynı sınır: toplayıcı yalnız `DATABASE_URL`i görür (Odds
    anahtarı `.env`de dursa da), GitHub token'ı yalnız alarm sürecine verilir; ikisi de
    argümanda değil ortamda taşınır ve çıktıya düşmez."""
    run = _run(tmp_path)

    assert run.call(COLLECT).endswith(f"|db={DATABASE_URL}|token=|odds=")
    assert run.call(ALARM).endswith("|db=|token=var|odds=")
    assert TOKEN not in run.output
    assert DB_PASSWORD not in run.output
    assert all(TOKEN not in call and DB_PASSWORD not in call.split("|")[0] for call in run.calls)


def test_a_red_collector_raises_the_alarm_and_keeps_its_exit_code(tmp_path: Path) -> None:
    run = _run(tmp_path, fail_match=COLLECT, fail_code=3)

    assert run.code == 3, run.output
    assert run.call(ALARM).startswith(f"{ALARM} fail --workflow footystats-local ")
    assert not any(f"{ALARM} ok" in call for call in run.calls)


def test_a_failed_pull_raises_the_alarm_and_collects_nothing(tmp_path: Path) -> None:
    run = _run(tmp_path, fail_match="git fetch", fail_code=128)

    assert run.code != 0
    assert COLLECT not in run.commands()
    assert run.call(ALARM).startswith(f"{ALARM} fail --workflow footystats-local ")


def test_without_a_github_session_the_run_stays_red_and_says_so(tmp_path: Path) -> None:
    """Alarm iletilemiyorsa bu da adıyla günlüğe yazılır; tur yine kırmızıdır."""
    run = _run(tmp_path, fail_match=COLLECT, fail_code=7, gh_fail=True)

    assert run.code == 7, run.output
    assert "gh oturumu yok" in run.output
    assert not any(call.startswith(ALARM) for call in run.calls)


def test_a_missing_database_url_stops_before_collecting(tmp_path: Path) -> None:
    run = _run(tmp_path, env_file_text="ODDS_API_KEY=odds-sentinel\n")

    assert run.code != 0
    assert COLLECT not in run.commands()
    assert "DATABASE_URL" in run.output
    assert run.call(ALARM).startswith(f"{ALARM} fail ")


def test_a_quoted_database_url_reaches_the_collector_unquoted(tmp_path: Path) -> None:
    run = _run(tmp_path, env_file_text=f'DATABASE_URL="{DATABASE_URL}"\n')

    assert run.code == 0, run.output
    assert run.call(COLLECT).endswith(f"|db={DATABASE_URL}|token=|odds=")


def test_a_failed_alarm_close_does_not_turn_a_green_run_red(tmp_path: Path) -> None:
    """`collect-daily`deki `continue-on-error` ile aynı: kapatma sonraki yeşil turda denenir."""
    run = _run(tmp_path, fail_match=f"{ALARM} ok", fail_code=1)

    assert run.code == 0, run.output


# ── launchd tanımı ───────────────────────────────────────────────────────────────────────────


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


def test_agent_runs_the_installed_script_daily_from_its_own_clone() -> None:
    """Koşan betik klonun İÇİNDE değil: betiğin ilk işi o klonda `git checkout`; bash betiği
    okurken dosya değişirse koşan tur yarı eski yarı yeni satırlar çalıştırır."""
    plan = installer.plan(home=HOME, env_file=ENV_FILE, which=TOOLS.get)
    plist = plan.plist
    env = plist["EnvironmentVariables"]

    assert plist["Label"] == "com.popiliadam.football-edge.footystats"
    assert plist["ProgramArguments"] == [
        "/bin/bash",
        "/Users/someone/.local/share/football-edge/bin/footystats_daily.sh",
    ]
    assert env["FOOTBALL_EDGE_CLONE"] == "/Users/someone/.local/share/football-edge/collector"
    assert not plist["ProgramArguments"][1].startswith(env["FOOTBALL_EDGE_CLONE"])
    assert plist["StartCalendarInterval"] == {"Hour": 10, "Minute": 40}
    assert plist["RunAtLoad"] is False
    assert env["FOOTBALL_EDGE_ENV_FILE"] == str(ENV_FILE)
    log = "/Users/someone/Library/Logs/football-edge/footystats.log"
    assert env["FOOTBALL_EDGE_LOG"] == plist["StandardOutPath"] == plist["StandardErrorPath"] == log
    assert (
        plan.plist_path
        == HOME / "Library/LaunchAgents/com.popiliadam.football-edge.footystats.plist"
    )
    plistlib.dumps(plist)


def test_agent_path_reaches_every_tool_the_script_calls() -> None:
    """launchd'nin varsayılan PATH'i `/usr/bin:/bin:/usr/sbin:/sbin`: `uv` ve `gh` orada yok."""
    env = installer.plan(home=HOME, env_file=ENV_FILE, which=TOOLS.get).plist[
        "EnvironmentVariables"
    ]
    directories = env["PATH"].split(":")

    assert {"/Users/someone/.local/bin", "/opt/homebrew/bin", "/usr/bin", "/bin"} <= set(
        directories
    )


def test_agent_definition_carries_no_secret() -> None:
    """plist düz bir dosyadır (`~/Library/LaunchAgents`): sır yalnız `.env`in YOLU olarak girer."""
    plist = installer.plan(home=HOME, env_file=ENV_FILE, which=TOOLS.get).plist

    assert (
        not {"DATABASE_URL", "GITHUB_TOKEN", "ODDS_API_KEY"} & plist["EnvironmentVariables"].keys()
    )


@dataclass
class Recorder:
    """Gerçek kurulumun yerine geçer: testler `git clone` ve `launchctl`e ulaşamaz."""

    plans: list[object] = field(default_factory=list)

    def __call__(self, plan: object) -> None:
        self.plans.append(plan)


def _env_file(tmp_path: Path) -> Path:
    path = tmp_path / "secrets" / ".env"
    path.parent.mkdir()
    path.write_text(f"DATABASE_URL={DATABASE_URL}\n", encoding="utf-8")
    return path


def test_install_applies_the_plan_once(tmp_path: Path) -> None:
    home, recorder = tmp_path / "home", Recorder()
    env_file = _env_file(tmp_path)

    code = installer.main(
        ["--env-file", str(env_file)], home=home, which=TOOLS.get, install=recorder
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
