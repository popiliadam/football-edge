"""`site.yml` (§11, H5d): elle tetiklenir; derleme işi DB adresini, yayın işi Netlify'ı görür.

Ham metin taraması değil ayrıştırılmış belge okunur (`tests/test_workflows.py` gerekçesi: yorum da
secret adını yazar). Secret yalnız bir adımın `env`inde durabilir; `run` metnine gömülürse betik
metnine girer. Adım düzeyindeki sınır aynı iş içinde yalıtım DEĞİLDİR (adımlar makineyi, `$HOME`u,
`$GITHUB_PATH`/`$GITHUB_ENV`i ve npm önbelleğini paylaşır; inceleme I1): Netlify kimliği bu yüzden
ayrı, taze bir işte, beş adımı sabit (kurulumsuz) yayın adımındadır; yayın sonrası kontrol üçüncü,
secret'sız bir iştedir. Kırmızı bir adımdan sonra hiçbir şey koşmaz (inceleme I3, N2): `if:`,
`continue-on-error`, `shell:`/`defaults:`, `||` ile atlanamaz; kapı komutları tam sabittir.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from tests.workflow_helpers import _index_of, _steps, _triggers

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / ".github/workflows/site.yml"
T0_RECORD = REPO / "docs/phases/06-site/b1-t0-olcumler.md"
EXPORT = "football_edge.site export"
VERIFY = "football_edge.site verify-snapshot"
CHECK_OUT = "web/scripts/check-out.ts"
DEPLOY = "deploy --prod --dir web/out"
# Secret'lı iki adımın komutu TAM sabittir (inceleme m1): `set -x`, `env`, `echo "${X:0:12}"` ya da
# base64 gibi eklemeler maskelemeyi atlatır. B-2 T10 yayına `--no-build`ı ekledi: netlify-cli v21+
# `deploy` yapılandırmadaki (bilerek düşen) derleme komutunu koşardı.
EXPORT_RUN = "uv run python -m football_edge.site export --out web/.snapshot"
DEPLOY_RUN = "netlify deploy --prod --dir web/out --no-build --config web/netlify.toml"
# Kapı komutları da TAM sabittir (inceleme N2): `| tee` (pipefail yok) ya da `set +e; …; true`
# kırmızıyı yutar.
SCAN_RUN = "./scripts/check_secrets.sh"
VERIFY_RUN = (
    "uv run python -m football_edge.site verify-snapshot web/.snapshot/snapshot.json"
    " --sha256 web/.snapshot/snapshot.sha256"
)
CHECK_RUN = "node web/scripts/check-out.ts --snapshot web/.snapshot/snapshot.json --out web/out"
# B-2 T10'un yerleri (controller kararı, T8 düzeltme turu 2): adım yazılana dek işaret satırı.
SLUGS = "scripts/site_publish.py slugs"
LIVE = "scripts/site_publish.py live"
SLUGS_MARK = "B-2 T10 → kaybolan-slug"
LIVE_MARK = "B-2 T10 → yayın sonrası kontrol"
MAIN_ONLY = "github.ref == 'refs/heads/main'"
DB = "SITE_DATABASE" + "_URL"
NETLIFY = {"NETLIFY_AUTH" + "_TOKEN", "NETLIFY_SITE" + "_ID"}
PIPELINE_ONLY = ("DATABASE" + "_URL", "ODDS_API" + "_KEY", "TYPESAFE_API" + "_KEY")
EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.S)
SECRETS = re.compile(r"\bsecrets\b")
NAMED = re.compile(r"\bsecrets\s*(?:\.\s*(\w+)|\[\s*['\"](\w+)['\"]\s*\])")
UNNAMED = "<secrets>"  # `toJSON(secrets)` gibi adsız erişim: bütün secret'lar


def _document() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(SITE.read_text(encoding="utf-8"))
    return loaded


def _jobs() -> dict[str, Any]:
    return dict(_document()["jobs"])


def _strings(node: Any) -> Iterator[str]:
    """Düğümdeki her anahtar ve değer dizesi. Döküm METNİ değil: `safe_dump` ASCII dışı skaleri
    80 sütunda katlar ve katlama `${{ … }}` içine düşerse ifade görünmez olur (inceleme I2)."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item)
    elif isinstance(node, str):
        yield node


