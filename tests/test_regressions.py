"""Synthetic-only regressions discovered by independent implementation review."""
import json
import math
from pathlib import Path
import unittest
from dataclasses import replace
from style_compiler.contracts import Document
from style_compiler.features import extract
from style_compiler.leakage import split_documents, validate_partition
from style_compiler.model import ModelSpec, _quadratic_residual, assess
from style_compiler.planner import propose_paragraph_break, apply_reviewed_plan
from helpers import document
from test_leakage_model import distinct_documents


class ReviewRegressions(unittest.TestCase):
    def test_nonobject_document_is_clean_error(self):
        for value in ([], None, 4, 'text'):
            with self.assertRaises(ValueError):
                Document.from_dict(value)

    def test_partition_schema_and_components_verified(self):
        docs = distinct_documents()
        partition = split_documents(docs)
        for invalid in (replace(partition, schema_version='bogus'), replace(partition, groups=[['nonexistent']])):
            with self.assertRaises(ValueError):
                validate_partition(docs, invalid)

    def test_support_thresholds_are_finite_integers(self):
        for invalid in (math.nan, math.inf, 3.2, True, '12'):
            with self.assertRaises(ValueError):
                ModelSpec(min_independent_groups=invalid)

    def test_multiline_quote_abstains(self):
        d = document('他说：“第一句。\n第二句。第三句。”之后结束。')
        self.assertEqual(propose_paragraph_break(d, max_sentences=1)['status'], 'abstained')

    def test_repeated_lock_checked(self):
        d = document('甲。乙。甲。乙。')
        result = propose_paragraph_break(d, max_sentences=3, protected_strings=('甲。乙',))
        self.assertEqual(result['status'], 'abstained')

    def test_coordinated_plan_change_rejected(self):
        from style_compiler.contracts import text_hash
        d = document('他离开。她说：“第一点。第二点。”最后结束。')
        plan = propose_paragraph_break(d, max_sentences=1)
        offset = d.text.index('第一点。') + len('第一点。')
        plan['edit']['offset'] = offset
        plan['candidate'] = d.text[:offset] + '\n' + d.text[offset:]
        plan['candidate_sha256'] = text_hash(plan['candidate'])
        with self.assertRaises(ValueError):
            apply_reviewed_plan(d, plan, semantic_review_approved=True)

    def test_numeric_quadratic_form_checks(self):
        try:
            import numpy
        except ImportError:
            self.skipTest('Optional NumPy absent')
        self.assertEqual(_quadratic_residual([1., 2.], [[1., 0.], [0., 1.]]), 5.)
        for residual, covariance in (([math.nan], [[1.]]), ([1.], [[0.]]), ([1.], [[math.inf]]), ([1., 2.], [[1., 1.], [0., 1.]])):
            with self.assertRaises(ValueError):
                _quadratic_residual(residual, covariance)

    def test_bad_model_version_cannot_score(self):
        result = assess(extract(document()), {'status':'fitted_experimental', 'model':{}})
        self.assertIsNone(result['distance_squared'])
        self.assertIn('version', result['reason'])


class SchemaTests(unittest.TestCase):
    def setUp(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest('Optional jsonschema absent')
        self.validate = jsonschema.validate
        self.root = Path(__file__).resolve().parents[1] / 'schemas'

    def test_document_schema(self):
        schema = json.loads((self.root / 'document.schema.json').read_text())
        self.validate(document().to_dict(), schema)

    def test_bundle_schema_for_observed_and_missing(self):
        schema = json.loads((self.root / 'measurement-bundle.schema.json').read_text())
        for text in ('', '甲。', '甲。甲甲。甲甲甲。甲甲甲甲。'):
            self.validate(extract(document(text)), schema)

class RegistryAndGroupingTests(unittest.TestCase):
    def test_cohort_selection_keeps_cross_cohort_bridges(self):
        from style_compiler.model import _intersect_components
        from style_compiler.leakage import connected_groups
        a, b, c, d = distinct_documents()
        b = replace(b, provenance=replace(b.provenance, cohort='A_G'),
                    leakage=replace(b.leakage, lineage_id=a.leakage.lineage_id))
        c = replace(c, leakage=replace(c.leakage, content_group_id=b.leakage.content_group_id))
        full = connected_groups([a, b, c, d])
        self.assertEqual(_intersect_components(full, {'0','2','3'}), [['0','2'], ['3']])

    def test_candidate_registry_is_not_a_completed_model(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads((root / 'docs/design/feature-schema-100.zh.json').read_text())
        features = registry['features']
        self.assertEqual(len(features), 100)
        self.assertEqual(len({f['id'] for f in features}), 100)
        self.assertFalse(registry['reference_distributions_fitted'])
        self.assertTrue(all(f['validated'] is False for f in features))
