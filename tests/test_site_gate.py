"""Site kapısının bağlantısı (§12.1–12.2, B10): CI kabı, `site-db` adımı, bayat dosya kimliği.

Metin ve ayrıştırılmış YAML okunur; kabın gerçekten kalktığını CI koşusunun kendisi kanıtlar
(Task 9 raporu).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from tests.workflow_helpers import _index_of, _steps

REPO = Path(__file__).resolve().parent.parent
CI = REPO / ".github/workflows/ci.yml"
VERIFY = REPO / "verify.sh"
T0_RECORD = REPO / "docs/phases/06-site/b1-t0-olcumler.md"
SITE_DB = "Site test veritabanı"
# Parçalardan: test DB adresini yalnız `tests/site_db.py` anar (`test_site_harness_rules.py`).
VAR = "SITE_TEST_" + "DATABASE_URL"


def _recorded(key: str) -> str:
    (value,) = re.findall(rf"^{key}=(\S+)$", T0_RECORD.read_text(encoding="utf-8"), re.M)
    return value


def _site_db_step() -> dict[str, object]:
    (step,) = [step for step in _steps(CI) if step.get("name") == SITE_DB]
    return step


def test_ci_starts_the_site_database_before_the_gate() -> None:
    steps = _steps(CI)
    sync, site_db, gate = (
        _index_of(steps, "uv sync"),
        _index_of(steps, SITE_DB, key="name"),
        _index_of(steps, "./verify.sh"),
    )

    assert None not in (sync, site_db, gate)
    assert sync < site_db < gate  # type: ignore[operator]


def test_the_ci_image_is_the_t0_pinned_image_with_its_digest() -> None:
    """Tek kaynak: T0 kaydı. Etiket kayarsa CI başka bir Postgres'i ölçerdi."""
    env = _site_db_step()["env"]

    assert env == {"SITE_DB_IMAGE": f"{_recorded('image')}@{_recorded('image_digest')}"}  # type: ignore[comparison-overlap]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", _recorded("image_digest"))


def test_the_site_database_is_local_and_its_password_is_generated_and_masked() -> None:
    run = str(_site_db_step()["run"])

    assert 'password="$(openssl rand -hex 16)"' in run
    assert 'echo "::add-mask::${password}"' in run
    assert "-p 127.0.0.1:55432:5432" in run
    assert 'address="postgresql://postgres:${password}@127.0.0.1:55432/postgres"' in run
    assert 'for name in "SITE_TEST_' + 'DATABASE""_URL" "SANDBOX_DATABASE""_URL"; do' in run
    assert 'echo "${name}=${address}" >> "${GITHUB_ENV}"' in run
    assert "secrets." not in yaml.safe_dump(_site_db_step())


def test_ci_never_prints_the_container_log() -> None:
    """supabase/postgres imajı ilk kurulumda kap parolasını kendi loguna yazar; `::add-mask::`
    yalnız bu adımın çıktısını maskeler, `docker logs` kuyruğu açık CI loguna parolayı taşırdı."""
    runs = [str(step.get("run", "")) for step in _steps(CI)]

    assert not [run for run in runs if re.search(r"docker\s+(container\s+)?logs\b", run)]


def _verify_text() -> str:
    return VERIFY.read_text(encoding="utf-8")


def test_the_run_id_is_exported_before_any_step() -> None:
    text = _verify_text()

    assert text.index("export FE_VERIFY_RUN_ID") < text.index('step "ruff-check"')


def test_sitedb_tests_run_exactly_once_in_their_own_step() -> None:
    text = _verify_text()

    assert 'step "pytest"      uv run pytest -q -m "not sitedb" --tb=short' in text
    assert text.count('-m "leakage and not sitedb"') == 2
    assert "uv run pytest tests/ -q -m sitedb -rs --tb=short" in text
    assert "EXPECTED_MIN_SITEDB_LEAKAGE=" in text and 'count "sitedb and leakage"' in text


def test_site_db_is_red_in_ci_and_named_skip_locally_without_a_database() -> None:
    text = _verify_text()
    branch = text[text.index(f'if [ -n "${{{VAR}:-}}" ]; then') :]

    assert 'elif [ "${CI:-}" = "true" ]; then' in branch
    assert 'site-db atlanamaz (B10)"; exit 1' in branch
    assert f'echo "SKIP: site-db ({VAR} yok)"' in branch


def test_the_end_to_end_directory_is_emptied_before_the_step_without_deleting() -> None:
    text = _verify_text()
    start = text.index('SITE_E2E_DIR="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/site-e2e"')
    block = text[start : text.index(f'if [ -n "${{{VAR}:-}}" ]; then')]

    for name in ("snapshot.json", "snapshot.sha256", "run-id"):
        assert f': > "$SITE_E2E_DIR/{name}"' in block
    assert "rm " not in block
