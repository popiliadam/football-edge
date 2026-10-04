"""Jev adımlarının (kademe 1 `collect-news.yml`, kademe 2 `shadow.yml`) ortak sınama yardımcıları.

Adımın `run:` gövdesi `uv` yerine kayıt tutan bir sahteyle `bash -e -c` altında koşulur
(`test_collect_workflows.py` deseni); `GITHUB_OUTPUT` ve `GITHUB_STEP_SUMMARY` geçici dosyadır.
Secret adı parçalardan kurulur: kapının secrets adımı testleri de tarar.
"""

from __future__ import annotations

import copy
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests.workflow_helpers import _index_of

JEV_SECRET = "TYPESAFE" + "_API_KEY"
# Toplama exit 7 (bir kaynak düştü) senkronu ve kademe 1'i durdurmaz (I-6, I-7); tur yine kırmızı
# biter çünkü toplama adımının kendisi 7 döner. Taramaya bağlı: kırmızı taramadan sonra secret'lı
# adım koşmaz (DEFERRED 19b, `test_secrets_scan_netlify.py`).
AFTER_FETCH = (
    "${{ !cancelled() && steps.secret_scan.outcome == 'success' && "
    "(success() || steps.fetch.outputs.code == '7') }}"
)
# (komutun kodu, JEV_ENABLED, beklenen `jev` çıktısı, hata satırında geçmesi gereken sözcük)
JEV_CASES = [
    (0, None, "ok", ""),
    (17, None, "ok", ""),
    (17, "1", "fail", "JEV_ENABLED"),
    (7, None, "fail", "kesinti"),
    (16, None, "fail", "tavan"),
    (1, None, "fail", "beklenmedik"),
]
JEV_CASE_IDS = ["ok", "off-17", "enabled-17", "outage-7", "budget-16", "other-1"]
# Ücret yamasının (R177) Jev adımına eklediği env satırları — yamalı/yamasız hâl ikisi de geçerli.
SWITCH = {JEV_SECRET: "${{ secrets." + JEV_SECRET + " }}", "JEV_ENABLED": "1"}
FAKE_UV = """\
#!/usr/bin/env bash
echo "$*" >> "$CALLS"
exit "${FAIL_CODE:-0}"
"""


@dataclass(frozen=True)
class StepRun:
    returncode: int
    errors: tuple[str, ...]
    outputs: dict[str, str]
    summary: str
    calls: tuple[str, ...]


def run_step(tmp_path: Path, body: str, *, code: int, jev_enabled: str | None = None) -> StepRun:
    fake = tmp_path / "uv"
    fake.write_text(FAKE_UV, encoding="utf-8")
    fake.chmod(0o755)
    calls, output, summary = tmp_path / "calls", tmp_path / "output", tmp_path / "summary.md"
    for path in (calls, output, summary):
        path.touch()
    env = {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "CALLS": str(calls),
        "FAIL_CODE": str(code),
        "GITHUB_OUTPUT": str(output),
        "GITHUB_STEP_SUMMARY": str(summary),
        **({} if jev_enabled is None else {"JEV_ENABLED": jev_enabled}),
    }
    result = subprocess.run(
        ["bash", "-e", "-c", body], env=env, capture_output=True, text=True, timeout=30, check=False
    )
    lines = output.read_text(encoding="utf-8").splitlines()
    return StepRun(
        returncode=result.returncode,
        errors=tuple(line for line in result.stdout.splitlines() if line.startswith("::error::")),
        outputs=dict(line.split("=", 1) for line in lines if "=" in line),
        summary=summary.read_text(encoding="utf-8"),
        calls=tuple(calls.read_text(encoding="utf-8").splitlines()),
    )


def with_jev_key(document: dict[str, Any], needle: str) -> dict[str, Any]:
    """Ücreti açan commit'in (R177) belgeye yaptığı tek şey: Jev adımının env'ine iki satır."""
    switched = copy.deepcopy(document)
    ((_, job),) = switched["jobs"].items()
    index = _index_of(job["steps"], needle)
    assert index is not None, f"{needle} adımı yok"
    step = job["steps"][index]
    step["env"] = {**step["env"], **SWITCH}
    return switched
