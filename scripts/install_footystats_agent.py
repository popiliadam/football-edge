"""Mac'teki günlük footystats işini (launchd) kurar — RUNBOOK §3.9.

GitHub runner'ları footystats'tan 403 alıyor (DEFERRED 10r); iş bu Mac'te koşar. Kurulum:
işin kendi temiz klonu, klonun DIŞINA kopyalanan betik, `~/Library/LaunchAgents` altına plist ve
`launchctl bootstrap`. Yeniden koşmak güvenlidir: betik ve plist atomik yenilenir, iş yeniden
yüklenir. Sonraki betik güncellemelerini betik kendisi `main`den alır.

    uv run python scripts/install_footystats_agent.py --dry-run   # yalnız planı gösterir
    uv run python scripts/install_footystats_agent.py
"""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LABEL = "com.popiliadam.football-edge.footystats"
REPO_URL = "https://github.com/popiliadam/football-edge.git"
REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_SCRIPT = REPO_ROOT / "scripts/footystats_daily.sh"
# Yerel saat (Europe/Istanbul). İlk dilim 07:40 UTC: günün snapshot'ından (06:22) ve GitHub'daki
# `collect-daily`den (07:10) sonra. Sonraki dilimler ve oturum açılışı kaçan günü telafi eder;
# betiğin UTC-gün damgası turu günde bire indirir. Mac uykudaysa launchd dilimi uyanınca koşar.
SLOTS = ((10, 40), (14, 40), (18, 40), (22, 40))
TOOLS = ("uv", "gh", "git")
# launchd'nin varsayılan PATH'i: `uv` ve `gh` bunların hiçbirinde yok.
SYSTEM_PATH = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")
# Önceki kaydın `bootout`u asenkron bitebilir; hemen ardından gelen `bootstrap` düşebilir.
BOOTSTRAP_ATTEMPTS = 5

Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class Plan:
    clone: Path
    script: Path
    stamp: Path
    log: Path
    plist_path: Path
    plist: dict[str, Any]


def plan(*, home: Path, env_file: Path, which: Callable[[str], str | None]) -> Plan:
    """Kurulacak her yolu ve plist'i hesaplar; hiçbir şeye dokunmaz."""
    found = {tool: which(tool) for tool in TOOLS}
    missing = [tool for tool, path in found.items() if path is None]
    if missing:
        raise SystemExit(f"HATA: PATH'te yok: {', '.join(missing)} — iş kurulmadı")
    base = home / ".local/share/football-edge"
    clone, script = base / "collector", base / "bin/footystats_daily.sh"
    stamp = base / "state/footystats-last-run"
    log = home / "Library/Logs/football-edge/footystats.log"
    tool_dirs = [str(Path(path).parent) for path in found.values() if path is not None]
    plist: dict[str, Any] = {
        "Label": LABEL,
        "ProgramArguments": ["/bin/bash", str(script)],
        "StartCalendarInterval": [{"Hour": hour, "Minute": minute} for hour, minute in SLOTS],
        "RunAtLoad": True,
        "ProcessType": "Background",
        # İzin listesi: sır yok, yalnız `.env`in YOLU (plist düz bir dosyadır).
        "EnvironmentVariables": {
            "PATH": ":".join(dict.fromkeys([*tool_dirs, *SYSTEM_PATH])),
            "FOOTBALL_EDGE_CLONE": str(clone),
            "FOOTBALL_EDGE_ENV_FILE": str(env_file),
            "FOOTBALL_EDGE_STAMP": str(stamp),
        },
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
    }
    plist_path = home / "Library/LaunchAgents" / f"{LABEL}.plist"
    return Plan(clone, script, stamp, log, plist_path, plist)


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _replace(target: Path, content: bytes, mode: int) -> None:
    """Geçici dosya + `os.replace`: koşan bir tur yarı yazılmış betik okumaz."""
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    with os.fdopen(handle, "wb") as stream:
        stream.write(content)
    os.chmod(temporary, mode)
    os.replace(temporary, target)


def _checked(run: Runner, command: list[str], what: str) -> None:
    result = run(command)
    if result.returncode != 0:
        raise SystemExit(f"HATA: {what} düştü (exit {result.returncode}): {result.stderr.strip()}")


def apply(target: Plan, *, run: Runner = _run, sleep: Callable[[float], None] = time.sleep) -> None:
    """Klon (yoksa), betik kopyası, plist ve launchd kaydı — bu sırayla."""
    target.log.parent.mkdir(parents=True, exist_ok=True)
    target.stamp.parent.mkdir(parents=True, exist_ok=True)
    if not (target.clone / ".git").exists():
        target.clone.parent.mkdir(parents=True, exist_ok=True)
        _checked(run, ["git", "clone", "--quiet", REPO_URL, str(target.clone)], "git clone")
    _replace(target.script, SOURCE_SCRIPT.read_bytes(), 0o755)
    _replace(target.plist_path, plistlib.dumps(target.plist), 0o644)
    domain = f"gui/{os.getuid()}"
    # Önceki kayıt yoksa bootout hata verir; bu beklenen durumdur.
    run(["launchctl", "bootout", f"{domain}/{LABEL}"])
    for attempt in range(1, BOOTSTRAP_ATTEMPTS + 1):
        result = run(["launchctl", "bootstrap", domain, str(target.plist_path)])
        if result.returncode == 0:
            break
        if attempt == BOOTSTRAP_ATTEMPTS:
            raise SystemExit(
                f"HATA: launchctl bootstrap {attempt} denemede de düştü: {result.stderr.strip()}"
            )
        sleep(1.0)
    _checked(run, ["launchctl", "print", f"{domain}/{LABEL}"], "launchctl print")


def main(
    argv: Sequence[str] | None = None,
    *,
    home: Path | None = None,
    which: Callable[[str], str | None] = shutil.which,
    install: Callable[[Plan], None] = apply,
) -> int:
    """`install` enjekte edilir: testler gerçek `git clone` ve `launchctl`e hiçbir yoldan
    ulaşamaz — bir gerileme plan kontrolünü bozsa bile geliştirme Mac'ine iş kaydedilmez."""
    parser = argparse.ArgumentParser(description="günlük footystats launchd işini kurar")
    parser.add_argument("--dry-run", action="store_true", help="yalnız planı göster")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    args = parser.parse_args(argv)
    target = plan(home=home or Path.home(), env_file=args.env_file.resolve(), which=which)
    sys.stdout.write(plistlib.dumps(target.plist).decode("utf-8"))
    if args.dry_run:
        sys.stdout.write(f"\n(kuru koşu) {target.plist_path} yazılmadı, iş yüklenmedi\n")
        return 0
    if not args.env_file.is_file():
        raise SystemExit(f"HATA: {args.env_file} yok — DATABASE_URL okunamaz, iş kurulmadı")
    install(target)
    sys.stdout.write(f"\nkuruldu: {target.plist_path}\ngünlük: {target.log}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
