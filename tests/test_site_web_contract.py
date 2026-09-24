"""B-2 ↔ sözleşme: TS tipi, JSON Schema ve B-2'nin sentetik fixture'ları aynı şekli taşır.

Sözleşmenin sahibi `web/contract/snapshot.schema.json`dur (B-1 T1). TS `Snapshot` tipini
elle taşır (spec §5.2); bir anahtar bir tarafta kalırsa sayfa ya sessizce boş basar ya da
derleme olmayan bir alanı okur. Bu dosya iki yönü de kırmızı yapar. Fixture'ların tam
içerik denetimi `verify-snapshot`in (B-1) işidir; burada yalnız B-2'nin dayandığı şekil,
sıralama ve `content_sha256` sınanır; DEĞERLER B-1'in doğrulayıcısıyla
(`football_edge.site.schema.validate`) şemaya karşı sınanır. `verify-snapshot` T10'dan beri kapıda.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from football_edge.site import schema as site_schema
from tests import site_web_fixtures

REPO = Path(__file__).resolve().parent.parent
SCHEMA = REPO / "web/contract/snapshot.schema.json"
TS_TYPES = REPO / "web/src/lib/snapshot-types.ts"
B2_FIXTURES = (site_web_fixtures.FULL, site_web_fixtures.EMPTY)

# Şemadaki her nesne yolu → onu taşıyan TS tipi. `[]` dizi öğesidir.
TYPE_OF_PATH = {
    "": "Snapshot",
    "ledger": "Ledger",
    "ledger.anchor": "Anchor",
    "leagues[]": "League",
    "leagues[].move_distribution": "MoveDistribution",
    "teams[]": "Team",
    "matches[]": "Match",
    "matches[].h2h": "H2h",
    "matches[].h2h.opening": "Round",
    "matches[].h2h.latest": "Round",
    "matches[].h2h.closing": "Round",
    "matches[].h2h.opening.p": "Triple",
    "matches[].h2h.latest.p": "Triple",
    "matches[].h2h.closing.p": "Triple",
    "matches[].move": "Triple",
    "record": "TrackRecord",
    "record.entries[]": "RecordEntry",
    "record.summary": "RecordSummary",
}
SORT_KEYS = {
    "leagues": ("id",),
    "teams": ("league_id", "slug"),
    "matches": ("commence_time", "id"),
}

Shape = dict[str, tuple[set[str], set[str]]]  # yol → (properties, required)
_TYPE_OPEN = re.compile(r"^export type (\w+) = \{$")
_KEY_LINE = re.compile(r"^  (\w+): ([^;]+);$")


def _resolve(node: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        target: Any = root
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        node = target
    return node


def _branches(node: dict[str, Any], root: dict[str, Any]) -> list[dict[str, Any]]:
    """Null olmayan alternatifler: `anyOf`/`oneOf` açılır, `null` ve `const: null` düşer."""
    node = _resolve(node, root)
    for key in ("anyOf", "oneOf"):
        if key in node:
            return [branch for sub in node[key] for branch in _branches(sub, root)]
    if node.get("type") == "null" or ("const" in node and node["const"] is None):
        return []
    return [node]


def _types(node: dict[str, Any]) -> list[Any]:
    kind = node.get("type")
    return kind if isinstance(kind, list) else [kind]


def schema_shape(node: dict[str, Any], root: dict[str, Any], path: str = "") -> Shape:
    shape: Shape = {}
    for branch in _branches(node, root):
        if "object" in _types(branch) or "properties" in branch:
            properties = branch.get("properties", {})
            shape[path] = (set(properties), set(branch.get("required", [])))
            for key, sub in properties.items():
                shape |= schema_shape(sub, root, f"{path}.{key}" if path else key)
        if "array" in _types(branch) or "items" in branch:
            shape |= schema_shape(branch["items"], root, f"{path}[]")
    return shape


def ts_shape(text: str) -> dict[str, set[str]]:
    """`snapshot-types.ts`in katı biçimini okur; biçim dışı her satır kırmızıdır."""
    types: dict[str, set[str]] = {}
    current: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if current is None:
            opened = _TYPE_OPEN.match(line)
            if opened:
                current = opened[1]
                types[current] = set()
            else:
                assert not line.startswith("export type"), f"satır {number}: biçim dışı tip"
            continue
        if line == "};":
            current = None
            continue
        key = _KEY_LINE.match(line)
        assert key, f"satır {number}: tip gövdesinde ayrıştırılamayan satır {line!r}"
        types[current].add(key[1])
    assert current is None, "kapanmamış tip bloğu"
    return types


def document_paths(value: Any, path: str = "") -> dict[str, list[set[str]]]:
    """Belgedeki her nesnenin anahtar kümesi, yola göre (dizi indisi `[]`e katlanır)."""
    found: dict[str, list[set[str]]] = {}
    if isinstance(value, dict):
        found.setdefault(path, []).append(set(value))
        for key, sub in value.items():
            for sub_path, keys in document_paths(sub, f"{path}.{key}" if path else key).items():
                found.setdefault(sub_path, []).extend(keys)
    elif isinstance(value, list):
        for item in value:
            for sub_path, keys in document_paths(item, f"{path}[]").items():
                found.setdefault(sub_path, []).extend(keys)
    return found


@pytest.fixture(scope="module")
def schema() -> Shape:
    assert SCHEMA.exists(), (
        f"{SCHEMA.relative_to(REPO)} yok — B-1 T1 (sözleşme) birleşmeden T2 başlamaz"
    )
    root = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return schema_shape(root, root)


def test_every_schema_object_has_a_mapped_ts_type(schema: Shape) -> None:
    assert set(schema) == set(TYPE_OF_PATH), (
        f"şemada eşlenmemiş nesne: {sorted(set(schema) - set(TYPE_OF_PATH))}; "
        f"eşlemede şemada olmayan: {sorted(set(TYPE_OF_PATH) - set(schema))}"
    )


@pytest.mark.parametrize("path", sorted(TYPE_OF_PATH))
def test_ts_type_keys_equal_schema_keys(schema: Shape, path: str) -> None:
    ts = ts_shape(TS_TYPES.read_text(encoding="utf-8"))
    properties, _ = schema[path]
    assert ts[TYPE_OF_PATH[path]] == properties, f"{path} ↔ {TYPE_OF_PATH[path]}"


def test_ts_parser_rejects_a_line_it_cannot_read() -> None:
    with pytest.raises(AssertionError, match="ayrıştırılamayan"):
        ts_shape("export type X = {\n  a: number; b: number;\n};\n")


@pytest.mark.parametrize("fixture", B2_FIXTURES, ids=lambda path: path.name)
def test_fixture_objects_fit_the_schema(schema: Shape, fixture: Path) -> None:
    document = json.loads(fixture.read_text(encoding="utf-8"))
    for path, key_sets in document_paths(document).items():
        assert path in schema, f"{fixture.name}: şemada olmayan nesne yolu {path!r}"
        properties, required = schema[path]
        for keys in key_sets:
            assert keys <= properties, f"{fixture.name} {path}: fazla {sorted(keys - properties)}"
            assert required <= keys, f"{fixture.name} {path}: eksik {sorted(required - keys)}"


@pytest.mark.parametrize("fixture", B2_FIXTURES, ids=lambda path: path.name)
def test_fixture_values_pass_the_b1_schema_validator(fixture: Path) -> None:
    """Anahtar kümesi yetmez: `outcome` enum'u ve çıpa dosya adı deseni DEĞER kuralıdır."""
    root = json.loads(SCHEMA.read_text(encoding="utf-8"))
    document = json.loads(fixture.read_text(encoding="utf-8"))
    assert site_schema.validate(document, root) == []


