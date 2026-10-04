import copy
import math
import unittest

from style_compiler.statistics import summarize


def row(identity, component, value, condition="HUMAN", source="web", split="TRAIN"):
    return {"schema": "style-observation/1", "id": identity, "component_id": component,
            "source": source, "condition": condition, "split": split, "profile": "synthetic/1",
            "units": {"length": "content_chars"}, "features": {"length": value}}


class StatisticsTests(unittest.TestCase):
    def test_components_are_equal_not_documents(self):
        rows = [row("a", "shared", 0), row("b", "shared", 2), row("c", "independent", 9)]
        result = summarize(rows)["partitions"]["TRAIN"]["web"]["conditions"]["HUMAN"]
        self.assertEqual(result["features"]["length"]["mean"], 5)
        self.assertEqual((result["documents"], result["components"]), (3, 2))

    def test_zero_and_missing_are_distinct(self):
        rows = [row("a", "zero", 0), row("b", "missing", None)]
        result = summarize(rows)["partitions"]["TRAIN"]["web"]["conditions"]["HUMAN"]["features"]["length"]
        self.assertEqual(result["mean"], 0)
        self.assertEqual(result["components"], 1)
        self.assertEqual(result["missing_documents"], 1)
        self.assertEqual(result["unavailable_components"], 1)
        missing = summarize([row("x", "x", None)])
        self.assertIsNone(missing["partitions"]["TRAIN"]["web"]["conditions"]["HUMAN"]["features"]["length"]["mean"])

    def test_pair_within_source_and_component_only(self):
        rows = [row("h1", "p1", 10), row("a1", "p1", 4, "CHATGPT"),
                row("h2", "p2", 100), row("a2", "different", 90, "CHATGPT"),
                row("a3", "p2", 10, "CHATGPT", "baike")]
        result = summarize(rows)["partitions"]["TRAIN"]["web"]["paired_contrasts"]["length"]
        self.assertEqual(result["paired_components"], 1)
        self.assertEqual(result["human_minus_chatgpt"], 6)
        self.assertIsNone(result["exploratory_ci95"])

    def test_order_and_seed_determinism(self):
        rows = [row("h1", "p1", 4), row("a1", "p1", 1, "CHATGPT"),
                row("h2", "p2", 6), row("a2", "p2", 2, "CHATGPT")]
        self.assertEqual(summarize(rows), summarize(list(reversed(rows))))
        result = summarize(rows)["partitions"]["TRAIN"]["web"]["paired_contrasts"]["length"]
        self.assertEqual(result["human_minus_chatgpt"], 3.5)
        self.assertIsNotNone(result["exploratory_ci95"])

    def test_cross_partition_and_test_exports_rejected(self):
        for rows in ([row("a", "same", 1), row("b", "same", 2, split="DEV")],
                     [row("a", "a", 1, split="TEST")]):
            with self.assertRaises(ValueError):
                summarize(rows)

    def test_duplicates_mismatched_profiles_units_and_invalid_numbers(self):
        original = row("a", "a", 1)
        cases = [original, row("b", "b", True), row("b", "b", math.inf), row("b", "b", math.nan)]
        for key, value in (("profile", "different"), ("units", {"length": "tokens"}),
                           ("features", {"other": 2}), ("source", "")):
            invalid = copy.deepcopy(row("b", "b", 2))
            invalid[key] = value
            cases.append(invalid)
        for invalid in cases:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                summarize([original, invalid])

    def test_negative_values_not_dropped(self):
        result = summarize([row("a", "a", -1), row("b", "b", 1)])
        self.assertEqual(result["partitions"]["TRAIN"]["web"]["conditions"]["HUMAN"]["features"]["length"]["mean"], 0)
