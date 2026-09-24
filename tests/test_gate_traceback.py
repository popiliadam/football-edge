"""Kapı ve kum havuzu pytest'i kısa traceback'le koşar: parola loga düşmesin (Task 6, N2).

pytest'in varsayılan (uzun) traceback'i her karenin yerel değişkenlerini basar. Bağlantı
kurulamayınca psycopg karesindeki `conninfo` bağlantı dizesini — PAROLA dâhil — taşır: yerel kum
havuzunda on kez ölçüldü. `verify.sh` canlı `DATABASE_URL` ile koşunca aynı yol canlı parolayı
kapı loguna yazardı.
`--tb=short|line|no` yerel değişken basmaz. Bu dosya, test KOŞTURAN her pytest çağrısının bunu
taşıdığını sabitler; `--collect-only` test koşturmaz ve kapsam dışıdır. `-l`/`--showlocals`
(`-ql`, `-lrs` gibi kümeler dâhil) `--tb=short` ile de yerel değişken basar, `--tb=long|auto` sonra
gelirse kısayı ezer, `--full-trace` kısaltmayı kapatır: hepsi reddedilir (B-1 son düzeltme yeniden
incelemesi (c)). Satır sonu yorumu koşu sayılmaz (DEFERRED 18g a). Ölçmediği:
`PYTEST_ADDOPTS` ve `pyproject` `addopts` (çağıranın ortamı).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SAFE_TRACEBACK = re.compile(r"--tb[= ](short|line|no)\b")
LOCALS = re.compile(
    r"(?:^|\s)(?:-[qvxs]*l\S*|--showlocals|--full-trace|--tb[= ](?:long|auto))(?=\s|$)"
)
COMMENT = re.compile(r"(?:^|\s)#.*$")


def _pytest_runs(path: Path) -> list[str]:
    runs = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = COMMENT.sub("", raw)
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
        assert not LOCALS.search(run), f"{script}: yerel değişkenler parolayı basar — {run}"


@pytest.mark.parametrize(
    "line",
    [
        "uv run pytest --tb=short -l",
        "uv run pytest -ql --tb=short",
        "uv run pytest --tb=short --showlocals",
        "uv run pytest --tb=short --tb=long",
        "uv run pytest --tb=short --tb auto",
        "uv run pytest -lrs --tb=short",
        "uv run pytest -qlrs --tb=short",
        "uv run pytest --tb=short --full-trace",
    ],
)
def test_the_locals_guard_names_each_unsafe_flag(line: str) -> None:
    assert LOCALS.search(line)
    assert not LOCALS.search("uv run pytest -q -rs -m 'not sitedb' -p no:cacheprovider --tb=short")
