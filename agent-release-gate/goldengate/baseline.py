"""The baseline: the last known-good run, committed to the repo. The gate compares every run with it."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .runner import RunReport

BASELINE_VERSION = 1


class BaselineError(ValueError):
    """The baseline file is missing, malformed, or for a different suite."""


@dataclass(frozen=True)
class Baseline:
    suite: str
    first_pass_success_rate: float
    cases: dict[str, bool]


@dataclass(frozen=True)
class Policy:
    """When to block. Defaults are strict on purpose: loosen them in the open, in a reviewed change."""

    max_rate_drop: float = 0.0  # allowed fall in first-pass success, as a fraction (0.02 = 2 points)
    max_invented: int = 0  # invented values allowed in a run; anything above blocks
    allow_removed_cases: bool = False  # deleting a golden case is how a gate quietly gets weaker


@dataclass(frozen=True)
class Decision:
    blocked: bool
    reasons: tuple[str, ...]
    regressed: tuple[str, ...] = ()
    fixed: tuple[str, ...] = ()
    new: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    baseline_rate: float | None = None
    details: dict[str, list[str]] = field(default_factory=dict)


def baseline_from_report(report: RunReport) -> dict[str, Any]:
    return {
        "version": BASELINE_VERSION,
        "suite": report.suite,
        "agent": report.agent,
        "created_at": report.started_at,
        "summary": report.summary.to_json(),
        "cases": {r.case_id: r.passed for r in report.results},
    }


def save_baseline(report: RunReport, path: Path) -> None:
    """Write atomically, so an interrupted run never leaves a half-written baseline behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(baseline_from_report(report), indent=2, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".baseline-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_baseline(path: Path, suite: str) -> Baseline:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BaselineError(f"no baseline at {path}: run once with --set-baseline on a known-good agent") from None
    except json.JSONDecodeError as exc:
        raise BaselineError(f"{path}: invalid JSON at line {exc.lineno}: {exc.msg}") from None
    if not isinstance(obj, dict) or obj.get("version") != BASELINE_VERSION:
        raise BaselineError(f"{path}: unsupported baseline version (expected {BASELINE_VERSION})")
    if obj.get("suite") != suite:
        raise BaselineError(f"{path}: baseline is for suite {obj.get('suite')!r}, not {suite!r}")
    cases = obj.get("cases")
    if not isinstance(cases, dict) or not all(isinstance(k, str) and isinstance(v, bool) for k, v in cases.items()):
        raise BaselineError(f"{path}: 'cases' must map case ids to true/false")
    rate = (obj.get("summary") or {}).get("first_pass_success_rate")
    if not isinstance(rate, (int, float)) or isinstance(rate, bool) or not 0 <= rate <= 1:
        raise BaselineError(f"{path}: summary.first_pass_success_rate must be between 0 and 1")
    return Baseline(suite=suite, first_pass_success_rate=float(rate), cases=dict(cases))


def compare(report: RunReport, baseline: Baseline, policy: Policy = Policy()) -> Decision:
    current = {r.case_id: r for r in report.results}
    regressed = tuple(cid for cid, r in current.items() if baseline.cases.get(cid) is True and not r.passed)
    fixed = tuple(cid for cid, r in current.items() if baseline.cases.get(cid) is False and r.passed)
    new = tuple(cid for cid in current if cid not in baseline.cases)
    removed = tuple(cid for cid in baseline.cases if cid not in current)

    reasons: list[str] = []
    if regressed:
        reasons.append(f"{len(regressed)} case(s) that passed in the baseline now fail: {', '.join(regressed)}")
    rate = report.summary.first_pass_success_rate
    drop = baseline.first_pass_success_rate - rate
    if drop > policy.max_rate_drop + 1e-9:
        reasons.append(
            f"first-pass success fell from {baseline.first_pass_success_rate:.1%} to {rate:.1%}"
            f" (allowed drop {policy.max_rate_drop:.1%})"
        )
    invented = report.summary.invented_fields
    if invented > policy.max_invented:
        reasons.append(f"{invented} invented value(s) not found in the source (allowed {policy.max_invented})")
    if removed and not policy.allow_removed_cases:
        reasons.append(f"{len(removed)} golden case(s) were removed: {', '.join(removed)} (re-baseline in a reviewed change)")

    details = {cid: [f"{f.field or '-'}: {f.message}" for f in current[cid].findings] for cid in regressed}
    return Decision(
        blocked=bool(reasons),
        reasons=tuple(reasons),
        regressed=regressed,
        fixed=fixed,
        new=new,
        removed=removed,
        baseline_rate=baseline.first_pass_success_rate,
        details=details,
    )
