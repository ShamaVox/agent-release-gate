import unittest

from goldengate import graders
from tests.helpers import GOOD, SCHEMA, SOURCE


def kinds(findings):
    return [(f.kind, f.field) for f in findings]


class NumbersTest(unittest.TestCase):
    def test_reads_thousands_separators_and_decimals(self):
        self.assertEqual(graders.numbers_in("$1,299.00 and 45 and 3.5 and SKU AB-12"), [1299.0, 45.0, 3.5, 12.0])

    def test_does_not_split_a_separated_number_into_parts(self):
        self.assertNotIn(1.0, graders.numbers_in("1,299"))
        self.assertNotIn(299.0, graders.numbers_in("1,299"))


class ShapeTest(unittest.TestCase):
    def test_valid_output_has_no_findings(self):
        self.assertEqual(graders.grade_shape(GOOD, SCHEMA), [])

    def test_non_object(self):
        for value in (None, [], "text", 3):
            with self.subTest(value=value):
                self.assertEqual(kinds(graders.grade_shape(value, SCHEMA)), [("shape", None)])

    def test_missing_extra_and_wrong_types(self):
        out = dict(GOOD, price="148", extra=1)
        del out["sku"]
        self.assertEqual(
            sorted(kinds(graders.grade_shape(out, SCHEMA))),
            [("shape", "extra"), ("shape", "price"), ("shape", "sku")],
        )

    def test_bools_nan_and_infinity_are_not_numbers(self):
        for value in (True, float("nan"), float("inf")):
            with self.subTest(value=value):
                self.assertEqual(kinds(graders.grade_shape(dict(GOOD, price=value), SCHEMA)), [("shape", "price")])

    def test_null_only_where_nullable_and_no_blank_strings(self):
        self.assertEqual(graders.grade_shape(dict(GOOD, color=None), SCHEMA), [])
        self.assertEqual(kinds(graders.grade_shape(dict(GOOD, sku=None), SCHEMA)), [("shape", "sku")])
        self.assertEqual(kinds(graders.grade_shape(dict(GOOD, title="  "), SCHEMA)), [("shape", "title")])


class TruthTest(unittest.TestCase):
    def test_values_traced_to_source_pass(self):
        self.assertEqual(graders.grade_truth(GOOD, SOURCE, SCHEMA), [])

    def test_verbatim_is_case_and_space_insensitive(self):
        self.assertEqual(graders.grade_truth(dict(GOOD, title="linen   WRAP dress"), SOURCE, SCHEMA), [])

    def test_invented_values_are_findings(self):
        cases = {
            "color": "Black",
            "title": "Silk Wrap Dress",
            "price": 1.0,
            "currency": "EUR",
            "size": "XL",
        }
        for name, value in cases.items():
            with self.subTest(field=name):
                self.assertEqual(kinds(graders.grade_truth(dict(GOOD, **{name: value}), SOURCE, SCHEMA)), [("truth", name)])

    def test_unknown_evidence_value(self):
        findings = graders.grade_truth(dict(GOOD, currency="JPY"), SOURCE, SCHEMA)
        self.assertIn("not an allowed value", findings[0].message)

    def test_alphabetic_evidence_matches_whole_words_only(self):
        self.assertTrue(graders._contains_token("price 10 EUR", "EUR"))
        self.assertFalse(graders._contains_token("EUROPA collection", "EUR"))

    def test_nulls_and_wrong_types_are_left_to_shape(self):
        self.assertEqual(graders.grade_truth(dict(GOOD, color=None, price="x"), SOURCE, SCHEMA), [])
        self.assertEqual(graders.grade_truth("not a dict", SOURCE, SCHEMA), [])


class CorrectnessTest(unittest.TestCase):
    def test_matches(self):
        self.assertEqual(graders.grade_correctness(dict(GOOD, title="LINEN WRAP DRESS", price=1148.004), GOOD, SCHEMA), [])
        self.assertEqual(graders.correct_field_count(GOOD, GOOD, SCHEMA), 6)

    def test_mismatches_including_null_versus_value(self):
        out = dict(GOOD, price=148.0, color=None)
        self.assertEqual(sorted(kinds(graders.grade_correctness(out, GOOD, SCHEMA))), [("mismatch", "color"), ("mismatch", "price")])
        self.assertEqual(graders.correct_field_count(out, GOOD, SCHEMA), 4)
        self.assertEqual(graders.correct_field_count(None, GOOD, SCHEMA), 0)

    def test_grade_combines_all_three(self):
        out = dict(GOOD, color="Black")
        del out["sku"]
        self.assertEqual(sorted(kinds(graders.grade(out, SOURCE, GOOD, SCHEMA))), [("mismatch", "color"), ("shape", "sku"), ("truth", "color")])


if __name__ == "__main__":
    unittest.main()
