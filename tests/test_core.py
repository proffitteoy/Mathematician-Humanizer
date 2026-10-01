import json
import math
import unittest
from dataclasses import replace
from style_compiler.contracts import Document, Measurement, Provenance
from style_compiler.features import extract, lag1_spearman, quantile, ranks
from style_compiler.segmentation import content_chars, segment
from helpers import document


class ContractTests(unittest.TestCase):
    def test_roundtrip(self):
        original = document()
        self.assertEqual(Document.from_dict(original.to_dict()), original)

    def test_explicit_version(self):
        raw = document().to_dict()
        del raw["schema_version"]
        with self.assertRaises(ValueError):
            Document.from_dict(raw)

    def test_unknown_fields(self):
        with self.assertRaises(ValueError):
            Document.from_dict(document().to_dict() | {"magic": True})

    def test_personalization_is_disabled(self):
        for cohort in ("H_U", "A_U"):
            with self.assertRaisesRegex(ValueError, "Personalization is disabled"):
                document(provenance=replace(document().provenance, cohort=cohort))

    def test_invalid_boolean_not_truthy(self):
        with self.assertRaises(ValueError):
            replace(document().provenance, rights_verified="yes")

    def test_missing_value_requires_reason(self):
        with self.assertRaises(ValueError):
            Measurement("F000", None, "x", "document", 0, "unavailable", None, False, None)

    def test_finite_values(self):
        with self.assertRaises(ValueError):
            Measurement("F000", math.nan, "x", "document", 1, "observed", None, True, None)


class SegmentationTests(unittest.TestCase):
    def test_offsets_crlf_quotes(self):
        text = '  他说：“可以。”随后离开！\r\n\r\n另一人留下。 '
        paragraphs, sentences = segment(text)
        self.assertEqual(len(paragraphs), 2)
        self.assertEqual([text[s.start:s.end] for s in sentences], ['他说：“可以。”', '随后离开！', '另一人留下。'])
        self.assertEqual([s.paragraph_index for s in sentences], [0, 0, 1])
        self.assertEqual(sum(s.content_chars for s in sentences), content_chars(text))

    def test_character_projection(self):
        self.assertEqual(content_chars('甲Aé９3🙂 +!?\t'), 5)
        self.assertEqual(content_chars('e\u0301'), 1)  # not grapheme normalization

    def test_decimal_is_not_sentence_boundary(self):
        p, s = segment('The value is 3.14. Another estimate is 9.2.')
        self.assertEqual(len(s), 2)

    def test_empty_punctuation(self):
        self.assertEqual(segment(' \n!?。\r\n🙂'), ([], []))

    def test_each_nonempty_line_is_a_paragraph(self):
        p, s = segment('甲乙\n丙丁\n\n戊己')
        self.assertEqual(len(p), 3)
        self.assertEqual(len(s), 3)


class FeatureTests(unittest.TestCase):
    def test_quantiles_and_tied_ranks(self):
        self.assertEqual(quantile([1, 3, 9, 11], .25), 2.5)
        self.assertEqual(ranks([4, 2, 4]), [2.5, 1., 2.5])

    def test_synthetic_known_lengths(self):
        b = extract(document('甲。甲甲。甲甲甲。甲甲甲甲。'))
        f = b['features']
        self.assertEqual([s['content_chars'] for s in b['sentences']], [1, 2, 3, 4])
        self.assertEqual(f['F013']['value'], 2.5)
        self.assertEqual(f['F014']['value'], 1.5)
        self.assertAlmostEqual(f['F015']['value'], 3.7)
        self.assertAlmostEqual(f['F016']['value'], .4)
        self.assertAlmostEqual(f['F024']['value'], .4)
        self.assertAlmostEqual(f['F025']['value'], 1.)
        self.assertFalse(f['F025']['eligible_for_comparison'])

    def test_sequence_order_not_bag(self):
        increasing = extract(document('甲。甲甲。甲甲甲。甲甲甲甲。'))
        zigzag = extract(document('甲。甲甲甲甲。甲甲。甲甲甲。'))
        self.assertEqual(increasing['features']['F013']['value'], zigzag['features']['F013']['value'])
        self.assertNotEqual(increasing['features']['F025']['value'], zigzag['features']['F025']['value'])

    def test_lag1_null_is_not_zero(self):
        self.assertIsNone(lag1_spearman([1., 2., 3.]))
        self.assertIsNone(lag1_spearman([4.] * 30))
        b = extract(document('甲乙。甲乙。甲乙。甲乙。'))
        self.assertIsNone(b['features']['F025']['value'])
        self.assertEqual(b['features']['F016']['status'], 'zero_observed')

    def test_empty_has_no_fake_zeros(self):
        b = extract(document(''))
        self.assertTrue(all(f['value'] is None for f in b['features'].values()))
        self.assertIsNone(b['reference_statistics'])
        self.assertTrue(all(f['value'] is None for f in b['optional_capabilities'].values()))

    def test_provisional_support_gates(self):
        sentence = '这是用于验证测量实现的合成文本不代表真实研究结果。'
        b = extract(document(sentence * 12))
        self.assertTrue(b['features']['F013']['eligible_for_comparison'])
        self.assertFalse(b['features']['F015']['eligible_for_comparison'])
        self.assertFalse(b['features']['F024']['eligible_for_comparison'])

    def test_deterministic_and_json_finite(self):
        d = document()
        self.assertEqual(extract(d), extract(d))
        json.dumps(extract(d), allow_nan=False)
