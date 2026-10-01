"""Site kapısının bağlantısı (§12.1–12.2, B10): CI kabı, `site-db` adımı, bayat dosya kimliği.

Metin ve ayrıştırılmış YAML okunur; kabın gerçekten kalktığını CI koşusunun kendisi kanıtlar
(Task 9 raporu).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from tests.workflow_helpers import _index_of, _logical_lines, _steps

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


INSPECT = re.compile(r"\bdocker\s+(?:container\s+)?inspect\b")
LOGS = re.compile(r"\bdocker\s+(?:container\s+)?logs\b")


# `-f`/`--format`: `-f 'x'`, `--format 'x'`, `--format='x'`.
FORMAT = re.compile(r"\s(?:-f|--format)(?:\s|=)")
# Şablon eylemindeki alan başvurusu: `.`, `.State.Status`, `$.Config` (önünde ad/kapanış yok).
FIELD = re.compile(r"(?<![\w)\]])\.(?:[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)?")
STATE_FIELD = re.compile(r"\.State(?:\.[A-Za-z_]\w*)+")


def _inspect_leaks(line: str) -> list[str]:
    """`docker inspect` satırının basabileceği yasak alanlar; boş liste = güvenli (21a).

    Beyaz liste: `-f`/`--format` şablonunda yalnız `.State.<alan>`. Kök (`.` — `{{json .}}`,
    `{{.}}`, `{{index . "Config"}}`) bütün nesneyi, `Config.Env` (kap parolası) dâhil basar;
    çıplak `.State` de bütün durum nesnesidir. Şablonu satırda okunamayan biçim
    (`-f "$BICIM"`) doğrulanamaz, reddedilir. Dize sabitleri alan sayılmaz."""
    if not FORMAT.search(line):
        return ["-f/--format yok: çıplak inspect bütün nesneyi basar"]
    actions = re.findall(r"\{\{(.*?)\}\}", line)
    if not actions:
        return ["şablon satırda değil: doğrulanamaz"]
    fields = [
        field
        for action in actions
        for field in FIELD.findall(re.sub(r'"[^"]*"|`[^`]*`', "", action))
    ]
    return [field for field in fields if not STATE_FIELD.fullmatch(field)]


def _inspect_lines(script: str) -> list[str]:
    return [line for line in _logical_lines(script) if INSPECT.search(line)]


def test_ci_never_prints_the_container_log() -> None:
    """Derinlemesine savunma: supabase/postgres imajı ilk kurulumda kap parolasını düz metin olarak
    kendi loguna yazar; `::add-mask::` tam dize eşleşmesine dayanan en iyi çaba korumasıdır. Log hiç
    basılmaz. `inspect` yalnız `-f`/`--format` biçimiyle ve yalnız `.State.<alan>` şablonuyla:
    çıplak `inspect`, `{{json .}}` ve `{{json .Config.Env}}` `Config.Env`i (parola) basar
    (19c, 21a). Betik mantıksal satırlarla okunur: `\\` ile bölünmüş komut birleştirilir."""
    runs = [str(step.get("run", "")) for step in _steps(CI)]
    inspects = [line for run in runs for line in _inspect_lines(run)]

    assert not [run for run in runs if any(LOGS.search(line) for line in _logical_lines(run))]
    assert inspects, "ci.yml kabın durumunu hiç basmıyor — test kurgusu bayatlamış"
    assert [line for line in inspects if _inspect_leaks(line)] == [], inspects


@pytest.mark.parametrize(
    "run",
    [
        "docker inspect fe-site-db",
        "docker inspect -f '{{json .}}' fe-site-db",
        "docker inspect --format '{{.}}' fe-site-db",
        "docker container inspect -f '{{json .Config.Env}}' fe-site-db",
        "docker inspect --format='{{index . \"Config\"}}' fe-site-db",
        "docker inspect -f '{{json .State}}' fe-site-db",
        'docker inspect -f "$BICIM" fe-site-db',
        "docker inspect -f \\\n  '{{json .Config.Env}}' fe-site-db",
        "docker \\\n  inspect fe-site-db",
    ],
    ids=[
        "ciplak",
        "json-kok",
        "kok",
        "config",
        "index-kok",
        "state-butun",
        "degiskende-sablon",
        "satir-devami-sablon",
        "satir-devami-ciplak",
    ],
)
def test_the_inspect_guard_rejects_any_template_beyond_state_fields(run: str) -> None:
    """21a: `-f`/`--format` şablonunda yalnız `.State.<alan>` serbest (beyaz liste). Kök (`.`,
    `json .`, `index . …`) `Config.Env`i de taşır; `\\` ile bölünmüş satır birleştirilerek
    okunur."""
    lines = _inspect_lines(run)

    assert any(_inspect_leaks(line) for line in lines), lines


@pytest.mark.parametrize(
    "run",
    [
        # ci.yml'in bugünkü satırı (kısaltılmış).
        "docker container inspect -f 'durum={{.State.Status}} oom={{.State.OOMKilled}}' fe-site-db",
        "docker inspect --format '{{.State.Health.Status}}' fe-site-db",
        "docker inspect --format='{{.State.Running}}' \\\n  fe-site-db",
    ],
    ids=["bugunku-ci", "format-saglik", "format-esittir-devam"],
)
def test_the_inspect_guard_accepts_state_fields(run: str) -> None:
    lines = _inspect_lines(run)

    assert lines and [line for line in lines if _inspect_leaks(line)] == []


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

    assert "export SITE_E2E_DIR" in block
    for name in ("snapshot.json", "snapshot.sha256", "run-id"):
        assert f': > "$SITE_E2E_DIR/{name}"' in block
    assert "rm " not in block
