"""Anlık görüntü sözleşmesi (Faz 6 İz B §5.2): şema, sentetik fixture'lar ve Python sabitleri.

B-2'nin başlangıç kapısıdır: `web/contract/snapshot.schema.json` ve `web/fixtures/*.json` bu
testlerle birlikte birleşir. Fixture'lar SENTETİKTİR (uydurma lig/takım adları); gerçek anlık
görüntü depoya girmez (`.gitignore`: `web/.snapshot/`).
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pytest

from football_edge.history.holdout import HOLDOUT_END
from football_edge.site.contract import (
    FORBIDDEN_KEYS,
    PUBLIC_FLOOR,
    SCHEMA_VERSION,
    SITE_MIN_BOOKS,
    content_sha256,
    iso_z,
)
from football_edge.site.schema import check_schema, property_names, validate

REPO = Path(__file__).resolve().parent.parent
SCHEMA = REPO / "web/contract/snapshot.schema.json"
FIXTURES = REPO / "web/fixtures"
BASE = FIXTURES / "snapshot.fixture.json"
FULL_RECORD = FIXTURES / "snapshot.fixture-record.json"


def _load(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def test_the_schema_uses_only_the_supported_subset_and_closes_every_object() -> None:
    check_schema(_load(SCHEMA))


@pytest.mark.parametrize("path", [BASE, FULL_RECORD], ids=lambda path: path.name)
def test_every_fixture_satisfies_the_schema_and_its_own_content_hash(path: Path) -> None:
    snapshot = _load(path)

    assert validate(snapshot, _load(SCHEMA)) == []
    assert content_sha256(snapshot) == snapshot["content_sha256"]


def test_the_two_contract_fixtures_exist_under_their_published_names() -> None:
    """B-2 bu adlara dayanır; B-2 kendi fixture'larını aynı dizine ekleyebilir (kapsayıcı değil)."""
    assert {BASE.name, FULL_RECORD.name} <= {path.name for path in FIXTURES.glob("*.json")}


def test_the_fixtures_carry_every_variant_the_site_must_render() -> None:
    """§6.4/1: boş sicil, dolu sicil (özetli), eşik altı tur, mühürsüz maç, tek turlu maç."""
    base, full = _load(BASE), _load(FULL_RECORD)
    matches = base["matches"]

    assert base["record"] == {"published": 0, "entries": [], "summary": None}
    assert full["record"]["published"] >= 1 and full["record"]["summary"] is not None
    assert any(not match["sealed"] for match in matches), "mühürsüz maç yok"
    assert any(match["rounds"] == 1 for match in matches), "tek turlu maç yok"
    assert any(match["rounds"] >= 2 and match["h2h"]["opening"] is None for match in matches), (
        "eşik altı tur yok"
    )
    assert any(league["move_distribution"] is not None for league in base["leagues"])
    assert any(league["move_distribution"] is None for league in base["leagues"])
    assert any(team["indexable"] for team in base["teams"])
    assert any(not match["indexable"] for match in matches)


def test_value_and_analysis_slots_are_const_null_and_no_model_field_exists() -> None:
    """H3/B6: şema sürümü artmadan öneri ya da model olasılığı taşınamaz."""
    schema = _load(SCHEMA)
    names = property_names(schema)

    assert schema["properties"]["value_badge"]["const"] is None
    assert schema["properties"]["analysis"]["const"] is None
    assert not {name for name in names if "model" in name or "value" in name} - {"value_badge"}


def test_the_schema_constants_are_the_python_constants() -> None:
    schema = _load(SCHEMA)

    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION
    assert schema["properties"]["floor"]["const"] == iso_z(PUBLIC_FLOOR)
    assert schema["$defs"]["round"]["properties"]["books"]["minimum"] == SITE_MIN_BOOKS


def test_no_forbidden_key_is_declared_by_the_schema() -> None:
    """§4.3: yasak küme şemanın bildirdiği anahtarları dışlar — kesişim boş olmalı."""
    assert FORBIDDEN_KEYS & property_names(_load(SCHEMA)) == frozenset()


@pytest.mark.leakage
def test_the_public_floor_is_one_day_after_the_holdout_end() -> None:
    """B4/H1c: taban Python'da `HOLDOUT_END + 1 gün`den türetilir, elle yazılmış bir tarih değil."""
    expected = datetime.combine(HOLDOUT_END + timedelta(days=1), time(), tzinfo=UTC)

    assert expected == PUBLIC_FLOOR


def test_the_content_hash_ignores_only_build_time_and_source_version() -> None:
    snapshot = _load(BASE)
    moved = {**snapshot, "generated_at": "2030-01-01T00:00:00Z", "git_sha": "f" * 40}
    touched = {**snapshot, "floor": "2026-07-03T00:00:00Z"}

    assert content_sha256(moved) == content_sha256(snapshot)
    assert content_sha256(touched) != content_sha256(snapshot)


@pytest.mark.parametrize(
    "path",
    ["web/.snapshot/snapshot.json", "web/out/index.html", "web/.next/cache", "web/node_modules/x"],
)
def test_the_real_snapshot_and_build_outputs_never_enter_the_repository(path: str) -> None:
    """§5.2/§13: gerçek anlık görüntü (`site.yml`in `web/.snapshot/`i) depoya commit'lenmez."""
    result = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", path], check=False)

    assert result.returncode == 0, f"{path} gitignore'da değil"
