import unittest
from style_compiler.planner import apply_reviewed_plan, personalize, propose_paragraph_break, semantic_guard
from helpers import document


class PlannerTests(unittest.TestCase):
    def test_candidate_deltas_are_measured_not_predicted(self):
        d = document('甲方说不。乙方可能答应。两方只讨论三次。')
        plan = propose_paragraph_break(d, max_sentences=1, protected_strings=('可能', '三次'))
        self.assertEqual(plan['status'], 'review_required')
        self.assertEqual(plan['evidence_status'], 'proposed')
        self.assertIsNone(plan['expected_feature_changes'])
        self.assertEqual(plan['checks']['semantic_equivalence'], 'unverified')
        self.assertTrue(plan['checks']['mechanical_checks_pass'])
        self.assertNotEqual(plan['measured_candidate_deltas']['F002'], 0)

    def test_review_required(self):
        d = document()
        plan = propose_paragraph_break(d, max_sentences=1)
        with self.assertRaisesRegex(ValueError, 'review is required'):
            apply_reviewed_plan(d, plan, semantic_review_approved=False)

    def test_reviewed_apply_and_rollback(self):
        d = document()
        plan = propose_paragraph_break(d, max_sentences=1)
        result = apply_reviewed_plan(d, plan, semantic_review_approved=True)
        self.assertEqual(result, plan['candidate'])
        self.assertEqual(result.replace('\n', ''), d.text)

    def test_stale_source(self):
        d = document()
        plan = propose_paragraph_break(d, max_sentences=1)
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            apply_reviewed_plan(document('已经变化。'), plan, semantic_review_approved=True)

    def test_candidate_tampering(self):
        d = document()
        plan = propose_paragraph_break(d, max_sentences=1)
        plan['candidate'] += '假事实。'
        with self.assertRaisesRegex(ValueError, 'Candidate changed'):
            apply_reviewed_plan(d, plan, semantic_review_approved=True)

    def test_quote_boundary_abstains(self):
        d = document('他说：“首先检查。随后讨论。”之后结束。')
        self.assertEqual(propose_paragraph_break(d, max_sentences=1)['status'], 'abstained')

    def test_locked_span_abstains(self):
        d = document('甲方不答应。乙方等待。')
        self.assertEqual(propose_paragraph_break(d, max_sentences=1, protected_strings=('答应。乙方',))['status'], 'abstained')

    def test_empty_no_change(self):
        self.assertEqual(propose_paragraph_break(document(''), max_sentences=1)['status'], 'no_change')

    def test_no_default_human_target(self):
        with self.assertRaises(TypeError):
            propose_paragraph_break(document())

    def test_fact_guard_cannot_certify_semantics(self):
        checks = semantic_guard('约三人', '三人')
        self.assertFalse(checks['mechanical_checks_pass'])
        self.assertEqual(checks['semantic_equivalence'], 'unverified')

    def test_personalization_cannot_run(self):
        with self.assertRaises(NotImplementedError):
            personalize()
