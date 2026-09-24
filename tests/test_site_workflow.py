"""`site.yml` (§11, H5d): elle tetiklenir, secret ADIM düzeyinde, yalnız iki adımda.

Ham metin taraması değil ayrıştırılmış belge okunur (`tests/test_workflows.py` gerekçesi: yorum da
secret adını yazar). `${{ secrets.X }}` ifadesi yalnız bir adımın `env`inde durabilir; `run` metnine
gömülürse secret betik metnine girer.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from tests.workflow_helpers import _index_of, _steps, _triggers

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / ".github/workflows/site.yml"
T0_RECORD = REPO / "docs/phases/06-site/b1-t0-olcumler.md"
EXPORT = "football_edge.site export"
DEPLOY = "deploy --prod --dir web/out"
SECRET = re.compile(r"\$\{\{\s*secrets\.(\w+)\s*\}\}")
PIPELINE_ONLY = ("DATABASE" + "_URL", "ODDS_API" + "_KEY", "TYPESAFE_API" + "_KEY")


def _document() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(SITE.read_text(encoding="utf-8"))
    return loaded


def _secrets_in(node: Any) -> set[str]:
    return set(SECRET.findall(yaml.safe_dump(node))) if node else set()


def test_site_is_dispatched_by_hand_only() -> None:
    """B9/AK15: `schedule`, `push`, pg_cron tetiği yok."""
    assert set(_triggers(SITE)) == {"workflow_dispatch"}


def test_site_reads_the_repository_and_deploys_one_at_a_time() -> None:
    document = _document()
    (job,) = document["jobs"].values()

    assert document["permissions"] == {"contents": "read"}
    assert "permissions" not in job
    assert document["concurrency"]["group"] == "site-deploy"
    (checkout,) = [s for s in _steps(SITE) if str(s.get("uses", "")).startswith("actions/checkout")]
    assert checkout["with"] == {"fetch-depth": 0, "persist-credentials": False}


def test_no_secret_lives_at_workflow_or_job_level() -> None:
    document = _document()
    (job,) = document["jobs"].values()

    assert _secrets_in(document.get("env")) == set()
    assert _secrets_in(job.get("env")) == set()


def test_each_secret_is_given_to_exactly_one_named_step_through_env() -> None:
    """H5d: DB adresi yalnız dışa aktarımda, Netlify kimliği yalnız yayında; öteki adımlar temiz."""
    given = {
        index: _secrets_in(step) for index, step in enumerate(_steps(SITE)) if _secrets_in(step)
    }
    export, deploy = _index_of(_steps(SITE), EXPORT), _index_of(_steps(SITE), DEPLOY)

    assert given == {
        export: {"SITE_DATABASE_URL"},
        deploy: {"NETLIFY_AUTH_TOKEN", "NETLIFY_SITE_ID"},
    }
    for index in given:
        step = _steps(SITE)[index]
        assert _secrets_in({key: value for key, value in step.items() if key != "env"}) == set()
        assert set(step["env"]) == given[index], "secret yalnız kendi adıyla env'e girer"


def test_the_pipeline_credentials_never_reach_the_site_job() -> None:
    names = {name for step in _steps(SITE) for name in (step.get("env") or {})}

    assert names.isdisjoint(PIPELINE_ONLY)
    assert _secrets_in(_document()).isdisjoint(PIPELINE_ONLY)


def test_the_export_is_scanned_verified_and_precedes_every_node_step() -> None:
    steps = _steps(SITE)
    scan = _index_of(steps, "scripts/check_secrets.sh")
    export = _index_of(steps, EXPORT)
    verify = _index_of(steps, "football_edge.site verify-snapshot")
    node = _index_of(steps, "actions/setup-node", key="uses")
    deploy = _index_of(steps, DEPLOY)

    assert None not in (scan, export, verify, node, deploy)
    assert scan < export < verify < node < deploy  # type: ignore[operator]
    assert "--out web/.snapshot" in steps[export]["run"]  # type: ignore[index]
    assert "--sha256 web/.snapshot/snapshot.sha256" in steps[verify]["run"]  # type: ignore[index]


def test_the_netlify_cli_is_pinned_to_the_t0_version() -> None:
    """Sürüm aralığı değil tam sürüm; değer T0 kaydından (tek kaynak)."""
    (recorded,) = re.findall(r"^netlify_cli=(\S+)$", T0_RECORD.read_text(encoding="utf-8"), re.M)
    (pinned,) = re.findall(
        r"netlify-cli@(\S+)", _steps(SITE)[_index_of(_steps(SITE), DEPLOY)]["run"]
    )  # type: ignore[index]

    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", pinned), pinned
    assert pinned == recorded