def _secrets_in(node: Any) -> set[str]:
    """Her `${{ … }}` ifadesindeki HER `secrets` başvurusu: `secrets.X`, `secrets['X']`,
    `secrets.X || ''`; adı okunamayan başvuru (`toJSON(secrets)`) `<secrets>` olarak döner."""
    found: set[str] = set()
    for text in _strings(node):
        for expression in EXPRESSION.findall(text):
            named = [dotted or indexed for dotted, indexed in NAMED.findall(expression)]
            found.update(named)
            if len(SECRETS.findall(expression)) > len(named):
                found.add(UNNAMED)
    return found


def _uses(job: str, action: str) -> list[dict[str, Any]]:
    return [step for step in _steps(SITE, job) if str(step.get("uses", "")).startswith(action)]


def _runs(job: str) -> list[str]:
    return [str(step["run"]) for step in _steps(SITE, job) if "run" in step]


def test_site_is_dispatched_by_hand_only() -> None:
    """B9/AK15: `schedule`, `push`, pg_cron tetiği yok."""
    assert set(_triggers(SITE)) == {"workflow_dispatch"}


def test_site_reads_the_repository_and_deploys_one_at_a_time() -> None:
    document = _document()

    assert set(document["jobs"]) == {"build", "deploy", "live"}
    assert document["permissions"] == {"contents": "read"}
    assert all("permissions" not in job for job in document["jobs"].values())
    assert document["concurrency"] == {"group": "site-deploy", "cancel-in-progress": False}
    checkouts = {
        name: [s["with"] for s in _uses(name, "actions/checkout")] for name in document["jobs"]
    }
    assert checkouts == {
        "build": [{"fetch-depth": 0, "persist-credentials": False}],
        "deploy": [{"persist-credentials": False}],
        "live": [{"persist-credentials": False}],
    }


def test_no_secret_lives_at_workflow_or_job_level() -> None:
    document = _document()

    assert _secrets_in({key: value for key, value in document.items() if key != "jobs"}) == set()
    for job in document["jobs"].values():
        assert _secrets_in({key: value for key, value in job.items() if key != "steps"}) == set()


def test_each_secret_is_given_to_exactly_one_named_step_through_env() -> None:
    """H5d: DB adresi yalnız dışa aktarımda, Netlify kimliği yalnız yayında; öteki adımlar temiz."""
    expected = {
        "build": {_index_of(_steps(SITE, "build"), EXPORT): {DB}},
        "deploy": {_index_of(_steps(SITE, "deploy"), DEPLOY): NETLIFY},
        "live": {},
    }
    for job, want in expected.items():
        steps = _steps(SITE, job)
        given = {index: _secrets_in(step) for index, step in enumerate(steps) if _secrets_in(step)}

        assert given == want, job
        for index in given:
            step = steps[index]
            assert _secrets_in({key: value for key, value in step.items() if key != "env"}) == set()
            assert set(step["env"]) == given[index], "secret yalnız kendi adıyla env'e girer"


def test_the_two_secret_steps_run_exactly_their_command() -> None:
    build, deploy = _steps(SITE, "build"), _steps(SITE, "deploy")

    assert build[_index_of(build, EXPORT)]["run"] == EXPORT_RUN  # type: ignore[index]
    assert deploy[_index_of(deploy, DEPLOY)]["run"] == DEPLOY_RUN  # type: ignore[index]


def test_the_netlify_identity_never_enters_the_build_job_nor_the_database_the_deploy_job() -> None:
    """I1: derleme işinde Netlify'ın ADI bile geçmez; yayın işi DB adresini görmez."""
    build, deploy = _jobs()["build"], _jobs()["deploy"]

    assert _secrets_in(build) == {DB}
    assert not [text for text in _strings(build) if "NETLIFY" in text.upper()]
    assert _secrets_in(deploy) == NETLIFY
    assert not [text for text in _strings(deploy) if "DATABASE" in text.upper()]


