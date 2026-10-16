"""The output schema: which fields an agent must return, their types, and how each is checked against the source."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

FIELD_TYPES = ("string", "number")
TRUTH_KINDS = ("verbatim", "number", "evidence", "none")


class SchemaError(ValueError):
    """The schema file is missing, malformed or inconsistent."""


@dataclass(frozen=True)
class TruthRule:
    """How a field's value is traced back to the source text.

    verbatim: the value appears in the source (case and whitespace insensitive).
    number:   a number in the source equals the value (thousands separators allowed).
    evidence: the value is one of a fixed set, and one of its evidence tokens appears in the source.
    none:     not checked (use sparingly: an unchecked field can be invented without anyone noticing).
    """

    kind: str
    evidence: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    nullable: bool
    truth: TruthRule


@dataclass(frozen=True)
class Schema:
    name: str
    fields: tuple[Field, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)

    def get(self, name: str) -> Field | None:
        return next((f for f in self.fields if f.name == name), None)


def _parse_truth(name: str, raw: Any) -> TruthRule:
    if isinstance(raw, str):
        if raw not in TRUTH_KINDS or raw == "evidence":
            raise SchemaError(f"field {name!r}: truth must be one of verbatim, number, none, or an evidence object")
        return TruthRule(kind=raw)
    if isinstance(raw, dict) and set(raw) == {"evidence"} and isinstance(raw["evidence"], dict) and raw["evidence"]:
        evidence: dict[str, tuple[str, ...]] = {}
        for value, tokens in raw["evidence"].items():
            if not isinstance(tokens, list) or not tokens or not all(isinstance(t, str) and t.strip() for t in tokens):
                raise SchemaError(f"field {name!r}: evidence for {value!r} must be a non-empty list of strings")
            evidence[value] = tuple(tokens)
        return TruthRule(kind="evidence", evidence=evidence)
    raise SchemaError(f"field {name!r}: truth must be a string or {{\"evidence\": {{value: [tokens]}}}}")


def parse_schema(obj: Any) -> Schema:
    if not isinstance(obj, dict):
        raise SchemaError("schema must be a JSON object")
    unknown = set(obj) - {"name", "fields"}
    if unknown:
        raise SchemaError(f"unknown schema keys: {sorted(unknown)}")
    name = obj.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SchemaError("schema needs a non-empty 'name'")
    raw_fields = obj.get("fields")
    if not isinstance(raw_fields, dict) or not raw_fields:
        raise SchemaError("schema needs a non-empty 'fields' object")
    fields: list[Field] = []
    for fname, spec in raw_fields.items():
        if not isinstance(spec, dict):
            raise SchemaError(f"field {fname!r} must be an object")
        unknown = set(spec) - {"type", "nullable", "truth"}
        if unknown:
            raise SchemaError(f"field {fname!r}: unknown keys {sorted(unknown)}")
        ftype = spec.get("type")
        if ftype not in FIELD_TYPES:
            raise SchemaError(f"field {fname!r}: type must be one of {FIELD_TYPES}")
        nullable = spec.get("nullable", False)
        if not isinstance(nullable, bool):
            raise SchemaError(f"field {fname!r}: nullable must be true or false")
        truth = _parse_truth(fname, spec.get("truth", "verbatim"))
        if truth.kind == "number" and ftype != "number":
            raise SchemaError(f"field {fname!r}: truth 'number' needs type 'number'")
        if truth.kind in ("verbatim", "evidence") and ftype != "string":
            raise SchemaError(f"field {fname!r}: truth {truth.kind!r} needs type 'string'")
        fields.append(Field(name=fname, type=ftype, nullable=nullable, truth=truth))
    return Schema(name=name, fields=tuple(fields))


def load_schema(path: Path) -> Schema:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SchemaError(f"schema not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise SchemaError(f"{path}: invalid JSON at line {exc.lineno}: {exc.msg}") from None
    return parse_schema(obj)
