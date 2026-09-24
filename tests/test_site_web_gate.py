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
