"""Site kapısının Node adımları `verify.sh` / `ci.yml` / `site.yml`e doğru bağlı (spec §12.1–§12.3).

Adımlar B-1'in `site-db` adımından SONRA koşar (uçtan uca anlık görüntüyü o yazar); CI
Node ve pnpm'i `web/.nvmrc` / `packageManager`dan kurar; uçtan uca anlık görüntü yalnız bu
koşunundur (bayat dosyayla PASS yok, CI'da yokluğu FAIL); `site.yml` derlemeyi `_headers`
üreten `run build` ile yapar, yayından önce çıktı tarayıcısını ve kaybolan-slug kontrolünü,
yayından sonra "yayımlanan = doğrulanan" kontrolünü koşar; Netlify CLI derlemez (`--no-build`).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
VERIFY = REPO / "verify.sh"
CI = REPO / ".github/workflows/ci.yml"
SITE = REPO / ".github/workflows/site.yml"
GATE = REPO / "scripts/site_gate.sh"
NODE_STEPS = ("site-kurulum", "site-tip", "site-lint", "site-test", "site-derleme", "site-uyum")


def _step_names() -> list[str]:
    # B-1 `site-db`yi `if/elif` içinde girintili yazar: girinti kabul edilir.
    return re.findall(r'^\s*step "([^"]+)"', VERIFY.read_text(encoding="utf-8"), flags=re.M)


def _steps(path: Path) -> list[dict[str, Any]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [step for job in document["jobs"].values() for step in job["steps"]]


def _index(steps: list[dict[str, Any]], needle: str, key: str = "run") -> int:
    for index, step in enumerate(steps):
        if needle in str(step.get(key, "")):
            return index
    raise AssertionError(f"adım yok: {needle!r}")


def test_node_steps_run_in_order_after_site_db() -> None:
    names = _step_names()
    positions = [names.index(name) for name in ("site-db", *NODE_STEPS)]
    assert positions == sorted(positions), f"sıra yanlış: {names}"


def test_the_site_block_starts_after_the_site_db_block_closes() -> None:
    """Sıra testi `site-db`nin İLK geçişini görür; blok `if … fi` kapandıktan SONRA başlar."""
    text = VERIFY.read_text(encoding="utf-8")
    closing = re.compile(r"^fi$", flags=re.M).search(text, text.rindex('step "site-db"'))
    assert closing is not None, "site-db bloğunun `fi`si yok"
    assert text.index('SITE_BUILDS="$(mktemp -d') > closing.start()


def test_builds_go_to_a_fresh_directory_per_run_and_nothing_is_deleted() -> None:
    text = VERIFY.read_text(encoding="utf-8")
    assert 'SITE_BUILDS="$(mktemp -d' in text
    assert "export SITE_BUILDS" in text
    assert not re.search(r"^\s*rm\s", GATE.read_text(encoding="utf-8"), flags=re.M)


def test_ci_installs_node_and_pnpm_from_the_pins_before_the_gate() -> None:
    steps = _steps(CI)
    pnpm = _index(steps, "pnpm/action-setup", key="uses")
    node = _index(steps, "actions/setup-node", key="uses")
    gate = _index(steps, "./verify.sh")
    assert pnpm < node < gate
    assert steps[pnpm]["with"]["package_json_file"] == "web/package.json"
    assert steps[node]["with"]["node-version-file"] == "web/.nvmrc"


def _gate(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(GATE), *args],
        capture_output=True,
        text=True,
        env={"PATH": os.environ["PATH"], **env},
        check=False,
    )


def _e2e_dir(tmp_path: Path, run_id: str | None) -> Path:
    directory = tmp_path / "site-e2e"
    directory.mkdir()
    (directory / "snapshot.json").write_text("{}", encoding="utf-8")
    if run_id is not None:
        (directory / "run-id").write_text(run_id + "\n", encoding="utf-8")
    return directory


@pytest.mark.parametrize("ci", ["", "true"])
def test_e2e_snapshot_of_this_run_is_used(tmp_path: Path, ci: str) -> None:
    directory = _e2e_dir(tmp_path, "run-7")
    env = {"RUNNER_TEMP": str(tmp_path), "FE_VERIFY_RUN_ID": "run-7", "CI": ci}
    result = _gate(["e2e"], env)
    assert (result.returncode, result.stdout.strip()) == (0, f"USE {directory}/snapshot.json")


@pytest.mark.parametrize("run_id", ["run-6", None])
def test_stale_or_unlabelled_e2e_snapshot_is_skipped_locally_and_fails_in_ci(
    tmp_path: Path, run_id: str | None
) -> None:
    _e2e_dir(tmp_path, run_id)
    local = _gate(["e2e"], {"RUNNER_TEMP": str(tmp_path), "FE_VERIFY_RUN_ID": "run-7"})
    assert (local.returncode, local.stdout.split(" ")[0]) == (0, "SKIP")
    env = {"RUNNER_TEMP": str(tmp_path), "FE_VERIFY_RUN_ID": "run-7", "CI": "true"}
    ci = _gate(["e2e"], env)
    assert (ci.returncode, ci.stdout.split(" ")[0]) == (1, "FAIL")


def test_missing_run_id_variable_never_accepts_a_file(tmp_path: Path) -> None:
    _e2e_dir(tmp_path, "")
    result = _gate(["e2e"], {"RUNNER_TEMP": str(tmp_path)})
    assert result.stdout.startswith("SKIP ")


def _fake_tools(tmp_path: Path, node: str, pnpm: str) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, output in (("node", node), ("pnpm", pnpm)):
        tool = bin_dir / name
        tool.write_text(f"#!/bin/sh\n{output}\n", encoding="utf-8")
        tool.chmod(0o755)
    return {"PATH": f"{bin_dir}:/usr/bin:/bin"}


@pytest.mark.parametrize(
    ("node", "pnpm", "message"),
    [
        ("echo 22", "echo 10.34.5", "Node 22, .nvmrc 24 istiyor"),
        ("echo 24", "echo 11.9.0", "pnpm 11, packageManager 10 istiyor"),
        ("exit 127", "echo 10.34.5", "node yok"),
        ("echo 24", "exit 127", "pnpm yok"),
    ],
)
def test_wrong_or_missing_toolchain_fails_by_name(
    tmp_path: Path, node: str, pnpm: str, message: str
) -> None:
    result = subprocess.run(
        [str(GATE), "toolchain"],
        capture_output=True,
        text=True,
        env=_fake_tools(tmp_path, node, pnpm),
        check=False,
    )
    assert result.returncode == 1
    assert message in result.stdout


def test_matching_toolchain_passes(tmp_path: Path) -> None:
    env = _fake_tools(tmp_path, "echo 24", "echo 10.34.5")
    result = subprocess.run(
        [str(GATE), "toolchain"], capture_output=True, text=True, env=env, check=False
    )
    assert result.returncode == 0, result.stdout


def test_site_workflow_builds_with_headers_and_checks_before_deploy() -> None:
    steps = _steps(SITE)
    install = _index(steps, "pnpm -C web install --frozen-lockfile")
    build = _index(steps, "pnpm -C web run build")
    check = _index(steps, "web/scripts/check-out.ts")
    deploy = _index(steps, "deploy --prod")
    assert install < build < check < deploy
    assert steps[build]["env"]["NEXT_TELEMETRY_DISABLED"] == "1"
    assert not any("next build" in str(step.get("run", "")) for step in steps), (
        "çıplak `next build` `_headers`/`_redirects` üretmez; `run build` kullanılır"
    )


def test_site_workflow_runs_both_publish_gates_around_the_deploy() -> None:
    """§11, §6.4/3f: kaybolan-slug yayından ÖNCE (kırmızıysa yayın yok), kontrol yayından SONRA."""
    steps = _steps(SITE)
    check = _index(steps, "web/scripts/check-out.ts")
    slugs = _index(steps, "scripts/site_publish.py slugs")
    deploy = _index(steps, "deploy --prod")
    live = _index(steps, "scripts/site_publish.py live")
    assert check < slugs < deploy < live
    assert "--first-publish" in steps[slugs]["run"]
    assert set(steps[slugs].get("env", {})) == {"FIRST_PUBLISH"}


def test_first_publish_is_an_explicit_input_that_defaults_to_off() -> None:
    document = yaml.safe_load(SITE.read_text(encoding="utf-8"))
    triggers = document.get("on") or document.get(True)
    first = triggers["workflow_dispatch"]["inputs"]["first_publish"]
    assert (first["type"], first["default"]) == ("boolean", False)


def test_netlify_cli_never_runs_the_refusing_build_command() -> None:
    """netlify-cli v21+ `deploy` yapılandırmadaki derlemeyi koşar; bizimki bilerek düşer."""
    steps = _steps(SITE)
    assert "--no-build" in steps[_index(steps, "deploy --prod")]["run"]


def test_site_workflow_never_turns_indexing_on() -> None:
    assert "SITE_INDEXABLE" not in SITE.read_text(encoding="utf-8"), "AK14 onayı yok"


# ── Düzeltme turu 1 (T10 incelemesi I1–I4): `site_gate.sh`in davranışı sahte araçlarla ──────────
# Betik geçici bir depo kopyasına konur (REPO betiğin yerinden türetilir) ve PATH'in başındaki sahte
# `uv`/`pnpm`/`node` her çağrıyı (argümanlar, SITE_SNAPSHOT, SITE_INDEXABLE, çalışma dizini) ve
# ortamını dosyaya yazar. Gerçek derleme koşmaz; ölçülen, kapının BAĞLANTISIDIR: sıra, hata
# yayılımı, CI'da uçtan uca varyantın zorunluluğu ve Node araçlarının gördüğü ortam.

# Node araçlarının göreceği ortamın izin listesi (`site_gate.sh` NODE_ENV_ALLOW + sabit NO_COLOR) ve
# `/bin/sh`in sahte aracın kendi ortamına eklediği adlar.
NODE_ENV_ALLOW = {
    "NO_COLOR",
    "PATH",
    "HOME",
    "TMPDIR",
    "CI",
    "PNPM_HOME",
    "NEXT_TELEMETRY_DISABLED",
    "SITE_SNAPSHOT",
    "SITE_INDEXABLE",
}
SHELL_ADDED = {"PWD", "OLDPWD", "SHLVL", "_"}
# Adlar parçalardan: kapının secrets taraması `AD=değer` biçimini arar.
CANARIES = {
    "DATABASE" + "_URL",
    "SITE_TEST_" + "DATABASE_URL",
    "SANDBOX_" + "DATABASE_URL",
    "ODDS_API" + "_KEY",
    "TYPESAFE_API" + "_KEY",
    "NETLIFY_AUTH" + "_TOKEN",
}
FAKE_TOOL = """#!/bin/sh
env > "{envs}/{tool}.$$"
row="{tool}|$PWD|$*|${{SITE_SNAPSHOT:-}}|${{SITE_INDEXABLE:-}}"
printf '%s\\n' "$row" >> "{calls}"
if [ -e "{flags}/{tool}-fails" ]; then exit 1; fi
case "{tool} $*" in
  "node -p "*) cat "{flags}/node-version" ;;
  "pnpm --version") echo 10.34.5 ;;
  "pnpm -C "*" run build") mkdir -p "$2/out" && echo "$SITE_SNAPSHOT" > "$2/out/built-from" ;;
