"""B-2 ↔ sözleşme: TS tipi, JSON Schema ve B-2'nin sentetik fixture'ları aynı şekli taşır.

Sözleşmenin sahibi `web/contract/snapshot.schema.json`dur (B-1 T1). TS `Snapshot` tipini
elle taşır (spec §5.2); bir anahtar bir tarafta kalırsa sayfa ya sessizce boş basar ya da
derleme olmayan bir alanı okur. Bu dosya iki yönü de kırmızı yapar. Fixture'ların tam
içerik denetimi `verify-snapshot`in (B-1) işidir; burada yalnız B-2'nin dayandığı şekil,
sıralama ve `content_sha256` sınanır; DEĞERLER B-1'in doğrulayıcısıyla
(`football_edge.site.schema.validate`) şemaya karşı sınanır. `verify-snapshot` T10'dan beri kapıda.

TS tarafı alan başına TİP de taşır: şemanın `integer`/`number`ı `number`, `enum`u literal birleşimi,
sayı/`null` `const`u literalidir; metin `const`u (`floor`) `string` taşınır — değeri bir DEĞER
kuralıdır, `verify-snapshot` sınar. Nesne alanı, `TYPE_OF_PATH`in o yola verdiği tipi kullanmalıdır.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from football_edge.site import contract
from football_edge.site import schema as site_schema
from tests import site_web_fixtures

REPO = Path(__file__).resolve().parent.parent
SCHEMA = REPO / "web/contract/snapshot.schema.json"
TS_TYPES = REPO / "web/src/lib/snapshot-types.ts"
TS_LOADER = REPO / "web/src/lib/snapshot.ts"
SITE_CONFIG = REPO / "web/site.config.ts"
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
Fields = dict[str, dict[str, str]]  # yol ya da TS tipi → {anahtar: TS tip ifadesi}
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


def _child(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def ts_type_of(node: dict[str, Any], root: dict[str, Any], path: str) -> str:
    """Şema düğümünün TS karşılığı (modül belgesindeki eşleme); nesne `TYPE_OF_PATH`ten adlanır."""
    node = _resolve(node, root)
    if "const" in node:
        value = node["const"]
        return "string" if isinstance(value, str) else json.dumps(value)
    if "enum" in node:
        return " | ".join(json.dumps(value) for value in node["enum"])
    names = []
    for kind in _types(node):
        if kind == "object":
            names.append(TYPE_OF_PATH.get(path, f"<eşlenmemiş {path}>"))
        elif kind == "array":
            names.append(f"{ts_type_of(node['items'], root, f'{path}[]')}[]")
        else:
            names.append("number" if kind in ("integer", "number") else str(kind))
    return " | ".join(names)


def schema_fields(node: dict[str, Any], root: dict[str, Any], path: str = "") -> Fields:
    fields: Fields = {}
    for branch in _branches(node, root):
        if "object" in _types(branch) or "properties" in branch:
            properties = branch.get("properties", {})
            fields[path] = {
                key: ts_type_of(sub, root, _child(path, key)) for key, sub in properties.items()
            }
            for key, sub in properties.items():
                fields |= schema_fields(sub, root, _child(path, key))
        if "array" in _types(branch) or "items" in branch:
            fields |= schema_fields(branch["items"], root, f"{path}[]")
    return fields


def ts_shape(text: str) -> Fields:
    """`snapshot-types.ts`in katı biçimini okur; biçim dışı her satır kırmızıdır."""
    types: Fields = {}
    current: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if current is None:
            opened = _TYPE_OPEN.match(line)
            if opened:
                current = opened[1]
                types[current] = {}
            else:
                assert not line.startswith("export type"), f"satır {number}: biçim dışı tip"
            continue
        if line == "};":
            current = None
            continue
        key = _KEY_LINE.match(line)
        assert key, f"satır {number}: tip gövdesinde ayrıştırılamayan satır {line!r}"
        types[current][key[1]] = key[2]
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


@pytest.fixture(scope="module")
def ts() -> Fields:
    return ts_shape(TS_TYPES.read_text(encoding="utf-8"))


def test_every_schema_object_has_a_mapped_ts_type(schema: Shape) -> None:
    assert set(schema) == set(TYPE_OF_PATH), (
        f"şemada eşlenmemiş nesne: {sorted(set(schema) - set(TYPE_OF_PATH))}; "
        f"eşlemede şemada olmayan: {sorted(set(TYPE_OF_PATH) - set(schema))}"
    )


@pytest.mark.parametrize("path", sorted(TYPE_OF_PATH))
def test_ts_type_keys_equal_schema_keys(schema: Shape, ts: Fields, path: str) -> None:
    properties, _ = schema[path]
    assert set(ts[TYPE_OF_PATH[path]]) == properties, f"{path} ↔ {TYPE_OF_PATH[path]}"


@pytest.mark.parametrize("path", sorted(TYPE_OF_PATH))
def test_ts_field_types_equal_schema_types(ts: Fields, path: str) -> None:
    """Değer tipi ve nesne alanının tipi: `move: Move | null` gibi eşlenmemiş tipe kaçış kırmızı."""
    root = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert ts[TYPE_OF_PATH[path]] == schema_fields(root, root)[path], (
        f"{path} ↔ {TYPE_OF_PATH[path]}"
    )


def test_ts_file_declares_only_the_mapped_types(ts: Fields) -> None:
    """Eşlenmemiş bir tip (ör. model olasılığı taşıyan) dosyada duramaz."""
    assert set(ts) == set(TYPE_OF_PATH.values())


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
        assert _strictly_increasing(rows), f"{fixture.name}: {array} {keys} kesin artan değil"
    ids = [entry["publication_id"] for entry in document["record"]["entries"]]
    assert _strictly_increasing(ids), f"{fixture.name}: publication_id kesin artan değil"


def _strictly_increasing(values: list[Any]) -> bool:
    """Sıralı VE tekrarsız: aynı anahtarlı iki satır iki kaydı tek sayfaya yazar."""
    return all(left < right for left, right in zip(values, values[1:], strict=False))


@pytest.mark.parametrize("fixture", B2_FIXTURES, ids=lambda path: path.name)
def test_fixture_record_is_internally_consistent(fixture: Path) -> None:
    record = json.loads(fixture.read_text(encoding="utf-8"))["record"]
    assert record["published"] == len(record["entries"])
    assert (record["published"] == 0) == (record["summary"] is None)


def _shown(value: float) -> float:
    return round(value, 1) + 0.0


def _exporter_move(match: dict[str, Any]) -> dict[str, float] | None:
    """B-1 `derive._move`: açılış → kapanış (mühürsüzse son); iki uç görünmüyorsa None."""
    h2h = match["h2h"]
    start, end = h2h["opening"], h2h["closing" if match["sealed"] else "latest"]
    if start is None or end is None:
        return None
    return {name: _shown(end["p"][name] - start["p"][name]) for name in ("home", "draw", "away")}


def _exporter_distribution(matches: list[dict[str, Any]]) -> dict[str, float] | None:
    """B-1 `derive._distribution`: mühürlü, ≥ 2 turlu, hareketli maçta en büyük |bileşen|."""
    moves = [
        max(abs(value) for value in match["move"].values())
        for match in matches
        if match["sealed"] and match["rounds"] >= 2 and match["move"] is not None
    ]
    if len(moves) < contract.MOVE_MIN_MATCHES:
        return None
    p10, p50, p90 = (float(value) for value in np.percentile(np.asarray(moves), [10, 50, 90]))
    return {"p10": _shown(p10), "p50": _shown(p50), "p90": _shown(p90)}


@pytest.mark.parametrize("fixture", B2_FIXTURES, ids=lambda path: path.name)
def test_fixture_derived_fields_follow_the_exporter_rules(fixture: Path) -> None:
    """Fixture dışa aktarıcının ÜRETEBİLECEĞİ bir anlık görüntüdür: hareket, dağılım ve sayımlar."""
    document = json.loads(fixture.read_text(encoding="utf-8"))
    for match in document["matches"]:
        assert match["move"] == _exporter_move(match), f"{match['path_id']}: move"
    counts: dict[tuple[str, str], int] = {}
    for match in document["matches"]:
        for name in (match["home"], match["away"]):
            counts[(match["league_id"], name)] = counts.get((match["league_id"], name), 0) + 1
    for team in document["teams"]:
        assert team["matches"] == counts.pop((team["league_id"], team["name"])), team["slug"]
        assert team["indexable"] == (team["matches"] >= contract.SITE_MIN_TEAM_MATCHES)
    assert counts == {}, f"takımı olmayan maç tarafı: {sorted(counts)}"
    for league in document["leagues"]:
        own = [match for match in document["matches"] if match["league_id"] == league["id"]]
        assert league["matches"] == len(own), league["id"]
        assert league["move_distribution"] == _exporter_distribution(own), league["id"]
    distributions = [league["move_distribution"] for league in document["leagues"]]
    assert None in distributions and any(distributions), "dolu VE boş dağılım sayfa durumu"
    assert any(
        match["move"] == {"home": 0.0, "draw": 0.0, "away": 0.0} for match in document["matches"]
    )


def _ts_const(text: str, name: str) -> str:
    found = re.search(rf"^const {name}(?:: [^=]+)? = (.+?);$", text, re.MULTILINE | re.DOTALL)
    assert found, f"snapshot.ts: `const {name}` yok"
    return found[1]


def _ts_strings(literal: str) -> set[str]:
    return set(re.findall(r'"([^"]*)"', literal))


def test_ts_routing_patterns_are_the_schema_patterns() -> None:
    """`parseSnapshot`in yol bölütü desenleri şemanınkilerle AYNI (kaynak şema; kopya sınanır)."""
    root = json.loads(SCHEMA.read_text(encoding="utf-8"))
    match = root["properties"]["matches"]["items"]["properties"]
    text = TS_LOADER.read_text(encoding="utf-8")
    assert _ts_const(text, "SLUG") == f"/{root['$defs']['slug']['pattern']}/"
    assert _ts_const(text, "PATH_ID") == f"/{match['path_id']['pattern']}/"
    assert _ts_const(text, "MATCH_SLUG") == f"/{match['slug']['pattern']}/"
    assert f"{{{contract.PATH_ID_LENGTH}}}" in match["path_id"]["pattern"]


def test_ts_forbidden_keys_are_the_b1_forbidden_keys() -> None:
    """§4.3: B-1 `contract.FORBIDDEN_KEYS`; H3 parçaları B-1 `test_site_contract`in kuralı."""
    text = TS_LOADER.read_text(encoding="utf-8")
    assert _ts_strings(_ts_const(text, "FORBIDDEN_KEYS")) == contract.FORBIDDEN_KEYS
    assert _ts_strings(_ts_const(text, "FORBIDDEN_FRAGMENTS")) == {"model", "value"}
    assert _ts_strings(_ts_const(text, "ALLOWED_FRAGMENT_KEYS")) == {"value_badge"}


def test_site_config_reserved_slugs_are_the_b1_reserved_slugs() -> None:
    text = SITE_CONFIG.read_text(encoding="utf-8")
    for name, expected in (
        ("RESERVED_LEAGUE_SLUGS", contract.RESERVED_LEAGUE_SLUGS),
        ("RESERVED_TEAM_SLUGS", contract.RESERVED_TEAM_SLUGS),
    ):
        found = re.search(rf"^export const {name}: [^=]+ = (\[.*?\]);$", text, re.M | re.S)
        assert found, f"site.config.ts: {name} yok"
        assert _ts_strings(found[1]) == expected, name
