"""Sözleşme doğrulayıcısı (`site/schema.py`): desteklenen alt küme, JSON tipleri, kapalı nesne."""

from __future__ import annotations

import re
from typing import Any

import pytest

from football_edge.site.schema import SchemaError, check_schema, property_names, validate

OBJECT: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["n", "tag"],
    "properties": {
        "n": {"type": "integer", "minimum": 0},
        "tag": {"type": "string", "pattern": "^[a-z]+$", "maxLength": 5},
        "maybe": {"type": ["number", "null"]},
        "kind": {"enum": ["a", "b"]},
        "fixed": {"const": None},
        "ref": {"$ref": "#/$defs/flag"},
        "items": {"type": "array", "items": {"type": "boolean"}},
        "pct": {"type": "number", "maximum": 100},
        "name": {"type": "string", "minLength": 1},
    },
    "$defs": {"flag": {"type": "boolean"}},
}


def test_a_valid_instance_has_no_errors() -> None:
    check_schema(OBJECT)
    instance = {"n": 3, "tag": "ab", "maybe": None, "kind": "a", "fixed": None, "ref": True}

    assert validate({**instance, "items": [True, False]}, OBJECT) == []


@pytest.mark.parametrize(
    ("instance", "needle"),
    [
        ({"tag": "ab"}, "zorunlu 'n'"),
        ({"n": 1, "tag": "ab", "extra": 1}, "bilinmeyen anahtar 'extra'"),
        ({"n": True, "tag": "ab"}, "$.n: tip"),  # JSON'da bool tamsayı değildir
        ({"n": 1.5, "tag": "ab"}, "$.n: tip"),
        ({"n": -1, "tag": "ab"}, "$.n: 0 altında"),
        ({"n": 1, "tag": "AB"}, "$.tag: '^[a-z]+$'"),
        ({"n": 1, "tag": "abcdef"}, "$.tag: 5 karakterden uzun"),
        ({"n": 1, "tag": "ab", "maybe": "x"}, "$.maybe: tip"),
        ({"n": 1, "tag": "ab", "kind": "c"}, "$.kind:"),
        ({"n": 1, "tag": "ab", "fixed": 0}, "$.fixed: sabit"),
        ({"n": 1, "tag": "ab", "ref": 1}, "$.ref: tip"),
        ({"n": 1, "tag": "ab", "items": [True, 0]}, "$.items[1]: tip"),
        ({"n": 1, "tag": "ab", "pct": 100.5}, "$.pct: 100 üstünde"),
        ({"n": 1, "tag": "ab", "name": ""}, "$.name: 1 karakterden kısa"),
        # Python'un `$`ı sondaki `\n`in önünde de eşleşir; JSON Schema'nınki (ECMA-262) eşleşmez.
        ({"n": 1, "tag": "ab\n"}, "$.tag: '^[a-z]+$'"),
        # JSON'da NaN/sonsuz yoktur; `nan < 0` hep yanlış olduğundan sınırlar da onu yakalamaz.
        ({"n": 1, "tag": "ab", "maybe": float("nan")}, "$.maybe: sonlu olmayan sayı"),
        ({"n": 1, "tag": "ab", "pct": float("inf")}, "$.pct: sonlu olmayan sayı"),
        ({"n": 1, "tag": "ab", "maybe": float("-inf")}, "$.maybe: sonlu olmayan sayı"),
    ],
)
def test_each_violation_is_named_by_its_json_path(instance: dict[str, Any], needle: str) -> None:
    errors = validate(instance, OBJECT)

    assert any(needle in error for error in errors), errors


def test_const_false_is_not_const_zero() -> None:
    assert validate(0, {"const": False}) != []
    assert validate(False, {"const": 0}) != []


@pytest.mark.parametrize(
    ("instance", "expected"),
    [([True], [1]), ([1], [True]), ({"a": 1}, {"a": True}), ([[0]], [[False]])],
)
def test_json_equality_separates_bool_and_int_inside_containers(
    instance: Any, expected: Any
) -> None:
    assert validate(instance, {"const": expected}) != []
    assert validate(instance, {"enum": [expected]}) != []
    assert validate(expected, {"const": expected}) == []


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object", "properties": {}, "additionalProperties": False, "oneOf": []},
        {"type": "object", "properties": {"a": {"type": "string"}}},
        {"type": "object", "properties": {}, "additionalProperties": True},
        {"type": "string", "format": "date-time"},
        {"type": "decimal"},
        {"$ref": "#/$defs/yok"},
    ],
)
def test_a_schema_outside_the_supported_subset_is_refused(schema: dict[str, Any]) -> None:
    """Doğrulayıcının sessizce yok saydığı bir anahtar kelime, hiç sınanmayan bir kural olurdu."""
    with pytest.raises(SchemaError):
        check_schema(schema)


def _closed(**children: Any) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "properties": children}


@pytest.mark.parametrize(
    ("schema", "needle"),
    [
        ({"type": "object", "additionalProperties": True}, "yalnız false olabilir"),
        (_closed(a={"type": "string", "additionalProperties": True}), "yalnız false olabilir"),
        ({"type": "object"}, "properties ve additionalProperties: false"),
        (_closed(p={"type": ["object", "null"]}), "properties ve additionalProperties: false"),
        (
            _closed(p={"type": "object", "properties": {}}),
            "properties ve additionalProperties: false",
        ),
        ({"properties": {}, "additionalProperties": False}, "type, const, enum ya da $ref"),
        (_closed(p={}), "type, const, enum ya da $ref"),
        (_closed(p={"description": "tipsiz"}), "type, const, enum ya da $ref"),
        ({"type": "string", "properties": {}, "additionalProperties": False}, "yalnız nesnede"),
        (_closed(a={"type": "array"}), "items taşımalı"),
        (
            {
                **_closed(a={"$ref": "#/$defs/s", "maxLength": 3}),
                "$defs": {"s": {"type": "string"}},
            },
            "$ref yanında",
        ),
        (_closed(a={"type": "string", "pattern": "[a-z]+"}), "^…$ ile çapalanmalı"),
        (_closed(a={"type": "string", "pattern": "^[a-z]+"}), "^…$ ile çapalanmalı"),
        (_closed(a={"type": "string", "pattern": "^[a-z]+\\$"}), "^…$ ile çapalanmalı"),
    ],
)
def test_every_node_is_typed_closed_and_applies_all_of_its_keywords(
    schema: dict[str, Any], needle: str
) -> None:
    """B6: her nesne kapalı; tipsiz düğüm, açık nesne, `$ref` kardeşi her şeyi geçirirdi."""
    with pytest.raises(SchemaError, match=re.escape(needle)):
        check_schema(schema)


def test_validate_refuses_a_schema_outside_the_subset_before_reading_the_instance() -> None:
    with pytest.raises(SchemaError):
        validate("x", {"type": "string", "format": "date-time"})


def test_property_names_reach_every_depth() -> None:
    assert property_names(OBJECT) == {
        "n",
        "tag",
        "maybe",
        "kind",
        "fixed",
        "ref",
        "items",
        "pct",
        "name",
    }
