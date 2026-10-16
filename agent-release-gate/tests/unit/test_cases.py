import json
import tempfile
import unittest
from pathlib import Path

from goldengate.cases import SuiteError, load_suite
from tests.helpers import GOOD, SCHEMA, SUITE_PATH


def _line(**over):
    case = {"id": "c1", "input": "x", "expected": GOOD}
    case.update(over)
    return json.dumps(case)


class LoadSuiteTest(unittest.TestCase):
    def _load(self, text):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "suite.jsonl"
            path.write_text(text, encoding="utf-8")
            return load_suite(path, SCHEMA)

    def test_the_shipped_golden_set_loads(self):
        cases = load_suite(SUITE_PATH, SCHEMA)
        self.assertEqual(len(cases), 12)
        self.assertEqual(len({c.id for c in cases}), 12)

    def test_skips_blank_lines_and_comments(self):
        cases = self._load("# comment\n\n" + _line(tags=["a"]) + "\n")
        self.assertEqual([(c.id, c.tags) for c in cases], [("c1", ("a",))])

    def test_errors_name_the_line(self):
        with self.assertRaisesRegex(SuiteError, r"suite.jsonl:2: invalid JSON"):
            self._load(_line() + "\n{oops\n")

    def test_rejects_bad_cases(self):
        bad = [
            "[1]",
            _line(id="has space"),
            _line(id=""),
            _line(input=""),
            _line(input="x" * 20_001),
            _line(expected={"title": "only"}),
            _line(expected=dict(GOOD, price="12")),
            _line(tags="a"),
            _line(notes="extra key"),
        ]
        for text in bad:
            with self.subTest(text=text[:60]), self.assertRaises(SuiteError):
                self._load(text)

    def test_duplicate_ids_and_empty_suites(self):
        with self.assertRaisesRegex(SuiteError, "duplicate"):
            self._load(_line() + "\n" + _line())
        with self.assertRaisesRegex(SuiteError, "no cases"):
            self._load("# only a comment\n")
        with self.assertRaisesRegex(SuiteError, "not found"):
            load_suite(Path("/nonexistent/suite.jsonl"), SCHEMA)


if __name__ == "__main__":
    unittest.main()
