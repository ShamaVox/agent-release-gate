"""Command line: `python -m goldengate run ...` and `python -m goldengate seed ...`.

Exit codes: 0 the gate passed, 1 the gate blocked the change, 2 a usage or configuration error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence, TextIO

from . import __version__, baseline as bl, metrics, seeding
from .agents import AgentError, load_agent
from .cases import SuiteError, load_suite
from .runner import RunReport, run_suite
from .schema import SchemaError, load_schema

EXIT_PASS, EXIT_BLOCKED, EXIT_ERROR = 0, 1, 2


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # usage errors exit 2, like every other configuration error
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"error: {message}\n")


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--suite", required=True, type=Path, help="golden set, one JSON case per line")
    p.add_argument("--schema", required=True, type=Path, help="output schema (JSON)")
    p.add_argument("--agent", required=True, help="py:package.module:function or cmd:<command>")
    p.add_argument("--timeout", type=float, default=30.0, help="seconds per case (default 30)")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="goldengate", description="A release gate for AI agents.")
    parser.add_argument("--version", action="version", version=f"goldengate {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    run = sub.add_parser("run", help="run the golden set and gate against the baseline")
    _common(run)
    run.add_argument("--baseline", type=Path, help="baseline file (default: baselines/<suite name>.json)")
    run.add_argument("--set-baseline", action="store_true", help="record this run as the new baseline")
    run.add_argument("--out", type=Path, default=Path(".goldengate"), help="where report.json and metrics.prom go")
    run.add_argument("--max-rate-drop", type=float, default=0.0, help="allowed fall in first-pass success, 0-1 (default 0)")
    run.add_argument("--max-invented", type=int, default=0, help="invented values allowed (default 0)")
    run.add_argument("--allow-removed-cases", action="store_true", help="do not block when golden cases were deleted")
    run.add_argument("--quiet", action="store_true", help="print only the decision")

    seed = sub.add_parser("seed", help="break known-good outputs on purpose and check every break is caught")
    _common(seed)
    return parser


def _load(args: argparse.Namespace):
    schema = load_schema(args.schema)
    cases = load_suite(args.suite, schema)
    agent = load_agent(args.agent)
    if args.timeout <= 0:
        raise SchemaError("--timeout must be greater than 0")
    return schema, cases, agent


def _suite_name(path: Path) -> str:
    return path.stem


def _print_summary(report: RunReport, decision: bl.Decision | None, out: TextIO) -> None:
    s = report.summary
    print(f"goldengate · suite {report.suite} ({s.cases_total} cases) · agent {report.agent}", file=out)
    base = f"   (baseline {decision.baseline_rate:.1%})" if decision and decision.baseline_rate is not None else ""
    print(f"  first-pass success  {s.cases_passed}/{s.cases_total}  {s.first_pass_success_rate:.1%}{base}", file=out)
    print(f"  field accuracy      {s.field_accuracy:.1%}", file=out)
    print(f"  invented values     {s.invented_fields}", file=out)
    print(f"  agent errors        {s.case_errors}", file=out)
    print(f"  latency p50 / p95   {s.latency_p50_ms:.1f} / {s.latency_p95_ms:.1f} ms", file=out)
    failing = [r for r in report.results if not r.passed]
    if failing and not decision:
        print("  failing cases:", file=out)
        for r in failing:
            print(f"    {r.case_id}: " + "; ".join(f"{f.field or '-'}: {f.message}" for f in r.findings), file=out)
    if decision:
        for label, ids in (("fixed", decision.fixed), ("new", decision.new)):
            if ids:
                print(f"  {label}: {', '.join(ids)}", file=out)


def _cmd_run(args: argparse.Namespace, out: TextIO) -> int:
    if not 0 <= args.max_rate_drop <= 1:
        raise SchemaError("--max-rate-drop must be between 0 and 1")
    if args.max_invented < 0:
        raise SchemaError("--max-invented must be 0 or more")
    schema, cases, agent = _load(args)
    suite = _suite_name(args.suite)
    baseline_path = args.baseline or Path("baselines") / f"{suite}.json"

    report = run_suite(cases, agent, schema, suite, args.timeout)

    decision = None
    if not args.set_baseline:
        baseline = bl.load_baseline(baseline_path, suite)
        policy = bl.Policy(
            max_rate_drop=args.max_rate_drop,
            max_invented=args.max_invented,
            allow_removed_cases=args.allow_removed_cases,
        )
        decision = bl.compare(report, baseline, policy)

    args.out.mkdir(parents=True, exist_ok=True)
    payload = report.to_json()
    if decision:
        payload["gate"] = {
            "blocked": decision.blocked,
            "reasons": list(decision.reasons),
            "regressed": list(decision.regressed),
            "fixed": list(decision.fixed),
            "new": list(decision.new),
            "removed": list(decision.removed),
        }
    (args.out / "report.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (args.out / "metrics.prom").write_text(metrics.render(report, decision), encoding="utf-8")

    if not args.quiet:
        _print_summary(report, decision, out)

    if args.set_baseline:
        bl.save_baseline(report, baseline_path)
        print(f"BASELINE SET: {baseline_path} ({report.summary.cases_passed}/{report.summary.cases_total} passing)", file=out)
        if report.summary.invented_fields:
            print(f"warning: this baseline run has {report.summary.invented_fields} invented value(s); later runs still block on them", file=out)
        return EXIT_PASS

    assert decision is not None
    if not decision.blocked:
        print("GATE: PASS", file=out)
        return EXIT_PASS
    print("GATE: BLOCKED", file=out)
    for reason in decision.reasons:
        print(f"  - {reason}", file=out)
    for cid, lines in decision.details.items():
        for line in lines:
            print(f"      {cid} {line}", file=out)
    print(f"  full report: {args.out / 'report.json'}", file=out)
    return EXIT_BLOCKED


def _cmd_seed(args: argparse.Namespace, out: TextIO) -> int:
    schema, cases, agent = _load(args)
    report = run_suite(cases, agent, schema, _suite_name(args.suite), args.timeout)
    outputs = {r.case_id: r.output for r in report.results}
    result = seeding.seed(cases, outputs, schema)
    if result.total == 0:
        print("seed: no passing cases to mutate; fix the agent or the golden set first", file=out)
        return EXIT_ERROR
    print(f"seeded regressions caught: {result.caught} / {result.total}", file=out)
    if result.skipped_cases:
        print(f"  skipped (already failing): {', '.join(result.skipped_cases)}", file=out)
    for m in result.escaped:
        print(f"  ESCAPED {m.case_id} {m.label}", file=out)
    return EXIT_BLOCKED if result.escaped else EXIT_PASS


def main(argv: Sequence[str] | None = None, out: TextIO = sys.stdout, err: TextIO = sys.stderr) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return _cmd_run(args, out)
        return _cmd_seed(args, out)
    except (SchemaError, SuiteError, AgentError, bl.BaselineError) as exc:
        print(f"error: {exc}", file=err)
        return EXIT_ERROR
