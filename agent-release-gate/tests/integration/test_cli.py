"""End to end: the real command line, the real golden set, the example agent, exit codes and files."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ROOT

PY_AGENT = "py:agents.listing_agent:extract"
CMD_AGENT = f"cmd:{sys.executable} agents/listing_agent.py"


def gate(*args, variant="baseline"):
    env = dict(os.environ, AGENT_VARIANT=variant)
    return subprocess.run(
        [sys.executable, "-m", "goldengate", *args],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120, check=False,
    )


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.baseline = self.dir / "baseline.json"
        self.out = self.dir / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def run_gate(self, *extra, agent=PY_AGENT, variant="baseline"):
        return gate(
            "run", "--suite", "golden/listings.jsonl", "--schema", "golden/listing.schema.json",
            "--agent", agent, "--baseline", str(self.baseline), "--out", str(self.out), *extra, variant=variant,
        )

    def test_set_baseline_then_pass(self):
        first = self.run_gate("--set-baseline")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("BASELINE SET", first.stdout)
        self.assertEqual(json.loads(self.baseline.read_text())["summary"]["cases_passed"], 12)

        second = self.run_gate()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("GATE: PASS", second.stdout)
        report = json.loads((self.out / "report.json").read_text())
        self.assertFalse(report["gate"]["blocked"])
        self.assertIn("goldengate_gate_blocked", (self.out / "metrics.prom").read_text())

    def test_model_swap_is_blocked_and_names_the_cases(self):
        self.run_gate("--set-baseline")
        res = self.run_gate(variant="model-swap")
        self.assertEqual(res.returncode, 1)
        self.assertIn("GATE: BLOCKED", res.stdout)
        self.assertIn("c02-thousands", res.stdout)
        report = json.loads((self.out / "report.json").read_text())
        self.assertEqual(report["gate"]["regressed"], ["c02-thousands", "c04-no-size", "c09-colour-last", "c10-eur-thousands"])
        self.assertIn('goldengate_gate_blocked{suite="listings",agent="py:agents.listing_agent:extract"} 1',
                      (self.out / "metrics.prom").read_text())

    def test_command_agent_gives_the_same_verdict(self):
        self.run_gate("--set-baseline")
        self.assertEqual(self.run_gate(agent=CMD_AGENT).returncode, 0)
        self.assertEqual(self.run_gate(agent=CMD_AGENT, variant="invent").returncode, 1)

    def test_configuration_errors_exit_2(self):
        no_baseline = self.run_gate()
        self.assertEqual(no_baseline.returncode, 2)
        self.assertIn("--set-baseline", no_baseline.stderr)
        self.assertEqual(self.run_gate("--max-rate-drop", "5").returncode, 2)
        self.assertEqual(gate("run", "--suite", "x").returncode, 2)  # argparse usage error
        self.assertEqual(self.run_gate(agent="py:nope:nothing").returncode, 2)

    def test_seed_catches_every_regression(self):
        res = gate("seed", "--suite", "golden/listings.jsonl", "--schema", "golden/listing.schema.json", "--agent", PY_AGENT)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("seeded regressions caught: 246 / 246", res.stdout)

    def test_committed_baseline_passes_with_the_known_good_agent(self):
        res = gate("run", "--suite", "golden/listings.jsonl", "--schema", "golden/listing.schema.json",
                   "--agent", PY_AGENT, "--out", str(self.out), "--quiet")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
