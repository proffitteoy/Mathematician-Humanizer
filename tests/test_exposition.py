import copy
import json
from pathlib import Path
import unittest

from math_reader.document import parse_document
from math_reader.graph import reconstruct
from math_exposition.prompts import PROMPTS
from math_exposition.workflow import audit_exposition, prepare_stage, statistical_feedback
from style_compiler.contracts import text_hash
from test_math_reader import PAPER, anchor, annotations


ROOT = Path(__file__).resolve().parents[1]
DRAFT = "先在像空间中寻找最优拟合向量。正交投影保证它唯一。再求这个向量的全部原像，系数的自由度来自核。"


def review(document, candidate=DRAFT):
    return {"document_id": document["document_id"], "candidate_sha256": text_hash(candidate),
            "reconstruction_sha256": reconstruct(document, annotations(document))["reconstruction_sha256"],
            "checks": [{"id": key, "status": "pass", "start": 0, "end": len(candidate), "quote": candidate,
                        "reason": "Synthetic fixture assessment, not an expert review", "evidence": [anchor(document)]}
                       for key in ("hypotheses", "dependencies", "mechanisms", "attribution", "scope")]}


class ExpositionTests(unittest.TestCase):
    def setUp(self):
        self.doc = parse_document(PAPER)
        self.data = annotations(self.doc)

    def test_reader_knowledge_changes_explanation_not_mathematics(self):
        task = prepare_stage("exposition", self.doc, self.data, known_nodes=["n1"])
        self.assertNotIn("n1", task["explanation_order"])
        self.assertIn("n1", task["reconstruction"]["prerequisite_order"])
        with self.assertRaises(ValueError):
            prepare_stage("exposition", self.doc, self.data, known_nodes=["unknown"])

    def test_motivation_receives_gaps_but_exposition_is_gated(self):
        self.data["coverage"]["n4"]["status"] = "gap"
        self.assertTrue(prepare_stage("motivation", self.doc, self.data)["reconstruction"]["findings"])
        with self.assertRaises(ValueError):
            prepare_stage("exposition", self.doc, self.data)

    def test_initial_literature_precedes_graph_and_later_visits_receive_gaps(self):
        initial = prepare_stage("literature", self.doc)
        self.assertEqual(initial["document_id"], self.doc["document_id"])
        self.assertTrue(initial["source_index"])
        self.assertNotIn("reconstruction", initial)
        self.data["coverage"]["n4"]["status"] = "gap"
        later = prepare_stage("literature", self.doc, self.data)
        self.assertTrue(later["reconstruction"]["findings"])
        wrong = dict(self.data, document_id="another-source")
        with self.assertRaises(ValueError):
            prepare_stage("literature", self.doc, wrong)

    def test_measured_statistics_bind_exact_text_and_locations(self):
        result = statistical_feedback(DRAFT, research=ROOT / "research", reference_source="web")
        self.assertEqual(result["measurement"]["text_sha256"], text_hash(DRAFT))
        self.assertEqual(len(result["measurement"]["features"]), 8)
        self.assertTrue(result["comparisons"])
        self.assertTrue(all(c["outside_descriptive_band"] is None for c in result["comparisons"]))
        for span in result["review_locations"]:
            self.assertTrue(DRAFT[span["start"]:span["end"]])

    def test_english_does_not_receive_chinese_thresholds(self):
        result = statistical_feedback("A mathematical explanation.", language="en")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["comparisons"], [])
        self.assertIn("presentation", result)

    def test_presentation_review_is_separate_from_permission_to_revise(self):
        candidate = DRAFT + '\n$$a=b$$\n$$c=d$$\n$$e=f$$\n$$g=h$$'
        result = audit_exposition(self.doc, self.data, candidate, candidate, review=review(self.doc, candidate))
        self.assertTrue(result["editorial_revision_allowed"])
        self.assertTrue(result["presentation_review_required"])
        self.assertEqual(result["statistics"]["presentation"]["display_math_blocks"], 4)
        task = prepare_stage("editorial", self.doc, self.data, baseline=candidate, candidate=candidate, audit=result)
        self.assertEqual(task["presentation_policy"]["max_display_math_blocks"], 3)
        self.assertTrue(task["measured_feedback"]["presentation"]["over_display_math_limit"])

    def test_no_review_no_polishing_even_if_protection_passes(self):
        result = audit_exposition(self.doc, self.data, DRAFT, DRAFT)
        self.assertFalse(result["editorial_revision_allowed"])
        self.assertFalse(result["content_protection"]["blockers"])
        self.assertEqual(result["statistics"]["status"], "measured")

    def test_current_review_and_measurements_prepare_editorial_task(self):
        result = audit_exposition(self.doc, self.data, DRAFT, DRAFT, review=review(self.doc))
        self.assertTrue(result["editorial_revision_allowed"])
        task = prepare_stage("editorial", self.doc, self.data, baseline=DRAFT, candidate=DRAFT, audit=result)
        self.assertEqual(task["measured_feedback"]["measurement"], result["statistics"]["measurement"])

    def test_selected_reference_is_rechecked_and_preserved(self):
        result = audit_exposition(self.doc, self.data, DRAFT, DRAFT, review=review(self.doc),
                                  research=ROOT / "research", reference_source="web")
        task = prepare_stage("editorial", self.doc, self.data, baseline=DRAFT, candidate=DRAFT,
                             audit=result, research=ROOT / "research")
        self.assertEqual(task["measured_feedback"], result["statistics"])
        result["statistics"]["comparisons"][0]["q10"] = -99
        with self.assertRaises(ValueError):
            prepare_stage("editorial", self.doc, self.data, baseline=DRAFT, candidate=DRAFT,
                          audit=result, research=ROOT / "research")

    def test_stale_or_forged_review_statistics_rejected(self):
        result = audit_exposition(self.doc, self.data, DRAFT, DRAFT, review=review(self.doc))
        for field in ("candidate_sha256", "statistics"):
            changed = copy.deepcopy(result)
            if field == "statistics":
                changed[field]["measurement"]["features"]["F013"]["value"] = 999
            else:
                changed[field] = "old-draft"
            with self.subTest(field=field), self.assertRaises(ValueError):
                prepare_stage("editorial", self.doc, self.data, baseline=DRAFT, candidate=DRAFT, audit=changed)
        with self.assertRaisesRegex(ValueError, "does not belong"):
            audit_exposition(self.doc, self.data, DRAFT, DRAFT + "改稿。", review=review(self.doc))

    def test_changed_proof_role_invalidates_old_mathematical_review(self):
        assessment = review(self.doc)
        self.data["edges"][0]["role"] = "A different interpretation of this dependency"
        with self.assertRaisesRegex(ValueError, "stale"):
            audit_exposition(self.doc, self.data, DRAFT, DRAFT, review=assessment)

    def test_failed_check_and_changed_formula_stop_polishing(self):
        assessment = review(self.doc)
        assessment["checks"][0]["status"] = "fail"
        self.assertFalse(audit_exposition(self.doc, self.data, DRAFT, DRAFT, review=assessment)["editorial_revision_allowed"])
        candidate = DRAFT + "$x=2$"
        result = audit_exposition(self.doc, self.data, DRAFT + "$x=1$", candidate, review=review(self.doc, candidate))
        self.assertTrue(result["content_protection"]["blockers"])
        self.assertFalse(result["editorial_revision_allowed"])

    def test_review_needs_source_evidence_and_all_categories(self):
        assessment = review(self.doc)
        assessment["checks"][0]["evidence"][0]["quote"] = "fabricated"
        with self.assertRaises(ValueError):
            audit_exposition(self.doc, self.data, DRAFT, DRAFT, review=assessment)
        assessment = review(self.doc)
        assessment["checks"].pop()
        with self.assertRaises(ValueError):
            audit_exposition(self.doc, self.data, DRAFT, DRAFT, review=assessment)

    def test_preparation_is_json_serializable_and_stage_specific(self):
        for stage in PROMPTS:
            kwargs = {}
            if stage == "editorial":
                kwargs["audit"] = audit_exposition(self.doc, self.data, DRAFT, DRAFT, review=review(self.doc))
            task = prepare_stage(stage, self.doc, self.data, baseline=DRAFT, candidate=DRAFT, **kwargs)
            json.dumps(task, allow_nan=False)
            self.assertEqual(task["instruction"], PROMPTS[stage])
