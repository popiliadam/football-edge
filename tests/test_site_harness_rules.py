"""Site test düzeninin kuralları (§4.4/4): tetikleyici kapatılmaz, fixture'lar tek dosyada.

Kapsam bilinçli olarak dardır: `tests/test_site_*.py` ve `tests/site_db.py`.
`tests/test_runbook.py` RUNBOOK'tan alıntılanmış bir kalıp taşır ve bu kuralın konusu değildir.
Kalıplar parçalardan kurulur: bu dosya kendi kalıbını eşlemesin.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.site_db import SITE_TEST_VAR, guarded_url, refusal

TESTS = Path(__file__).resolve().parent
HARNESS = TESTS / "site_db.py"
SCOPE = sorted({*TESTS.glob("test_site_*.py"), HARNESS})
DISABLING = (
    re.compile("disable" + r"\s+trigger", re.IGNORECASE),
    re.compile("session_replication" + "_role", re.IGNORECASE),
    re.compile(r"alter\s+table\b[^;\n]*\b" + "disable", re.IGNORECASE),
)
SITE_FIXTURES = frozenset({"site_cluster", "site_db", "site_db_each", "full_sequence"})
ENV_PART = "SITE_TEST_" + "DATABASE"


def test_the_scope_is_the_site_tests_and_the_harness() -> None:
    assert HARNESS in SCOPE and len(SCOPE) > 1


def test_no_site_test_disables_a_trigger() -> None:
    """Append-only tetikleyicisi testte de kapatılmaz: temizlik veritabanı düzeyindedir."""
    hits = [
        f"{path.name}: {pattern.pattern}"
        for path in SCOPE
        for pattern in DISABLING
        if pattern.search(path.read_text(encoding="utf-8"))
    ]

    assert hits == []


def _fixture_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any("fixture" in ast.unparse(decorator) for decorator in node.decorator_list)
    }


def test_sitedb_fixtures_live_only_in_the_harness() -> None:
    """n5: `sitedb` fixture'ları ve test DB adresi yalnız `tests/site_db.py`de."""
    elsewhere = {
        path.name: sorted(_fixture_names(path) & SITE_FIXTURES)
        for path in TESTS.glob("*.py")
        if path != HARNESS and _fixture_names(path) & SITE_FIXTURES
    }
    readers = sorted(
        path.name
        for path in TESTS.glob("*.py")
        if path != HARNESS and ENV_PART in path.read_text(encoding="utf-8")
    )

    assert _fixture_names(HARNESS) >= SITE_FIXTURES
    assert elsewhere == {}
    assert readers == []


def test_the_migration_grants_no_membership_in_the_reader_role() -> None:
    """Test kümesi `postgres`e SET üyeliği verebilir (`site_db.py`); 0014 kimseye vermez."""
    text = (TESTS.parent / "db/migrations/0014_site_read.sql").read_text(encoding="utf-8").lower()

    assert re.search(r"grant\s+site_reader\s+to", text) is None


def test_the_gate_runs_sitedb_tests_only_where_it_names_them() -> None:
    """Test KOŞTURAN her `uv run pytest` çağrısı `sitedb`i adıyla seçer ya da dışlar.

    `-m contract` muaftır; `--collect-only` test koşturmaz. Aksi hâlde `CI=true` iken kabı olmayan
    bir adımda `sitedb` fixture'ı FAIL verir, ya da testler iki adımda iki kez koşar.
    """
    runs = [
        line.strip()
        for line in (TESTS.parent / "verify.sh").read_text(encoding="utf-8").splitlines()
        if "uv run pytest" in line
        and "--collect-only" not in line  # sayım çağrısı test koşturmaz
        and not line.lstrip().startswith("#")
    ]

    assert runs, "verify.sh'de pytest çağrısı bulunamadı"
    assert all("sitedb" in run or "-m contract" in run for run in runs), runs


# ── Koruma (§4.4/5): atılabilir olmayan hedef reddedilir, adres metne girmez ──────────────────


@pytest.mark.parametrize(
    ("url", "live", "refused"),
    [
        ("postgresql://postgres:gizli@127.0.0.1:55481/postgres", "", False),
        ("postgresql://postgres:gizli@localhost:5432/postgres", "", False),
        ("postgresql://postgres:gizli@db.uzak.invalid:5432/postgres", "", True),
        ("postgresql:///postgres", "", True),  # soket: ana makine yok
        (
            "postgresql://postgres:gizli@127.0.0.1:5432/postgres",
            "postgresql://postgres:gizli@127.0.0.1:5432/postgres",
            True,
        ),
        ("bu bir adres değil ===", "", True),
    ],
)
def test_only_a_local_disposable_address_is_accepted(url: str, live: str, refused: bool) -> None:
    reason = refusal(url, live)

    assert (reason is not None) is refused, reason
    assert reason is None or "gizli" not in reason


def test_a_missing_address_skips_locally_and_fails_in_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    """B10: SKIP'in CI'da sessizce yeşil olması Vaka 1 desenidir.

    İki sonuç da yakalanıp TÜRÜYLE sınanır: yakalanmayan bir SKIP bu testi kırmızı değil "atlandı"
    gösterirdi.
    """
    outcomes = (pytest.skip.Exception, pytest.fail.Exception)
    monkeypatch.delenv(SITE_TEST_VAR, raising=False)
    monkeypatch.delenv("CI", raising=False)
    with pytest.raises(outcomes) as local:
        guarded_url()
    monkeypatch.setenv("CI", "true")
    with pytest.raises(outcomes) as ci:
        guarded_url()

    assert local.type is pytest.skip.Exception and "SKIP: site-db" in str(local.value)
    assert ci.type is pytest.fail.Exception and "CI=true" in str(ci.value)
