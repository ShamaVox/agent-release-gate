import json
import tempfile
import unittest
from pathlib import Path

from goldengate.schema import SchemaError, load_schema, parse_schema


def _schema(**fields):
    return {"name": "t", "fields": fields}


class ParseSchemaTest(unittest.TestCase):
    def test_parses_types_nullability_and_truth_rules(self):
        s = parse_schema(_schema(
            a={"type": "string"},
            b={"type": "number", "truth": "number"},
            c={"type": "string", "nullable": True, "truth": {"evidence": {"X": ["x"]}}},
            d={"type": "string", "truth": "none"},
        ))
        self.assertEqual(s.names, ("a", "b", "c", "d"))
        self.assertEqual(s.get("a").truth.kind, "verbatim")
        self.assertTrue(s.get("c").nullable)
        self.assertEqual(s.get("c").truth.evidence, {"X": ("x",)})
        self.assertIsNone(s.get("missing"))

    def test_rejects_bad_schemas(self):
        bad = [
            [],
            {"fields": {"a": {"type": "string"}}},
            {"name": "t", "fields": {}},
            {"name": "t", "fields": {"a": {"type": "string"}}, "extra": 1},
            _schema(a={"type": "bool"}),
            _schema(a={"type": "string", "nullable": "yes"}),
            _schema(a={"type": "string", "colour": "red"}),
            _schema(a={"type": "string", "truth": "fuzzy"}),
            _schema(a={"type": "string", "truth": "evidence"}),
            _schema(a={"type": "string", "truth": {"evidence": {"X": []}}}),
            _schema(a={"type": "string", "truth": {"evidence": {}}}),
            _schema(a={"type": "string", "truth": "number"}),
            _schema(a={"type": "number", "truth": "verbatim"}),
            _schema(a="string"),
        ]
        for obj in bad:
            with self.subTest(obj=obj), self.assertRaises(SchemaError):
                parse_schema(obj)


class LoadSchemaTest(unittest.TestCase):
    def test_missing_and_malformed_files(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(SchemaError, "not found"):
                load_schema(Path(d) / "none.json")
            bad = Path(d) / "bad.json"
            bad.write_text("{nope", encoding="utf-8")
            with self.assertRaisesRegex(SchemaError, "invalid JSON"):
                load_schema(bad)
            good = Path(d) / "good.json"
            good.write_text(json.dumps(_schema(a={"type": "string"})), encoding="utf-8")
            self.assertEqual(load_schema(good).name, "t")


if __name__ == "__main__":
    unittest.main()
