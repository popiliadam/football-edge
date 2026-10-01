"""Site kapısının bağlantısı (§12.1–12.2, B10): CI kabı, `site-db` adımı, bayat dosya kimliği.

Metin ve ayrıştırılmış YAML okunur; kabın gerçekten kalktığını CI koşusunun kendisi kanıtlar
(Task 9 raporu).
"""

from __future__ import annotations

import re
import shlex
import time
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


# `docker` ile alt komut arasında genel bayraklar olabilir (`--log-level error`, `-H unix://…`,
# `-D`) — N-6. Bayrak en çok bir değer alır; değersiz bayrakta regex geri izler. `(?!-)`:
# `--x` tek yoldan eşlenir, yoksa arama bayrak sayısında üstel olurdu (N-10).
DOCKER = r"\bdocker(?:\s+-{1,2}(?!-)[^\s=]+(?:=\S+|\s+(?!-)\S+)?)*\s+(?:container\s+)?"
INSPECT = re.compile(DOCKER + r"inspect\b")
LOGS = re.compile(DOCKER + r"logs\b")
# Kaba seçim (N-11): satırda `docker` ve `inspect` sözcükleri, sırasız. Tırnaklı ya da ANSI-C
# alt komut (`docker "inspect"`, `docker $'inspect'`) ham regex'ten kaçar ama bu kuraldan kaçmaz.
DOCKER_WORD = re.compile(r"\bdocker\b")
INSPECT_WORD = re.compile(r"\binspect\b")


# Şablonun TEK izinli eylem biçimi (gerçek beyaz liste, eylem başına tam eşleşme):
# `{{.State.X}}`, `{{$.State.X.Y}}`, `{{json .State.X}}`, `{{printf "%s" .State.X}}`.
# Kök (`.`, `$`), `index`, `range`, boru, değişken — geri kalan her şey kırmızı.
STATE_ACTION = re.compile(r'\s*(?:json\s+|printf\s+"[^"{}]*"\s+)?\$?\.State(?:\.[A-Za-z_]\w*)+\s*')
# Komut ayırıcı token'ları (`&&`, `||`, `;`, `|`, `&`, parantez); yönlendirme (`2>&1`) değil.
SEPARATOR = frozenset(";&|()")


def _commands(line: str) -> list[list[str]] | None:
    """Mantıksal satırın kabuk komutları (sözcük listeleri); bölünemezse `None`."""
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""  # hiçbir metin atılmaz: `#` yorum sayılmaz
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    commands: list[list[str]] = [[]]
    for token in tokens:
        if set(token) <= SEPARATOR:
            commands.append([])
        else:
            commands[-1].append(token)
    return [command for command in commands if command]


def _templates(command: list[str]) -> list[str]:
    """Komuttaki HER `-f x`, `--format x`, `--format=x`, `-fx` şablonu (N-2): docker
    yinelenen bayrakta sonuncuyu kullanır, bekçi hangisi kazanırsa kazansın hepsini denetler.
    Değersiz sondaki `-f` boş şablon sayılır (doğrulanamaz → kırmızı)."""
    found = []
    for index, word in enumerate(command):
        if word in ("-f", "--format"):
            found.append(command[index + 1] if index + 1 < len(command) else "")
        elif word.startswith("--format="):
            found.append(word.split("=", 1)[1])
        elif word.startswith("-f") and not word.startswith("--") and len(word) > 2:
            found.append(word[2:])
    return found


def _template_leaks(templates: list[str]) -> list[str]:
    if not templates:
        return ["-f/--format yok: çıplak inspect bütün nesneyi basar"]
    leaks = []
    for template in templates:
        actions = re.findall(r"\{\{(.*?)\}\}", template)
        outside = re.sub(r"\{\{.*?\}\}", "", template)
        if not actions or "$" in outside or "`" in outside:
            leaks.append(f"şablon doğrulanamaz: {template!r}")
        leaks.extend(action for action in actions if not STATE_ACTION.fullmatch(action))
    return leaks


def _inspect_leaks(line: str) -> list[str]:
    """`docker inspect` satırının basabileceği yasak içerik; boş liste = güvenli (21a).

    Beyaz liste, eylem başına: yalnız `.State.<alan>` (önünde `$`, `json` ya da `printf "…"`
    olabilir). Kök — `.` ya da `$` (`{{json .}}`, `{{.}}`, `{{json $}}`, `{{index . "Config"}}`,
    `{{range … := $}}`) — bütün nesneyi, `Config.Env` (kap parolası) dâhil basar; çıplak
    `.State` de bütün durum nesnesidir. Komuttaki HER `-f`/`--format` şablonu denetlenir (N-2);
    satırdaki HER `docker inspect` komutu ayrı denetlenir
    (`a && docker inspect x` ikincisini de, I-2); ham metindeki inspect sayısı okunabilen
    komut sayısını aşarsa (tırnak, `$(…)` içinde) satır doğrulanamaz, reddedilir."""
    commands = _commands(line)
    if commands is None:
        return ["satır kabuk sözcüklerine bölünemiyor: doğrulanamaz"]
    inspects = [command for command in commands if INSPECT.search(" ".join(command))]
    if len(inspects) != len(INSPECT.findall(line)):
        return ["inspect komutu kabuk düzeyinde okunamıyor (tırnak ya da `$(…)` içinde)"]
    if not inspects and _coarse_inspect(line):
        return ["satırda `docker` ve `inspect` var ama inspect komutu okunamıyor"]
    return [leak for command in inspects for leak in _template_leaks(_templates(command))]


