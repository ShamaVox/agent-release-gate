import json
import tempfile
import unittest
from pathlib import Path

from goldengate import baseline as bl
from goldengate.graders import Finding
from goldengate.runner import CaseResult, make_report


def result(cid, passed, invented=0):
    findings = tuple(Finding("truth", "color", "invented") for _ in range(invented))
    if not passed and not findings:
        findings = (Finding("mismatch", "price", "expected 1, got 2"),)
    return CaseResult(case_id=cid, passed=passed, findings=findings, correct_fields=6 if passed else 5, latency_ms=1.0)


def report(*results):
    return make_report("listings", "test", list(results), fields_per_case=6)


BASE = bl.Baseline(suite="listings", first_pass_success_rate=0.75, cases={"a": True, "b": True, "c": True, "d": False})


class CompareTest(unittest.TestCase):
    def test_same_results_pass(self):
        d = bl.compare(report(result("a", True), result("b", True), result("c", True), result("d", False)), BASE)
        self.assertFalse(d.blocked)
        self.assertEqual(d.reasons, ())

    def test_regression_blocks_and_names_cases_with_details(self):
        d = bl.compare(report(result("a", True), result("b", False), result("c", True), result("d", True)), BASE)
        self.assertTrue(d.blocked)
        self.assertEqual(d.regressed, ("b",))
        self.assertEqual(d.fixed, ("d",))
        self.assertEqual(d.details, {"b": ["price: expected 1, got 2"]})

    def test_a_drop_in_rate_blocks_unless_within_policy(self):
        r = report(result("a", True), result("b", True), result("c", True), result("d", False), result("e", False))
        self.assertTrue(bl.compare(r, BASE).blocked)  # 60% vs 75%, though no known case regressed
        self.assertEqual(bl.compare(r, BASE).new, ("e",))
        self.assertFalse(bl.compare(r, BASE, bl.Policy(max_rate_drop=0.2)).blocked)

    def test_invented_values_block_even_when_everything_else_holds(self):
        r = report(result("a", True), result("b", True), result("c", True), result("d", False, invented=1))
        d = bl.compare(r, BASE)
        self.assertTrue(d.blocked)
        self.assertIn("invented", d.reasons[0])
        self.assertFalse(bl.compare(r, BASE, bl.Policy(max_invented=1)).blocked)

    def test_removing_golden_cases_blocks(self):
        r = report(result("a", True), result("b", True), result("c", True))
        d = bl.compare(r, bl.Baseline("listings", 0.75, {"a": True, "b": True, "c": True, "d": False}))
        self.assertTrue(d.blocked)
        self.assertEqual(d.removed, ("d",))
        self.assertFalse(bl.compare(r, BASE, bl.Policy(allow_removed_cases=True)).blocked)


class SaveLoadTest(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "nested" / "listings.json"
            bl.save_baseline(report(result("a", True), result("b", False)), path)
            loaded = bl.load_baseline(path, "listings")
            self.assertEqual(loaded.cases, {"a": True, "b": False})
            self.assertEqual(loaded.first_pass_success_rate, 0.5)
            self.assertEqual(list(path.parent.glob(".baseline-*")), [])

    def test_rejects_missing_wrong_suite_and_malformed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "b.json"
            with self.assertRaisesRegex(bl.BaselineError, "--set-baseline"):
                bl.load_baseline(path, "listings")
            bad = {
                "{oops": "invalid JSON",
                json.dumps({"version": 9}): "version",
                json.dumps({"version": 1, "suite": "other"}): "not 'listings'",
                json.dumps({"version": 1, "suite": "listings", "cases": {"a": "yes"}}): "cases",
                json.dumps({"version": 1, "suite": "listings", "cases": {}, "summary": {"first_pass_success_rate": 2}}): "between 0 and 1",
            }
            for text, message in bad.items():
                with self.subTest(message=message):
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaisesRegex(bl.BaselineError, message):
                        bl.load_baseline(path, "listings")


if __name__ == "__main__":
    unittest.main()