def test_committed_fixtures_equal_the_generator_output() -> None:
    for path, text in site_web_fixtures.expected_files().items():
        assert path.read_text(encoding="utf-8") == text, (
            f"{path.name} üreticiden sapmış: `uv run python -m tests.site_web_fixtures`"
        )


@pytest.mark.parametrize("fixture", B2_FIXTURES, ids=lambda path: path.name)
def test_fixture_content_hash_and_order(fixture: Path) -> None:
    document = json.loads(fixture.read_text(encoding="utf-8"))
    assert document["content_sha256"] == site_web_fixtures.content_sha256(document)
    for array, keys in SORT_KEYS.items():
        rows = [tuple(row[key] for key in keys) for row in document[array]]
        assert rows == sorted(rows), f"{fixture.name}: {array} {keys} sırasında değil"
    ids = [entry["publication_id"] for entry in document["record"]["entries"]]
    assert ids == sorted(ids)


@pytest.mark.parametrize("fixture", B2_FIXTURES, ids=lambda path: path.name)
def test_fixture_record_is_internally_consistent(fixture: Path) -> None:
    record = json.loads(fixture.read_text(encoding="utf-8"))["record"]
    assert record["published"] == len(record["entries"])
    assert (record["published"] == 0) == (record["summary"] is None)