def _coarse_inspect(line: str) -> bool:
    return bool(DOCKER_WORD.search(line) and INSPECT_WORD.search(line))


def _inspect_lines(script: str) -> list[str]:
    """Denetlenecek satırlar: ham `INSPECT` regex'i YA DA kaba sözcük kuralı (N-11)."""
    return [
        line for line in _logical_lines(script) if INSPECT.search(line) or _coarse_inspect(line)
    ]


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
        # Düzeltme turu 1 (I-2): Go şablonunun kök değişkeni `$` bütün nesnedir.
        "docker inspect -f '{{json $}}' fe-site-db",
        "docker inspect -f '{{$}}' fe-site-db",
        "docker inspect -f '{{printf \"%v\" $}}' fe-site-db",
        "docker inspect -f '{{range $k, $v := $}}{{$k}}{{end}}' fe-site-db",
        # Aynı mantıksal satırda ikinci, çıplak inspect — düz ya da `\` ile bölünmüş.
        "docker inspect -f '{{.State.Status}}' a && docker inspect fe-site-db",
        "docker inspect -f '{{.State.Status}}' a \\\n  && docker inspect fe-site-db",
        "docker inspect -f '{{.State.Status}}' a; docker container inspect fe-site-db",
        'echo "$(docker inspect fe-site-db)"',
        "docker inspect -f '{{.State.Status}}' \"$(docker inspect fe-site-db)\"",
        'docker inspect -f "{{.State.Status}}$EK" fe-site-db',
        # Düzeltme turu 2 (N-2): yinelenen bayrakta docker sonuncuyu kullanır — hepsi denetlenir.
        "docker inspect -f '{{.State.Status}}' -f '{{json .}}' fe-site-db",
        "docker inspect --format '{{.State.Status}}' --format='{{json .Config.Env}}' fe-site-db",
        "docker inspect -f='{{.State.Status}}' fe-site-db -f '{{json .}}'",
        # N-6: genel docker bayrağı inspect'ten önce.
        "docker --log-level error inspect fe-site-db",
        "docker -H unix:///var/run/docker.sock container inspect fe-site-db",
        # Düzeltme turu 3 (N-9): sızıntı İLK şablonda — "yalnız sonuncu (kazanan)" da ölür.
        "docker inspect -f '{{json .}}' -f '{{.State.Status}}' fe-site-db",
        # N-8, N-11: kelime ortasında satır devamı; tırnaklı ya da ANSI-C alt komut.
        "docker ins\\\npect fe-site-db",
        'docker "inspect" fe-site-db',
        '"docker" inspect fe-site-db',
        "docker $'inspect' fe-site-db",
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
        "json-dolar",
        "dolar",
        "printf-dolar",
        "range-dolar",
        "zincirli-ciplak",
        "zincirli-devam-ciplak",
        "noktali-virgul-ciplak",
        "komut-ikamesi-ciplak",
        "ic-ice-ikame",
        "sablona-degisken-eki",
        "cift-f",
        "cift-format",
        "f-esittir-sonra-f",
        "genel-bayrak-log-level",
        "genel-bayrak-H",
        "ilk-sablon-sizinti",
        "kelime-ortasi-devam",
        "tirnakli-alt-komut",
        "tirnakli-docker",
        "ansi-c-alt-komut",
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
        "docker inspect -f '{{json .State.Health.Status}} {{$.State.Pid}}' fe-site-db",
        "docker inspect -f '{{printf \"%s\" .State.Status}}' fe-site-db 2>&1 | tee durum.txt",
        "docker inspect -f '{{.State.Status}}' a && docker inspect -f '{{.State.Pid}}' b",
        "docker inspect -f '{{.State.Status}}' -f '{{.State.Pid}}' fe-site-db",
        "docker --log-level error inspect -f '{{.State.Status}}' fe-site-db",
        # `#` yorum sayılmaz: kelime içindeki `#` inspect'i gizlemez, okunur.
        "n=${#a[@]}; docker inspect -f '{{.State.Status}}' fe-site-db",
    ],
    ids=[
        "bugunku-ci",
        "format-saglik",
        "format-esittir-devam",
        "json-ve-dolar-state",
        "printf-boru",
        "zincirli-iki-state",
        "iki-f-ikisi-state",
        "genel-bayrak-state",
        "kelime-ici-diyez-state",
    ],
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


def test_the_docker_flag_pattern_is_linear_in_the_number_of_flags() -> None:
    """N-10: `--?[^\\s=]+` `--x`i iki yoldan eşleyince arama bayrak sayısında üstel geri izler
    (n=22'de ~1 sn). Ayrık bayrak kalıbıyla 24 bayrak anında taranır."""
    line = "docker " + " ".join(f"--b{index}" for index in range(24)) + " ps"
    started = time.perf_counter()

    assert INSPECT.search(line) is None
    assert time.perf_counter() - started < 1.0
