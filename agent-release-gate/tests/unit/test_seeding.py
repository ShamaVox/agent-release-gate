import unittest

from goldengate import graders, seeding
from goldengate.cases import Case
from tests.helpers import GOOD, SCHEMA, SOURCE

CASE = Case(id="c1", input=SOURCE, expected=GOOD)


class SeedingTest(unittest.TestCase):
    def test_every_mutation_is_a_failing_output(self):
        muts = seeding.mutations_for(CASE, GOOD, SCHEMA)
        # per field: dropped, wrong type, changed (+ lost to null when nullable); plus one extra field
        self.assertEqual(len(muts), 6 * 3 + 2 + 1)
        for m in muts:
            with self.subTest(label=m.label):
                self.assertTrue(graders.grade(m.output, SOURCE, GOOD, SCHEMA))

    def test_null_fields_get_an_invented_value(self):
        expected = dict(GOOD, color=None)
        labels = [m.label for m in seeding.mutations_for(Case("c", SOURCE, expected), expected, SCHEMA)]
        self.assertIn("color: invented where the source has none", labels)

    def test_mutations_do_not_touch_the_original(self):
        original = dict(GOOD)
        seeding.mutations_for(CASE, original, SCHEMA)
        self.assertEqual(original, GOOD)

    def test_seed_skips_failing_cases_and_counts_escapes(self):
        result = seeding.seed([CASE, Case("c2", SOURCE, GOOD)], {"c1": GOOD, "c2": dict(GOOD, price=1.0)}, SCHEMA)
        self.assertEqual(result.skipped_cases, ("c2",))
        self.assertEqual((result.total, result.caught, result.escaped), (21, 21, ()))


if __name__ == "__main__":
    unittest.main()
