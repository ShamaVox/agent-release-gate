"""Running the golden set against an agent and summarizing the results."""

from __future__ import annotations

import concurrent.futures
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from . import graders
from .agents import Agent, AgentError
from .cases import Case
from .schema import Schema


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    passed: bool
    findings: tuple[graders.Finding, ...]
    correct_fields: int
    latency_ms: float
    output: Any = None

    @property
    def errored(self) -> bool:
        return any(f.kind == "error" for f in self.findings)

    @property
    def invented(self) -> int:
        return sum(1 for f in self.findings if f.kind == "truth")

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.case_id,
            "passed": self.passed,
            "latency_ms": round(self.latency_ms, 3),
            "findings": [f.to_json() for f in self.findings],
            "output": self.output,
        }


@dataclass(frozen=True)
class Summary:
    cases_total: int
    cases_passed: int
    case_errors: int
    first_pass_success_rate: float
    field_accuracy: float
    invented_fields: int
    latency_p50_ms: float
    latency_p95_ms: float

    def to_json(self) -> dict[str, Any]:
        return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


@dataclass(frozen=True)
class RunReport:
    suite: str
    agent: str
    started_at: str
    duration_s: float
    results: tuple[CaseResult, ...]
    summary: Summary

    def to_json(self) -> dict[str, Any]:
        return {
            "suite": self.suite,
            "agent": self.agent,
            "started_at": self.started_at,
            "duration_s": round(self.duration_s, 3),
            "summary": self.summary.to_json(),
            "cases": [r.to_json() for r in self.results],
        }


def quantile(values: list[float], q: float) -> float:
    """Nearest-rank quantile; 0.0 for no values."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


def summarize(results: tuple[CaseResult, ...], fields_per_case: int) -> Summary:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    latencies = [r.latency_ms for r in results if not r.errored]
    possible = total * fields_per_case
    return Summary(
        cases_total=total,
        cases_passed=passed,
        case_errors=sum(1 for r in results if r.errored),
        first_pass_success_rate=passed / total if total else 0.0,
        field_accuracy=sum(r.correct_fields for r in results) / possible if possible else 0.0,
        invented_fields=sum(r.invented for r in results),
        latency_p50_ms=quantile(latencies, 0.5),
        latency_p95_ms=quantile(latencies, 0.95),
    )


def grade_case(case: Case, output: Any, schema: Schema, latency_ms: float) -> CaseResult:
    findings = graders.grade(output, case.input, case.expected, schema)
    return CaseResult(
        case_id=case.id,
        passed=not findings,
        findings=tuple(findings),
        correct_fields=graders.correct_field_count(output, case.expected, schema),
        latency_ms=latency_ms,
        output=output,
    )


def run_suite(cases: list[Case], agent: Agent, schema: Schema, suite_name: str, timeout_s: float) -> RunReport:
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    results: list[CaseResult] = []
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="goldengate-agent")
    try:
        for case in cases:
            c0 = time.perf_counter()
            try:
                output = pool.submit(agent.call, case.input, timeout_s).result(timeout=timeout_s)
            except concurrent.futures.TimeoutError:
                # The stuck call keeps its thread; start a fresh worker so the next case is not queued behind it.
                pool.shutdown(wait=False, cancel_futures=True)
                pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="goldengate-agent")
                results.append(_errored(case, f"timed out after {timeout_s:g}s", c0))
                continue
            except AgentError as exc:
                results.append(_errored(case, str(exc), c0))
                continue
            except Exception as exc:  # the agent is user code: any exception is that case's failure, not the run's
                results.append(_errored(case, f"{type(exc).__name__}: {exc}", c0))
                continue
            results.append(grade_case(case, output, schema, (time.perf_counter() - c0) * 1000))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return make_report(
        suite_name, agent.spec, results, len(schema.fields),
        duration_s=time.perf_counter() - t0, started_at=started.isoformat(timespec="seconds"),
    )


def make_report(
    suite: str,
    agent: str,
    results: list[CaseResult],
    fields_per_case: int,
    duration_s: float = 0.0,
    started_at: str | None = None,
) -> RunReport:
    frozen = tuple(results)
    return RunReport(
        suite=suite,
        agent=agent,
        started_at=started_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        duration_s=duration_s,
        results=frozen,
        summary=summarize(frozen, fields_per_case),
    )


def _errored(case: Case, message: str, c0: float) -> CaseResult:
    return CaseResult(
        case_id=case.id,
        passed=False,
        findings=(graders.Finding("error", None, message),),
        correct_fields=0,
        latency_ms=(time.perf_counter() - c0) * 1000,
    )
