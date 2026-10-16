"""Graders. Shape checks the output's structure, truth checks that every value comes from the source,
correctness checks the output against the known-right answer.

Old gates check shape. A release gate for agents has to check truth too: a well-formed answer the
model invented passes every schema check.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Mapping

from .schema import Field, Schema

NUMBER_TOLERANCE = 0.005
_NUMBER_RE = re.compile(r"(?<![\d.])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\d.,])\d+(?:\.\d+)?")


@dataclass(frozen=True)
class Finding:
    kind: str  # shape | truth | mismatch | error
    field: str | None
    message: str

    def to_json(self) -> dict[str, Any]:
        return {"kind": self.kind, "field": self.field, "message": self.message}


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def numbers_in(text: str) -> list[float]:
    """Every number written in the text; '1,299.00' reads as 1299.0."""
    return [float(m.group(0).replace(",", "")) for m in _NUMBER_RE.finditer(text)]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _type_ok(f: Field, value: Any) -> bool:
    if value is None:
        return f.nullable
    if f.type == "number":
        return _is_number(value)
    return isinstance(value, str) and value.strip() != ""


def _describe(value: Any) -> str:
    return "null" if value is None else type(value).__name__


def grade_shape(output: Any, schema: Schema) -> list[Finding]:
    if not isinstance(output, dict):
        return [Finding("shape", None, f"output is {_describe(output)}, expected an object")]
    findings: list[Finding] = []
    for name in sorted(set(output) - set(schema.names)):
        findings.append(Finding("shape", name, "field is not in the schema"))
    for f in schema.fields:
        if f.name not in output:
            findings.append(Finding("shape", f.name, "required field is missing"))
        elif not _type_ok(f, output[f.name]):
            want = f.type + (" or null" if f.nullable else "")
            findings.append(Finding("shape", f.name, f"expected {want}, got {_describe(output[f.name])}"))
    return findings


def _contains_token(source: str, token: str) -> bool:
    if token.isalpha():
        return re.search(rf"(?<![A-Za-z]){re.escape(token.casefold())}(?![A-Za-z])", source.casefold()) is not None
    return token in source


def _truth_finding(f: Field, value: Any, source: str) -> Finding | None:
    rule = f.truth
    if rule.kind == "none" or value is None:
        return None
    if rule.kind == "verbatim":
        if normalize_text(value) not in normalize_text(source):
            return Finding("truth", f.name, f"{value!r} does not appear in the source")
    elif rule.kind == "number":
        if not any(abs(n - value) <= NUMBER_TOLERANCE for n in numbers_in(source)):
            return Finding("truth", f.name, f"{value!r} is not a number in the source")
    elif rule.kind == "evidence":
        tokens = rule.evidence.get(value)
        if tokens is None:
            return Finding("truth", f.name, f"{value!r} is not an allowed value ({', '.join(rule.evidence)})")
        if not any(_contains_token(source, t) for t in tokens):
            return Finding("truth", f.name, f"nothing in the source supports {value!r}")
    return None


def grade_truth(output: Any, source: str, schema: Schema) -> list[Finding]:
    """One finding per value that can't be traced back to the source: an invented value."""
    if not isinstance(output, dict):
        return []
    findings = []
    for f in schema.fields:
        if f.name in output and _type_ok(f, output[f.name]):
            finding = _truth_finding(f, output[f.name], source)
            if finding:
                findings.append(finding)
    return findings


def values_equal(f: Field, expected: Any, actual: Any) -> bool:
    if expected is None or actual is None:
        return expected is None and actual is None
    if f.type == "number":
        return abs(float(expected) - float(actual)) <= NUMBER_TOLERANCE
    return normalize_text(expected) == normalize_text(actual)


def grade_correctness(output: Any, expected: Mapping[str, Any], schema: Schema) -> list[Finding]:
    """Field-by-field comparison with the known-right answer, for fields whose shape is valid."""
    if not isinstance(output, dict):
        return []
    findings = []
    for f in schema.fields:
        if f.name in output and _type_ok(f, output[f.name]) and not values_equal(f, expected.get(f.name), output[f.name]):
            findings.append(Finding("mismatch", f.name, f"expected {expected.get(f.name)!r}, got {output[f.name]!r}"))
    return findings


def correct_field_count(output: Any, expected: Mapping[str, Any], schema: Schema) -> int:
    if not isinstance(output, dict):
        return 0
    return sum(
        1
        for f in schema.fields
        if f.name in output and _type_ok(f, output[f.name]) and values_equal(f, expected.get(f.name), output[f.name])
    )


def grade(output: Any, source: str, expected: Mapping[str, Any], schema: Schema) -> list[Finding]:
    return grade_shape(output, schema) + grade_truth(output, source, schema) + grade_correctness(output, expected, schema)
