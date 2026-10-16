"""Seeded regressions: break known-good outputs on purpose and prove the graders catch every one.

A gate you have never seen fail is a gate you can't trust. For each passing case and each field this
makes the mistakes agents really make (drop a field, change its type, change its value, invent a value
the source never had) and grades the broken output. Every mutation must fail its case.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from . import graders
from .cases import Case
from .schema import Field, Schema

INVENTED_TEXT = "Zzyzx Invented"
INVENTED_NUMBER = 987654.32


@dataclass(frozen=True)
class Mutation:
    case_id: str
    label: str
    output: Any


def _changed_value(f: Field, value: Any) -> Any:
    if f.type == "number":
        return round(float(value) * 1.37 + 1, 2)
    if f.truth.kind == "evidence":
        others = [v for v in f.truth.evidence if v != value]
        return others[0] if others else INVENTED_TEXT
    return f"{value} {INVENTED_TEXT}"


def mutations_for(case: Case, output: dict[str, Any], schema: Schema) -> list[Mutation]:
    found: list[Mutation] = []

    def add(label: str, change: Any) -> None:
        mutated = copy.deepcopy(output)
        change(mutated)
        found.append(Mutation(case.id, label, mutated))

    for f in schema.fields:
        value = output.get(f.name)
        add(f"{f.name}: dropped", lambda o, n=f.name: o.pop(n))
        add(f"{f.name}: wrong type", lambda o, n=f.name, t=f.type: o.__setitem__(n, [] if t == "string" else "12"))
        if value is None:
            invented = INVENTED_NUMBER if f.type == "number" else INVENTED_TEXT
            add(f"{f.name}: invented where the source has none", lambda o, n=f.name, v=invented: o.__setitem__(n, v))
        else:
            add(f"{f.name}: changed value", lambda o, n=f.name, v=_changed_value(f, value): o.__setitem__(n, v))
            if f.nullable:
                add(f"{f.name}: lost to null", lambda o, n=f.name: o.__setitem__(n, None))
    add("extra field", lambda o: o.__setitem__("confidence_note", "looks right"))
    return found


@dataclass(frozen=True)
class SeedResult:
    total: int
    caught: int
    escaped: tuple[Mutation, ...]
    skipped_cases: tuple[str, ...]


def seed(cases: list[Case], outputs: dict[str, Any], schema: Schema) -> SeedResult:
    """outputs: case id -> the agent's output. Only cases the agent currently passes are mutated."""
    total = caught = 0
    escaped: list[Mutation] = []
    skipped: list[str] = []
    for case in cases:
        output = outputs.get(case.id)
        if not isinstance(output, dict) or graders.grade(output, case.input, case.expected, schema):
            skipped.append(case.id)
            continue
        for m in mutations_for(case, output, schema):
            total += 1
            if graders.grade(m.output, case.input, case.expected, schema):
                caught += 1
            else:
                escaped.append(m)
    return SeedResult(total=total, caught=caught, escaped=tuple(escaped), skipped_cases=tuple(skipped))