def test_the_pipeline_credentials_never_reach_the_site_jobs() -> None:
    document = _document()
    names = {
        name
        for node in (document, *document["jobs"].values(), *_steps(SITE))
        for name in (node.get("env") or {})
    }

    assert names.isdisjoint(PIPELINE_ONLY)
    assert _secrets_in(document).isdisjoint({*PIPELINE_ONLY, UNNAMED})


def test_the_export_is_scanned_verified_and_precedes_every_node_step() -> None:
    steps = _steps(SITE, "build")
    scan = _index_of(steps, "scripts/check_secrets.sh")
    export = _index_of(steps, EXPORT)
    verify = _index_of(steps, VERIFY)
    node = _index_of(steps, "actions/setup-node", key="uses")
    check = _index_of(steps, CHECK_OUT)
    upload = _index_of(steps, "actions/upload-artifact", key="uses")

    assert None not in (scan, export, verify, node, check, upload)
    assert scan < export < verify < node < check < upload  # type: ignore[operator]
    assert [steps[i]["run"] for i in (scan, verify, check)] == [  # type: ignore[index]
        SCAN_RUN,
        VERIFY_RUN,
        CHECK_RUN,
    ]
    assert "uv sync --frozen" in _runs("build")
    assert "pnpm -C web install --frozen-lockfile" in _runs("build")


def test_the_deploy_job_takes_only_the_checked_build_from_main() -> None:
    """Yayın, derleme işi YEŞİLSE koşar (`needs` + örtük `success()`), yalnız `main`den ve
    `production` ortamında; derlenmiş siteyi artifact'tan alır."""
    build, deploy = _jobs()["build"], _jobs()["deploy"]
    (upload,) = _uses("build", "actions/upload-artifact")
    steps = _steps(SITE, "deploy")
    download = _index_of(steps, "actions/download-artifact", key="uses")

    assert deploy["needs"] in ("build", ["build"])
    assert deploy["if"] == MAIN_ONLY
    assert deploy["environment"] == "production"
    assert "needs" not in build
    assert upload["with"]["name"] == "site"
    assert set(upload["with"]["path"].split()) == {"web/out", "web/.snapshot/snapshot.sha256"}
    assert upload["with"]["if-no-files-found"] == "error"
    # `.snapshot` gizli dizin: bayrak düşerse sha256 artifact'tan SESSİZCE çıkar (inceleme N4).
    assert upload["with"]["include-hidden-files"] is True
    assert download is not None
    assert steps[download]["with"] == {"name": "site", "path": "web"}
    assert download < _index_of(steps, DEPLOY)  # type: ignore[operator]


def _deploy_steps() -> list[dict[str, Any]]:
    token = {name: "${{ secrets." + name + " }}" for name in NETLIFY}
    return [
        {"uses": "actions/checkout@v4", "with": {"persist-credentials": False}},
        {"uses": "actions/download-artifact@v4", "with": {"name": "site", "path": "web"}},
        {"uses": "actions/setup-node@v4", "with": {"node-version-file": "web/.nvmrc"}},
        {"name": "Netlify CLI", "run": "npm install --global netlify-cli@" + _t0_netlify_cli()},
        {"name": "Yayın", "env": token, "run": DEPLOY_RUN},
    ]


def test_the_deploy_job_is_exactly_five_steps_and_installs_nothing_else() -> None:
    """I1/N1: tokenlı işte bağımlılık kodu koşmaz. Pozitif liste — yasak listesi `uv sync`,
    `pip install`, iş düzeyinde `NODE_OPTIONS` gibi yeni yolları kaçırıyordu. B-2 T10 yalnız
    `DEPLOY_RUN`a `--no-build` ekler."""
    deploy = _jobs()["deploy"]

    assert set(deploy) == {"needs", "if", "environment", "runs-on", "timeout-minutes", "steps"}
    assert deploy["steps"] == _deploy_steps()


