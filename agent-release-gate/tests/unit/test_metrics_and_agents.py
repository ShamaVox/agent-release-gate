import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from goldengate import baseline as bl, metrics
from goldengate.agents import AgentError, load_agent
from goldengate.runner import CaseResult, make_report


class MetricsTest(unittest.TestCase):
    def test_renders_quality_and_operational_metrics(self):
        r = make_report('my"suite', "py:a\\b", [CaseResult("a", True, (), 6, 2.0)], 6, duration_s=0.5)
        d = bl.Decision(blocked=True, reasons=("x",), regressed=("a", "b"))
        text = metrics.render(r, d)
        labels = 'suite="my\\"suite",agent="py:a\\\\b"'
        for line in (
            f"goldengate_first_pass_success_ratio{{{labels}}} 1.0",
            f"goldengate_regressed_cases{{{labels}}} 2",
            f"goldengate_gate_blocked{{{labels}}} 1",
            f'goldengate_agent_latency_ms{{{labels},quantile="0.95"}} 2.0',
            f"goldengate_run_duration_seconds{{{labels}}} 0.5",
        ):
            self.assertIn(line, text)
        self.assertEqual(text.count("# TYPE goldengate_agent_latency_ms"), 1)
        self.assertTrue(text.endswith("\n"))

    def test_no_decision_reports_zero(self):
        text = metrics.render(make_report("s", "a", [], 6), None)
        self.assertIn('goldengate_gate_blocked{suite="s",agent="a"} 0', text)


class AgentSpecTest(unittest.TestCase):
    def test_rejects_bad_specs(self):
        for spec in ("agents.listing_agent:extract", "py:nomodule", "py:no_such_module_xyz:f", "py:json:not_there", "cmd:", "http:x"):
            with self.subTest(spec=spec), self.assertRaises(AgentError):
                load_agent(spec)

    def test_python_agent(self):
        out = load_agent("py:agents.listing_agent:extract").call("Satin Scarf | $48.00 | SKU SS-77", 5)
        self.assertEqual(out["sku"], "SS-77")


class CommandAgentTest(unittest.TestCase):
    def _script(self, d, body):
        path = Path(d) / "agent.py"
        path.write_text(textwrap.dedent(body), encoding="utf-8")
        return load_agent(f"cmd:{sys.executable} {path}")

    def test_reads_json_from_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            a = self._script(d, """
                import json, sys
                req = json.load(sys.stdin)
                print(json.dumps({"echo": req["input"]}))
            """)
            self.assertEqual(a.call("hello", 10), {"echo": "hello"})

    def test_failures_become_agent_errors(self):
        bodies = {
            "import sys; sys.stderr.write('bad key'); sys.exit(3)": "exited with code 3: bad key",
            "print('not json')": "not JSON",
            "import time; time.sleep(5)": "timed out",
        }
        with tempfile.TemporaryDirectory() as d:
            for body, message in bodies.items():
                with self.subTest(message=message), self.assertRaisesRegex(AgentError, message):
                    self._script(d, body).call("x", 0.5)
        with self.assertRaisesRegex(AgentError, "command not found"):
            load_agent("cmd:definitely-not-a-command-xyz").call("x", 5)


if __name__ == "__main__":
    unittest.main()
