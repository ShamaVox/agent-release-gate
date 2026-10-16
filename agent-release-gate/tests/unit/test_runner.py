import threading
import unittest

from goldengate.agents import Agent, AgentError
from goldengate.cases import Case
from goldengate.runner import quantile, run_suite
from tests.helpers import GOOD, SCHEMA, SOURCE

CASE = Case(id="c1", input=SOURCE, expected=GOOD)


def agent(fn):
    return Agent(spec="test", call=lambda text, timeout: fn(text))


class QuantileTest(unittest.TestCase):
    def test_nearest_rank(self):
        self.assertEqual(quantile([], 0.5), 0.0)
        self.assertEqual(quantile([5.0], 0.95), 5.0)
        self.assertEqual(quantile([4.0, 1.0, 3.0, 2.0], 0.5), 2.0)
        self.assertEqual(quantile(list(map(float, range(1, 101))), 0.95), 95.0)


class RunSuiteTest(unittest.TestCase):
    def test_summary_counts_pass_accuracy_and_invented(self):
        cases = [CASE, Case(id="c2", input=SOURCE, expected=GOOD)]
        outputs = iter([GOOD, dict(GOOD, color="Black")])
        report = run_suite(cases, agent(lambda _: next(outputs)), SCHEMA, "s", timeout_s=5)
        s = report.summary
        self.assertEqual((s.cases_total, s.cases_passed, s.case_errors, s.invented_fields), (2, 1, 0, 1))
        self.assertAlmostEqual(s.first_pass_success_rate, 0.5)
        self.assertAlmostEqual(s.field_accuracy, 11 / 12)
        self.assertEqual(report.to_json()["cases"][1]["findings"][0]["kind"], "truth")

    def test_agent_exceptions_fail_only_their_case(self):
        def flaky(text, _calls=[0]):
            _calls[0] += 1
            if _calls[0] == 1:
                raise KeyError("boom")
            return GOOD

        report = run_suite([CASE, Case(id="c2", input=SOURCE, expected=GOOD)], agent(flaky), SCHEMA, "s", 5)
        self.assertEqual([r.passed for r in report.results], [False, True])
        self.assertTrue(report.results[0].errored)
        self.assertIn("KeyError", report.results[0].findings[0].message)
        self.assertEqual(report.summary.case_errors, 1)

    def test_agent_error_message_is_kept(self):
        def broken(_):
            raise AgentError("exited with code 3")

        report = run_suite([CASE], agent(broken), SCHEMA, "s", 5)
        self.assertEqual(report.results[0].findings[0].message, "exited with code 3")

    def test_timeout_fails_the_case_and_the_run_continues(self):
        release = threading.Event()
        outputs = iter(["hang", "ok"])

        def slow(_):
            if next(outputs) == "hang":
                release.wait(5)
            return GOOD

        try:
            report = run_suite([CASE, Case(id="c2", input=SOURCE, expected=GOOD)], agent(slow), SCHEMA, "s", timeout_s=0.2)
        finally:
            release.set()
        self.assertIn("timed out", report.results[0].findings[0].message)
        self.assertTrue(report.results[1].passed)
        self.assertEqual(report.summary.latency_p95_ms, report.results[1].latency_ms)


if __name__ == "__main__":
    unittest.main()
