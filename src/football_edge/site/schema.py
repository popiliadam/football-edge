"""Anlık görüntü şemasının (`web/contract/snapshot.schema.json`) bağımlılıksız doğrulayıcısı.

JSON Schema'nın yalnız sözleşmenin kullandığı alt kümesi desteklenir. Şema bilinmeyen bir anahtar
kelime taşırsa `SchemaError` yükselir: doğrulayıcının SESSİZCE yok saydığı bir kural, sözleşmede
yazılı ama hiç sınanmayan bir kural olurdu. Aynı nedenle her düğüm tiplidir (`type`/`const`/`enum`/
`$ref`), her nesne `properties` ve `additionalProperties: false` taşır (B6), her dizi `items` taşır,
`$ref`in yanında kural olmaz (uygulanmazdı). Kalıplar `^…$` çapalıdır ve TAM eşleşmeyle
uygulanır: Python'un `$`ı sondaki satır sonunun önünde de eşleşir, JSON Schema'nınki (ECMA-262)
eşleşmez. JSON'da NaN/sonsuz yoktur; sınır karşılaştırmaları NaN'ı göremediği için ayrıca
reddedilir.
"""

from __future__ import annotations

import math
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
_SHAPERS = frozenset({"type", "const", "enum", "$ref"})
_REF_COMPANIONS = frozenset({"$ref", "title", "description"})


class SchemaError(ValueError):
    """Şemanın kendisi desteklenen alt kümenin dışında."""


def check_schema(schema: Mapping[str, Any]) -> None:
    """Her düğüm yalnız desteklenen anahtar kelimeleri taşır ve tiplidir; nesneler kapalıdır."""
    for path, node in _nodes(schema, "#"):
        _check_node(schema, path, node)


def _check_node(root: Mapping[str, Any], path: str, node: Mapping[str, Any]) -> None:
    unknown = sorted(set(node) - SUPPORTED)
    if unknown:
        raise SchemaError(f"{path}: desteklenmeyen anahtar kelime {unknown}")
    if "$ref" in node:
        _check_ref(root, path, node)
        return
    if not _SHAPERS & set(node):
        raise SchemaError(f"{path}: düğüm type, const, enum ya da $ref taşımalı")
    if "additionalProperties" in node and node["additionalProperties"] is not False:
        raise SchemaError(f"{path}: additionalProperties yalnız false olabilir")
    kinds = node.get("type")
    declared = kinds if isinstance(kinds, list) else [kinds] if kinds is not None else []
    if not set(declared) <= _TYPES:
        raise SchemaError(f"{path}: bilinmeyen tip {declared}")
    closed = "properties" in node and node.get("additionalProperties") is False
    if "object" in declared and not closed:
        raise SchemaError(f"{path}: nesne properties ve additionalProperties: false taşımalı")
    if "properties" in node and "object" not in declared:
        raise SchemaError(f"{path}: properties yalnız nesnede olabilir")
    if "array" in declared and "items" not in node:
        raise SchemaError(f"{path}: dizi items taşımalı")
    if "pattern" in node:
        _check_pattern(path, node["pattern"])


def _check_ref(root: Mapping[str, Any], path: str, node: Mapping[str, Any]) -> None:
    siblings = sorted(set(node) - _REF_COMPANIONS)
    if siblings:
        raise SchemaError(f"{path}: $ref yanında anahtar kelime {siblings} (uygulanmazdı)")
    if _resolve(root, node["$ref"]) is None:
        raise SchemaError(f"{path}: çözülemeyen $ref {node['$ref']!r}")


def _check_pattern(path: str, pattern: Any) -> None:
    anchored = (
        isinstance(pattern, str)
        and pattern.startswith("^")
        and pattern.endswith("$")
        and not pattern.endswith("\\$")
    )
    if not anchored:
        raise SchemaError(f"{path}: kalıp ^…$ ile çapalanmalı (tam eşleşme uygulanır)")


def property_names(schema: Mapping[str, Any]) -> frozenset[str]:
    """Şemanın herhangi bir derinlikte bildirdiği bütün nesne anahtarları."""
    return frozenset(name for _, node in _nodes(schema, "#") for name in node.get("properties", {}))


def validate(instance: Any, schema: Mapping[str, Any]) -> list[str]:
    """Şemaya uymayan her yer için `<json yolu>: <neden>`; boş liste = geçerli.

    Şema önce `check_schema`den geçer: alt küme dışı bir şema `SchemaError` yükseltir.
    """
    check_schema(schema)
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
    if isinstance(value, float) and not math.isfinite(value):
        yield f"{at}: sonlu olmayan sayı"
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
    if "pattern" in node and re.fullmatch(node["pattern"], value) is None:
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
    """JSON eşitliği: `True == 1` Python'da doğrudur, JSON'da değildir — iç içe dizi/nesnede de."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(map(_same, left, right))
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_same(left[key], right[key]) for key in left)
    return bool(left == right)
