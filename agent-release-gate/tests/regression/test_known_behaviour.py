"""Regression tests: pin the example agent's outputs and exactly which cases each broken variant fails.

If one of these fails, either the example agent or the graders changed behaviour. Decide which on
purpose, then update the snapshot with:  python -m tests.regression.update_snapshot
"""

import json
import unittest

from agents.listing_agent import VARIANTS, extract_with
from goldengate import graders
from goldengate.cases import load_suite
from tests.helpers import ROOT, SCHEMA, SUITE_PATH

SNAPSHOT = ROOT / "tests" / "regression" / "snapshots" / "listings.outputs.json"

EXPECTED_FAILURES = {
    "baseline": {},
    "model-swap": {
        "c02-thousands": {"truth", "mismatch"},
        "c04-no-size": {"truth", "mismatch"},
        "c09-colour-last": {"truth", "mismatch"},
        "c10-eur-thousands": {"truth", "mismatch"},
    },
    "invent": {"c06-no-colour": {"truth", "mismatch"}, "c12-sparse": {"truth", "mismatch"}},
    "schema-drift": "every case, shape only",  # the price comes back as a string in all 12
}


def failures(variant):
    found = {}
    for case in load_suite(SUITE_PATH, SCHEMA):
        kinds = {f.kind for f in graders.grade(extract_with(case.input, variant), case.input, case.expected, SCHEMA)}
        if kinds:
            found[case.id] = kinds
    return found


class KnownBehaviourTest(unittest.TestCase):
    def test_every_variant_is_pinned(self):
        self.assertEqual(set(EXPECTED_FAILURES), set(VARIANTS))

    def test_baseline_outputs_match_the_snapshot(self):
        cases = load_suite(SUITE_PATH, SCHEMA)
        actual = {c.id: extract_with(c.input) for c in cases}
        self.assertEqual(actual, json.loads(SNAPSHOT.read_text(encoding="utf-8")))

    def test_each_variant_fails_exactly_the_known_cases(self):
        for variant, expected in EXPECTED_FAILURES.items():
            with self.subTest(variant=variant):
                actual = failures(variant)
                if expected == "every case, shape only":
                    self.assertEqual(len(actual), 12)
                    self.assertTrue(all(k == {"shape"} for k in actual.values()))
                else:
                    self.assertEqual(actual, expected)

    def test_committed_baseline_is_all_green(self):
        data = json.loads((ROOT / "baselines" / "listings.json").read_text(encoding="utf-8"))
        self.assertEqual(data["suite"], "listings")
        self.assertTrue(all(data["cases"].values()))
        self.assertEqual(len(data["cases"]), 12)


if __name__ == "__main__":
    unittest.main()
