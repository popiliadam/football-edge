"""Kapı ve kum havuzu pytest'i kısa traceback'le koşar: parola loga düşmesin (Task 6, N2).

pytest'in varsayılan (uzun) traceback'i her karenin yerel değişkenlerini basar. Bağlantı
kurulamayınca psycopg karesindeki `conninfo` bağlantı dizesini — PAROLA dâhil — taşır: yerel kum
havuzunda on kez ölçüldü. `verify.sh` canlı `DATABASE_URL` ile koşunca aynı yol canlı parolayı
kapı loguna yazardı.
`--tb=short|line|no` yerel değişken basmaz. Bu dosya, test KOŞTURAN her pytest çağrısının bunu
taşıdığını sabitler; `--collect-only` test koşturmaz ve kapsam dışıdır.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SAFE_TRACEBACK = re.compile(r"--tb[= ](short|line|no)\b")


def _pytest_runs(path: Path) -> list[str]:
    runs = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0] if raw.lstrip().startswith("#") else raw
        if "uv run pytest" in line and "--collect-only" not in line:
            runs.append(line.strip())
    return runs


@pytest.mark.parametrize(
    ("script", "expected_runs"),
    [("verify.sh", 4), ("scripts/sandbox_db.sh", 1)],
)
def test_every_pytest_run_prints_no_local_variables(script: str, expected_runs: int) -> None:
    runs = _pytest_runs(REPO / script)

    assert len(runs) == expected_runs, f"{script}: pytest çağrısı sayısı değişti — {runs}"
    for run in runs:
        assert SAFE_TRACEBACK.search(run), f"{script}: uzun traceback parolayı basar — {run}"