esac
"""


class Rig:
    """Geçici depo kopyası + sahte araçlar. `run` betiği verilen ek ortamla koşar."""

    def __init__(self, tmp_path: Path) -> None:
        self.repo = (tmp_path / "repo").resolve()
        self.web = self.repo / "web"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy2(GATE, self.repo / "scripts/site_gate.sh")
        (self.web / "fixtures").mkdir(parents=True)
        for name in (".nvmrc", "package.json"):
            shutil.copy2(REPO / "web" / name, self.web / name)
        self.full = self.web / "fixtures/snapshot.fixture.web-full.json"
        self.empty = self.web / "fixtures/snapshot.fixture.web-empty.json"
        for fixture in (self.full, self.empty):
            fixture.write_text("{}", encoding="utf-8")
        e2e = tmp_path / "site-e2e"
        e2e.mkdir()
        self.e2e = e2e / "snapshot.json"
        self.e2e.write_text("{}", encoding="utf-8")
        self.e2e_sha = e2e / "snapshot.sha256"
        self.e2e_sha.write_text(f"{'a' * 64}  snapshot.json\n", encoding="utf-8")
        self.calls = tmp_path / "calls.log"
        self.envs = tmp_path / "envs"
        self.flags = tmp_path / "flags"
        self.builds = tmp_path / "builds"
        for directory in (self.envs, self.flags, self.builds):
            directory.mkdir()
        (self.flags / "node-version").write_text("24\n", encoding="utf-8")
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        for tool in ("uv", "pnpm", "node"):
            path = bin_dir / tool
            text = FAKE_TOOL.format(envs=self.envs, tool=tool, calls=self.calls, flags=self.flags)
            path.write_text(text, encoding="utf-8")
            path.chmod(0o755)
        self.base = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path)}
        self.base["SITE_BUILDS"] = str(self.builds)

    def run(self, command: str, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.repo / "scripts/site_gate.sh"), command],
            capture_output=True,
            text=True,
            env={**self.base, **env},
            check=False,
        )

    def calls_of(self, *tools: str) -> list[tuple[str, str, str, str]]:
        """(araç, argümanlar, SITE_SNAPSHOT, SITE_INDEXABLE) — çağrı sırasıyla."""
        if not self.calls.exists():
            return []
        rows = [line.split("|") for line in self.calls.read_text("utf-8").splitlines()]
        return [(t, args, snap, flag) for t, _, args, snap, flag in rows if t in tools]

    def uv_dirs(self) -> set[str]:
        rows = [line.split("|") for line in self.calls.read_text("utf-8").splitlines()]
        return {pwd for tool, pwd, *_ in rows if tool == "uv"}

    def env_names(self, tool: str) -> list[set[str]]:
        return [
            {line.split("=", 1)[0] for line in dump.read_text("utf-8").splitlines() if "=" in line}
            for dump in sorted(self.envs.glob(f"{tool}.*"))
        ]

    def fail(self, tool: str) -> None:
        (self.flags / f"{tool}-fails").write_text("", encoding="utf-8")


def _verify(snapshot: Path, *extra: str) -> tuple[str, str, str, str]:
    args = " ".join(("run python -m football_edge.site verify-snapshot", str(snapshot), *extra))
    return ("uv", args, "", "")


def _built(rig: Rig, snapshot: Path, flag: str = "") -> tuple[str, str, str, str]:
    return ("pnpm", f"-C {rig.web} run build", str(snapshot), flag)


def test_every_build_is_preceded_by_verify_snapshot_of_the_same_file(tmp_path: Path) -> None:
    """Carry-in 5 (T2 kararı): her derlemeden ÖNCE aynı dosyaya `verify-snapshot`; uçtan uca dosya
    yanındaki `snapshot.sha256`le. Sıra değişirse ya da doğrulama düşerse kırmızı (I2)."""
    rig = Rig(tmp_path)
    result = rig.run("build", SITE_E2E_SNAPSHOT=str(rig.e2e))

    assert result.returncode == 0, result.stdout
    assert rig.calls_of("uv", "pnpm") == [
        _verify(rig.full),
        _built(rig, rig.full),
        _verify(rig.full),
        _built(rig, rig.full, "1"),
        _verify(rig.empty),
        _built(rig, rig.empty),
        _verify(rig.e2e, "--sha256", str(rig.e2e_sha)),
        _built(rig, rig.e2e),
    ]
    assert rig.uv_dirs() == {str(rig.repo)}
    built = sorted(path.name for path in rig.builds.iterdir())
    assert built == ["e2e", "fixture-empty", "fixture-full", "fixture-full-indexable"]


def test_check_scans_every_built_variant_with_its_own_snapshot(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    assert rig.run("build", SITE_E2E_SNAPSHOT=str(rig.e2e)).returncode == 0
    rig.calls.write_text("", encoding="utf-8")
    result = rig.run("check", SITE_E2E_SNAPSHOT=str(rig.e2e))

    script = rig.web / "scripts/check-out.ts"
    expected = [
        (name, snapshot, flag)
        for name, snapshot, flag in (
            ("fixture-full", rig.full, ""),
            ("fixture-full-indexable", rig.full, "1"),
            ("fixture-empty", rig.empty, ""),
            ("e2e", rig.e2e, ""),
        )
    ]
    assert result.returncode == 0, result.stdout
    assert rig.calls_of("node") == [
        ("node", f"{script} --snapshot {snapshot} --out {rig.builds / name}", "", flag)
        for name, snapshot, flag in expected
    ]


@pytest.mark.parametrize(
    ("tool", "command", "message"),
    [
        ("uv", "build", "HATA: anlık görüntü doğrulanmadı: fixture-full"),
        ("pnpm", "build", "HATA: derleme düştü: fixture-full"),
        ("node", "check", ""),
    ],
)
def test_a_red_tool_makes_its_subcommand_red(
    tmp_path: Path, tool: str, command: str, message: str
) -> None:
    """I3: `verify-snapshot`, derleme ya da çıktı tarayıcısı kırmızıysa alt komut da kırmızı —
    `|| true` ile yutulamaz. Doğrulama düşünce derleme hiç koşmaz."""
    rig = Rig(tmp_path)
    if command == "check":
        assert rig.run("build").returncode == 0
    rig.fail(tool)
    result = rig.run(command)

    assert result.returncode == 1, result.stdout
    assert message in result.stdout
    if tool == "uv":
        assert rig.calls_of("pnpm") == []


@pytest.mark.parametrize("command", ["build", "check"])
def test_ci_without_the_end_to_end_variant_is_red_even_if_verify_sh_lets_it_through(
    tmp_path: Path, command: str
) -> None:
    """I1: `verify.sh`in e2e kararı bu alt komutlara `SITE_E2E_SNAPSHOT` ile ulaşır. Bağ koparsa
    (değişken dışa verilmez, varyant listeden düşer) `CI=true` iken derleme ve tarama kırmızıdır;
    yerelde kırmızı değildir (yerel SKIP'i `verify.sh` adıyla basar)."""
    rig = Rig(tmp_path)
    assert rig.run("build", SITE_E2E_SNAPSHOT=str(rig.e2e)).returncode == 0

    missing = rig.run(command, CI="true")
    assert missing.returncode == 1
    assert "uçtan uca varyant işlenmedi" in missing.stdout
    assert rig.run(command).returncode == 0
    assert rig.run(command, CI="true", SITE_E2E_SNAPSHOT=str(rig.e2e)).returncode == 0


def test_install_refuses_a_wrong_toolchain_before_installing(tmp_path: Path) -> None:
    """I3: `site-kurulum` araç zinciri bekçisini atlayamaz — Node 22'de `pnpm install` koşmaz."""
    rig = Rig(tmp_path)
    (rig.flags / "node-version").write_text("22\n", encoding="utf-8")
    wrong = rig.run("install")

    assert (wrong.returncode, wrong.stdout.strip()) == (1, "HATA: Node 22, .nvmrc 24 istiyor")
    assert [args for _, args, _, _ in rig.calls_of("pnpm")] == ["--version"]

    (rig.flags / "node-version").write_text("24\n", encoding="utf-8")
    rig.calls.write_text("", encoding="utf-8")
    assert rig.run("install").returncode == 0
    assert [(tool, args) for tool, args, _, _ in rig.calls_of("node", "pnpm")] == [
        ("node", '-p process.versions.node.split(".")[0]'),
        ("pnpm", "--version"),
        ("pnpm", f"-C {rig.web} install --frozen-lockfile"),
    ]


def test_node_tools_see_only_the_allowlisted_environment(tmp_path: Path) -> None:
    """I4 (controller kararı, spec H5d): pnpm/node alt süreçleri DB adresini, API anahtarlarını ve
    Netlify kimliğini görmez; ortamları izin listesidir. Kanaryaların betiğe ULAŞTIĞI sahte `uv`un
    ortamından görülür (izin listesi dışındaki Python adımı), yani test boş geçmez."""
    rig = Rig(tmp_path)
    canaries = {name: "kanarya-degeri" for name in CANARIES}
    env = {**canaries, "SITE_E2E_SNAPSHOT": str(rig.e2e), "TMPDIR": str(tmp_path)}
    commands = ("install", "tip", "lint", "test", "build", "check")
    results = {command: rig.run(command, **env).returncode for command in commands}

    assert results == dict.fromkeys(commands, 0)
    node_envs = rig.env_names("pnpm") + rig.env_names("node")
    assert len(node_envs) == len(rig.calls_of("pnpm", "node")) == 14  # 3 kurulum + 3 + 4 + 4
    for names in node_envs:
        assert names.isdisjoint(CANARIES), names & CANARIES
        assert names <= NODE_ENV_ALLOW | SHELL_ADDED, names - NODE_ENV_ALLOW - SHELL_ADDED
    assert all(names >= CANARIES for names in rig.env_names("uv"))
    assert [args for _, args, _, _ in rig.calls_of("pnpm")][2:5] == [
        f"-C {rig.web} exec tsc --noEmit",
        f"-C {rig.web} exec biome ci .",
        f"-C {rig.web} exec vitest run",
    ]


# `verify.sh`in site bloğu baytla sabittir (I1, I3): adım komutları, e2e kararının okunuşu ve
# SKIP/FAIL ayrımı. B-1'in kendi komutlarını sabitlediği gibi (`tests/test_site_gate.py`).
VERIFY_SITE_BLOCK = """\
SITE_BUILDS="$(mktemp -d "${TMPDIR:-/tmp}/site-builds.XXXXXX")"
export SITE_BUILDS
SITE_E2E_SNAPSHOT=""
e2e_decision="$(./scripts/site_gate.sh e2e)"
case "$e2e_decision" in
  "USE "*) SITE_E2E_SNAPSHOT="${e2e_decision#USE }" ;;
  "SKIP "*) echo "SKIP: site-derleme/e2e (${e2e_decision#SKIP })" | tee -a "$LOG" ;;
  *)
    echo "$e2e_decision" | tee -a "$LOG"
    step "site-e2e" false
    ;;
esac
export SITE_E2E_SNAPSHOT
step "site-kurulum" ./scripts/site_gate.sh install
step "site-tip"     ./scripts/site_gate.sh tip
step "site-lint"    ./scripts/site_gate.sh lint
step "site-test"    ./scripts/site_gate.sh test
step "site-derleme" ./scripts/site_gate.sh build
step "site-uyum"    ./scripts/site_gate.sh check
"""


def test_the_verify_site_block_is_pinned_byte_for_byte() -> None:
    text = VERIFY.read_text(encoding="utf-8")
    start = text.index('SITE_BUILDS="$(mktemp -d')
    end = text.index('step "site-uyum"', start)
    assert text[start : text.index("\n", end) + 1] == VERIFY_SITE_BLOCK
    assert not re.search(r"^\s*step \"site-[^\"]+\"\s+pnpm", text, flags=re.M)
