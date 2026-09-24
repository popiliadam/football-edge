"""Sözleşme doğrulayıcısı (`site/schema.py`): desteklenen alt küme, JSON tipleri, kapalı nesne."""

from __future__ import annotations

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
    ],
)
def test_each_violation_is_named_by_its_json_path(instance: dict[str, Any], needle: str) -> None:
    errors = validate(instance, OBJECT)

    assert any(needle in error for error in errors), errors


def test_const_false_is_not_const_zero() -> None:
    assert validate(0, {"const": False}) != []
    assert validate(False, {"const": 0}) != []


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


def test_property_names_reach_every_depth() -> None:
    assert property_names(OBJECT) == {"n", "tag", "maybe", "kind", "fixed", "ref", "items"}
