"""Anlık görüntü şemasının (`web/contract/snapshot.schema.json`) bağımlılıksız doğrulayıcısı.

JSON Schema'nın yalnız sözleşmenin kullandığı alt kümesi desteklenir. Şema bilinmeyen bir anahtar
kelime taşırsa `SchemaError` yükselir: doğrulayıcının SESSİZCE yok saydığı bir kural, sözleşmede
yazılı ama hiç sınanmayan bir kural olurdu. `additionalProperties` yalnız `false` olabilir (B6).
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from typing import Any

SUPPORTED = frozenset(
    {
        "$schema",
        "$id",
        "$defs",
        "$ref",
        "title",
        "description",
        "type",
        "const",
        "enum",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "pattern",
    }
)
_TYPES = frozenset({"object", "array", "string", "integer", "number", "boolean", "null"})


class SchemaError(ValueError):
    """Şemanın kendisi desteklenen alt kümenin dışında."""


def check_schema(schema: Mapping[str, Any]) -> None:
    """Şemadaki her düğüm yalnız desteklenen anahtar kelimeleri taşır; nesneler kapalıdır."""
    for path, node in _nodes(schema, "#"):
        unknown = sorted(set(node) - SUPPORTED)
        if unknown:
            raise SchemaError(f"{path}: desteklenmeyen anahtar kelime {unknown}")
        if "additionalProperties" in node and node["additionalProperties"] is not False:
            raise SchemaError(f"{path}: additionalProperties yalnız false olabilir")
        if "properties" in node and node.get("additionalProperties") is not False:
            raise SchemaError(f"{path}: nesne additionalProperties: false taşımalı")
        kinds = node.get("type")
        declared = kinds if isinstance(kinds, list) else [kinds] if kinds is not None else []
        if not set(declared) <= _TYPES:
            raise SchemaError(f"{path}: bilinmeyen tip {declared}")
        ref = node.get("$ref")
        if ref is not None and _resolve(schema, ref) is None:
            raise SchemaError(f"{path}: çözülemeyen $ref {ref!r}")


def property_names(schema: Mapping[str, Any]) -> frozenset[str]:
    """Şemanın herhangi bir derinlikte bildirdiği bütün nesne anahtarları."""
    return frozenset(name for _, node in _nodes(schema, "#") for name in node.get("properties", {}))


def validate(instance: Any, schema: Mapping[str, Any]) -> list[str]:
    """Şemaya uymayan her yer için `<json yolu>: <neden>`; boş liste = geçerli."""
    return list(_errors(instance, schema, schema, "$"))


def _nodes(node: Any, path: str) -> Iterator[tuple[str, Mapping[str, Any]]]:
    if not isinstance(node, Mapping):
        return
    yield path, node
    for name, child in node.get("$defs", {}).items():
        yield from _nodes(child, f"{path}/$defs/{name}")
    for name, child in node.get("properties", {}).items():
        yield from _nodes(child, f"{path}/properties/{name}")
    if "items" in node:
        yield from _nodes(node["items"], f"{path}/items")


def _resolve(root: Mapping[str, Any], ref: str) -> Mapping[str, Any] | None:
    if not ref.startswith("#/$defs/"):
        return None
    found = root.get("$defs", {}).get(ref.removeprefix("#/$defs/"))
    return found if isinstance(found, Mapping) else None


def _type_ok(value: Any, kind: str) -> bool:
    if kind == "null":
        return value is None
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if kind == "string":
        return isinstance(value, str)
    if kind == "array":
        return isinstance(value, list)
    return isinstance(value, dict)


def _errors(value: Any, node: Mapping[str, Any], root: Mapping[str, Any], at: str) -> Iterator[str]:
    if "$ref" in node:
        target = _resolve(root, node["$ref"])
        if target is None:
            raise SchemaError(f"çözülemeyen $ref {node['$ref']!r}")
        yield from _errors(value, target, root, at)
        return
    kinds = node.get("type")
    if kinds is not None:
        allowed = kinds if isinstance(kinds, list) else [kinds]
        if not any(_type_ok(value, kind) for kind in allowed):
            yield f"{at}: tip {allowed} bekleniyordu, {type(value).__name__} geldi"
            return
    if "const" in node and not _same(value, node["const"]):
        yield f"{at}: sabit {node['const']!r} bekleniyordu"
    if "enum" in node and not any(_same(value, option) for option in node["enum"]):
        yield f"{at}: {node['enum']} dışında"
    if isinstance(value, str):
        yield from _string_errors(value, node, at)
    if isinstance(value, int | float) and not isinstance(value, bool):
        if "minimum" in node and value < node["minimum"]:
            yield f"{at}: {node['minimum']} altında"
        if "maximum" in node and value > node["maximum"]:
            yield f"{at}: {node['maximum']} üstünde"
    if isinstance(value, dict):
        yield from _object_errors(value, node, root, at)
    if isinstance(value, list) and "items" in node:
        for index, item in enumerate(value):
            yield from _errors(item, node["items"], root, f"{at}[{index}]")


def _string_errors(value: str, node: Mapping[str, Any], at: str) -> Iterator[str]:
    if "minLength" in node and len(value) < node["minLength"]:
        yield f"{at}: {node['minLength']} karakterden kısa"
    if "maxLength" in node and len(value) > node["maxLength"]:
        yield f"{at}: {node['maxLength']} karakterden uzun"
    if "pattern" in node and re.search(node["pattern"], value) is None:
        yield f"{at}: {node['pattern']!r} kalıbına uymuyor"


def _object_errors(
    value: dict[str, Any], node: Mapping[str, Any], root: Mapping[str, Any], at: str
) -> Iterator[str]:
    properties = node.get("properties", {})
    for name in node.get("required", []):
        if name not in value:
            yield f"{at}: zorunlu {name!r} yok"
    if node.get("additionalProperties") is False:
        for name in sorted(set(value) - set(properties)):
            yield f"{at}: bilinmeyen anahtar {name!r}"
    for name, child in properties.items():
        if name in value:
            yield from _errors(value[name], child, root, f"{at}.{name}")


def _same(left: Any, right: Any) -> bool:
    """JSON eşitliği: `True == 1` Python'da doğrudur, JSON'da değildir."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return bool(left == right)
