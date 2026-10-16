"""The golden set: real inputs with known-right answers, one JSON object per line."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .graders import grade_shape
from .schema import Schema

CASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MAX_INPUT_CHARS = 20_000
CASE_KEYS = {"id", "input", "expected", "tags"}


class SuiteError(ValueError):
    """The golden set is missing, malformed, or disagrees with the schema."""


@dataclass(frozen=True)
class Case:
    id: str
    input: str
    expected: dict[str, Any]
    tags: tuple[str, ...] = ()


def _case_from(obj: Any, where: str, schema: Schema) -> Case:
    if not isinstance(obj, dict):
        raise SuiteError(f"{where}: each line must be a JSON object")
    unknown = set(obj) - CASE_KEYS
    if unknown:
        raise SuiteError(f"{where}: unknown keys {sorted(unknown)}")
    cid = obj.get("id")
    if not isinstance(cid, str) or not CASE_ID_RE.match(cid):
        raise SuiteError(f"{where}: 'id' must match {CASE_ID_RE.pattern}")
    text = obj.get("input")
    if not isinstance(text, str) or not text.strip():
        raise SuiteError(f"{where}: case {cid!r} needs a non-empty string 'input'")
    if len(text) > MAX_INPUT_CHARS:
        raise SuiteError(f"{where}: case {cid!r} input is over {MAX_INPUT_CHARS} characters")
    expected = obj.get("expected")
    problems = grade_shape(expected, schema)
    if problems:
        detail = "; ".join(f"{p.field or 'expected'}: {p.message}" for p in problems)
        raise SuiteError(f"{where}: case {cid!r} 'expected' does not match the schema ({detail})")
    tags = obj.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(t, str) and t for t in tags):
        raise SuiteError(f"{where}: case {cid!r} 'tags' must be a list of strings")
    return Case(id=cid, input=text, expected=dict(expected), tags=tuple(tags))


def load_suite(path: Path, schema: Schema) -> list[Case]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise SuiteError(f"golden set not found: {path}") from None
    cases: list[Case] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        where = f"{path}:{lineno}"
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SuiteError(f"{where}: invalid JSON: {exc.msg}") from None
        case = _case_from(obj, where, schema)
        if case.id in seen:
            raise SuiteError(f"{where}: duplicate case id {case.id!r}")
        seen.add(case.id)
        cases.append(case)
    if not cases:
        raise SuiteError(f"{path}: the golden set has no cases")
    return cases
