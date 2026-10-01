import unittest
from dataclasses import replace
from style_compiler.contracts import Context
from style_compiler.leakage import Partition, connected_groups, split_documents, validate_partition
from style_compiler.model import ModelSpec, _weighted_ridge, eligibility_reasons, fit_population_model
from helpers import document


def distinct_documents():
    # Synthetic strings are deliberately lexically distinct for grouping tests.
    return [document(t, str(i)) for i, t in enumerate(['甲乙丙丁。', '乾坤天地。', '春夏秋冬。', '酸甜苦辣。'])]


class LeakageTests(unittest.TestCase):
    def test_transitive_hard_groups(self):
        a, b, c, d = distinct_documents()
        b = replace(b, leakage=replace(b.leakage, lineage_id=a.leakage.lineage_id))
        c = replace(c, leakage=replace(c.leakage, content_group_id=b.leakage.content_group_id))
        self.assertEqual(connected_groups([a, b, c, d]), [['0', '1', '2'], ['3']])

    def test_author_and_prompt_separation(self):
        a, b, c, d = distinct_documents()
        b = replace(b, provenance=replace(b.provenance, author_id=a.provenance.author_id))
        c = replace(c, leakage=replace(c.leakage, prompt_family_id=b.leakage.prompt_family_id))
        self.assertEqual(connected_groups([a, b, c, d]), [['0', '1', '2'], ['3']])

    def test_topic_not_implicitly_unioned(self):
        self.assertEqual(len(connected_groups(distinct_documents())), 4)
        self.assertEqual(len(connected_groups(distinct_documents(), ('topic',))), 1)

    def test_exact_normalized_duplicates(self):
        a = document('ＡＢＣ甲乙丙', 'a')
        b = document('ABC 甲乙丙', 'b')
        self.assertEqual(connected_groups([a, b]), [['a', 'b']])

    def test_lexical_near_duplicates(self):
        text = '春风吹过群山河流森林田野城市村庄海岸沙漠草原湖泊以及远方天空'
        a = document(text, 'a')
        b = document(text + '。', 'b')
        self.assertEqual(connected_groups([a, b]), [['a', 'b']])

    def test_infeasible_strict_split_abstains(self):
        a, b, c, d = distinct_documents()
        docs = [replace(item, leakage=replace(item.leakage, content_group_id='same')) for item in (a, b, c, d)]
        with self.assertRaisesRegex(ValueError, 'Infeasible split'):
            split_documents(docs)

    def test_partition_stable_under_input_order(self):
        docs = distinct_documents()
        self.assertEqual(split_documents(docs).assignments, split_documents(list(reversed(docs))).assignments)

    def test_forged_partition_detected(self):
        a, b, c, d = distinct_documents()
        b = replace(b, leakage=replace(b.leakage, lineage_id=a.leakage.lineage_id))
        partition = Partition('partition/1.0.0', {'0': 'train', '1': 'test', '2': 'train', '3': 'test'}, connected_groups([a, b, c, d]), ('author', 'prompt'), 'test', .85, ())
        with self.assertRaisesRegex(ValueError, 'Leakage'):
            validate_partition([a, b, c, d], partition)

    def test_partition_must_cover_exact_input(self):
        docs = distinct_documents()
        partition = split_documents(docs)
        with self.assertRaises(ValueError):
            validate_partition(docs[:3], partition)


class ModelTests(unittest.TestCase):
    def test_synthetic_provenance_is_never_empirical(self):
        reasons = eligibility_reasons(document())
        self.assertTrue(any('Synthetic' in reason for reason in reasons))

    def test_cannot_fit_without_real_data(self):
        docs = distinct_documents()
        model = fit_population_model(docs, split_documents(docs), cohort='H_G')
        self.assertEqual(model['status'], 'unavailable')
        self.assertIsNone(model['model'])
        self.assertIsNone(model['calibration'])

    def test_spoofed_cohort_does_not_override_synthetic_flag(self):
        docs = [replace(d, provenance=replace(d.provenance, cohort='H_G', assistance_status='unassisted')) for d in distinct_documents()]
        result = fit_population_model(docs, split_documents(docs), cohort='H_G')
        self.assertEqual(result['reason'], 'Ineligible training provenance')
        self.assertIsNone(result['model'])

    def test_baseline_requires_strict_axes(self):
        docs = distinct_documents()
        result = fit_population_model(docs, split_documents(docs, holdout_axes=()), cohort='H_G')
        self.assertIn('author and prompt-family', result['reason'])

    def test_bad_spec(self):
        with self.assertRaises(ValueError):
            ModelSpec(covariance_shrinkage=0)
        with self.assertRaises(ValueError):
            ModelSpec(feature_ids=('F013', 'F013'))

    def test_synthetic_numeric_ridge_algebra_only(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest('Optional NumPy not installed')
        x = np.array([[1., -1.], [1., 0.], [1., 1.]])
        y = np.array([[0.], [1.], [2.]])
        result = _weighted_ridge(x, y, [1., 1., 1.], 1.)
        self.assertAlmostEqual(result[0, 0], 1.)
        self.assertAlmostEqual(result[1, 0], 2/3)
        # This is a synthetic numerical primitive test, not a fitted corpus model.