def test_the_post_deploy_check_has_its_own_secret_free_job_after_the_deploy() -> None:
    """Controller kararı (d): yayın sonrası kontrol `needs: deploy`, yalnız `main`, secret'sız,
    ortamsız bir iştedir; derleme tarafını artifact'tan alır."""
    live = _jobs()["live"]
    steps = _steps(SITE, "live")
    download = _index_of(steps, "actions/download-artifact", key="uses")

    assert set(live) == {"needs", "if", "runs-on", "timeout-minutes", "steps"}
    assert live["needs"] in ("deploy", ["deploy"])
    assert live["if"] == MAIN_ONLY
    assert _secrets_in(live) == set()
    assert not [text for text in _strings(live) if re.search("NETLIFY|DATABASE", text.upper())]
    assert download is not None
    assert steps[download]["with"] == {"name": "site", "path": "web"}


def _line(text: str) -> int:
    (index,) = [
        i for i, line in enumerate(SITE.read_text(encoding="utf-8").splitlines()) if text in line
    ]
    return index


def test_the_b2_publish_gates_have_their_place_outside_the_deploy_job() -> None:
    """Controller kararı (a, b, d): kaybolan-slug `build`de tarayıcıdan sonra, yayın paketinden
    ÖNCE (kırmızıysa paket yok, `needs` yayını durdurur); yayın sonrası kontrol `live`da. B-2 T10
    adımı yazana dek yer bir işaret satırıdır; yazıldıktan sonra adımın kendisi sınanır."""
    assert _line("- name: Çıktı tarayıcısı") < _line(SLUGS_MARK) < _line("- name: Yayın paketi")
    assert _line("  live:") < _line(LIVE_MARK)
    placed = {
        needle: {name for name in _jobs() if _index_of(_steps(SITE, name), needle) is not None}
        for needle in (SLUGS, LIVE)
    }
    assert placed[SLUGS] <= {"build"} and placed[LIVE] <= {"live"}, placed
    if placed[SLUGS]:
        build = _steps(SITE, "build")
        upload = _index_of(build, "actions/upload-artifact", key="uses")
        assert _index_of(build, CHECK_OUT) < _index_of(build, SLUGS) < upload  # type: ignore[operator]


def test_a_red_step_stops_everything_after_it() -> None:
    """I3: kırmızı `verify-snapshot`ten sonra yayın OLAMAZ. Adımda `if:` ve `continue-on-error`
    yok; işte `continue-on-error` yok; tek iş koşulu yayının `main` koşulu (örtük `success()`i
    korur); hiçbir komut `||` ile kırmızıyı yutmaz; kabuk `bash -e` dışına çıkarılamaz."""
    jobs = _jobs()

    assert [s for s in _steps(SITE) if {"if", "continue-on-error"} & set(s)] == []
    assert {name: job.get("if") for name, job in jobs.items()} == {
        "build": None,
        "deploy": MAIN_ONLY,
        "live": MAIN_ONLY,
    }
    assert [name for name, job in jobs.items() if "continue-on-error" in job] == []
    assert [str(s["run"]) for s in _steps(SITE) if "||" in str(s.get("run", ""))] == []
    # N2: `shell: bash {0}` `-e`yi kaldırır; `defaults.run.shell` aynısını işe/workflow'a yayar.
    assert [s for s in _steps(SITE) if "shell" in s] == []
    assert [
        n for n, node in {"<workflow>": _document(), **jobs}.items() if "defaults" in node
    ] == []


def _t0_netlify_cli() -> str:
    (recorded,) = re.findall(r"^netlify_cli=(\S+)$", T0_RECORD.read_text(encoding="utf-8"), re.M)
    return str(recorded)


def test_the_netlify_cli_is_pinned_to_the_t0_version() -> None:
    """Sürüm aralığı değil tam sürüm; değer T0 kaydından (tek kaynak)."""
    (pinned,) = re.findall(r"netlify-cli@(\S+)", "\n".join(_runs("deploy")))

    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", pinned), pinned
    assert pinned == _t0_netlify_cli()
