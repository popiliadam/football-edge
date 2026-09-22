"""Mac'teki günlük footystats işini (launchd) kurar — RUNBOOK §3.9.

GitHub runner'ları footystats'tan 403 alıyor (DEFERRED 10r); iş bu Mac'te koşar. Kurulum:
işin kendi temiz klonu, klonun DIŞINA kopyalanan betik, `~/Library/LaunchAgents` altına plist ve
`launchctl bootstrap`. Yeniden koşmak güvenlidir: betik ve plist yenilenir, iş yeniden yüklenir.

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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LABEL = "com.popiliadam.football-edge.footystats"
REPO_URL = "https://github.com/popiliadam/football-edge.git"
REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_SCRIPT = REPO_ROOT / "scripts/footystats_daily.sh"
# Yerel saat (Europe/Istanbul) — 07:40 UTC: günün snapshot'ından (06:22) ve GitHub'daki
# `collect-daily`den (07:10) sonra. Mac uykudaysa launchd turu uyanınca bir kez koşar.
HOUR, MINUTE = 10, 40
TOOLS = ("uv", "gh", "git")
# launchd'nin varsayılan PATH'i: `uv` ve `gh` bunların hiçbirinde yok.
SYSTEM_PATH = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")


@dataclass(frozen=True)
class Plan:
    clone: Path
    script: Path
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
    log = home / "Library/Logs/football-edge/footystats.log"
    tool_dirs = [str(Path(path).parent) for path in found.values() if path is not None]
    path_value = ":".join(dict.fromkeys([*tool_dirs, *SYSTEM_PATH]))
    plist: dict[str, Any] = {
        "Label": LABEL,
        "ProgramArguments": ["/bin/bash", str(script)],
        "StartCalendarInterval": {"Hour": HOUR, "Minute": MINUTE},
        "RunAtLoad": False,
        "ProcessType": "Background",
        "EnvironmentVariables": {
            "PATH": path_value,
            "FOOTBALL_EDGE_CLONE": str(clone),
            "FOOTBALL_EDGE_ENV_FILE": str(env_file),
            "FOOTBALL_EDGE_LOG": str(log),
        },
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
    }
    plist_path = home / "Library/LaunchAgents" / f"{LABEL}.plist"
    return Plan(clone=clone, script=script, log=log, plist_path=plist_path, plist=plist)


def apply(target: Plan) -> None:
    """Klon (yoksa), betik kopyası, plist ve launchd kaydı."""
    target.log.parent.mkdir(parents=True, exist_ok=True)
    if not (target.clone / ".git").exists():
        target.clone.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--quiet", REPO_URL, str(target.clone)], check=True)
    target.script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE_SCRIPT, target.script)
    target.script.chmod(0o755)
    target.plist_path.parent.mkdir(parents=True, exist_ok=True)
    target.plist_path.write_bytes(plistlib.dumps(target.plist))
    domain = f"gui/{os.getuid()}"
    # Önceki kayıt varsa kaldırılır; yoksa bootout hata verir ve bu beklenen durumdur.
    subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], capture_output=True, check=False)
    subprocess.run(["launchctl", "bootstrap", domain, str(target.plist_path)], check=True)


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
