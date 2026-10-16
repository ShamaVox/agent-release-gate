"""Metrics in Prometheus text format, ready for a node_exporter textfile collector or a CI artifact.

Quality metrics (what the business cares about): first-pass success, field accuracy, invented values,
regressions. Operational metrics (what keeps the gate healthy): cases, errors, latency, run time, decision.
"""

from __future__ import annotations

from .baseline import Decision
from .runner import RunReport


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _fmt(value: float | int) -> str:
    return repr(float(value)) if isinstance(value, float) else str(value)


def render(report: RunReport, decision: Decision | None) -> str:
    labels = f'suite="{_escape(report.suite)}",agent="{_escape(report.agent)}"'
    s = report.summary
    rows: list[tuple[str, str, str, float | int, str]] = [
        ("goldengate_first_pass_success_ratio", "gauge", "Share of golden cases passed with no findings.", s.first_pass_success_rate, ""),
        ("goldengate_field_accuracy_ratio", "gauge", "Share of output fields equal to the known-right answer.", s.field_accuracy, ""),
        ("goldengate_invented_values", "gauge", "Output values that could not be traced to the source.", s.invented_fields, ""),
        ("goldengate_regressed_cases", "gauge", "Cases that passed in the baseline and fail now.", len(decision.regressed) if decision else 0, ""),
        ("goldengate_cases", "gauge", "Golden cases run.", s.cases_total, ""),
        ("goldengate_cases_passed", "gauge", "Golden cases passed.", s.cases_passed, ""),
        ("goldengate_case_errors", "gauge", "Cases where the agent raised, exited non-zero, timed out or returned non-JSON.", s.case_errors, ""),
        ("goldengate_agent_latency_ms", "gauge", "Agent latency per case, nearest-rank quantiles.", s.latency_p50_ms, 'quantile="0.5"'),
        ("goldengate_agent_latency_ms", "gauge", "", s.latency_p95_ms, 'quantile="0.95"'),
        ("goldengate_run_duration_seconds", "gauge", "Wall time of the whole run.", report.duration_s, ""),
        ("goldengate_gate_blocked", "gauge", "1 when the gate blocked the change, 0 when it passed.", int(decision.blocked) if decision else 0, ""),
    ]
    lines: list[str] = []
    seen: set[str] = set()
    for name, mtype, help_text, value, extra in rows:
        if name not in seen:
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} {mtype}")
            seen.add(name)
        all_labels = labels + ("," + extra if extra else "")
        lines.append(f"{name}{{{all_labels}}} {_fmt(value)}")
    return "\n".join(lines) + "\n"
