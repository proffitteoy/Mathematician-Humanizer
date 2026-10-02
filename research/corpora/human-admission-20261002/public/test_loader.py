"""Synthetic contract regressions. No source prose, model fitting or network."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from loader import (OPERATIONAL_POLICY, STRICT_POLICY, admission_reasons,
                    checked_file, source_units, sha256, validate_record)
from loader import require_analysis_boundary, load_registry
from build_admission import verify_reviewed_catalogs, APPROVED_CATALOGS


def fixture_record():
    return {"schema_version": "human-corpus-record/1.0.0", "document_id": "synthetic-intake-test",
            "admission": {"status": "admitted", "cohort": "H_G", "single_author_cohort_eligible": True},
            "analysis_assignment": {"experiment_id": None, "split": None, "fit_authorized": False},
            "human_origin_evidence": {"assessment": "supported_by_human_byline_and_publishing_source",
                                      "byline_verified": True, "source_verified": True,
                                      "evidence_urls": ["https://example.invalid/synthetic-fixture"]},
            "assistance_status": "unknown",
            "author_unit": {"kind": "single_byline", "members": [{"author_id": "fixture-author"}],
                            "individual_author_id": "fixture-author"},
            "rights": {"evidence_reviewed": True, "evidence_urls": ["https://example.invalid/fixture-rights"],
                       "raw_text_publication_allowed": False},
            "source": {"canonical_url": "https://example.invalid/synthetic-fixture"},
            "genre": "synthetic", "content": {"structure_format": "html_leaf_blocks/1.0.0"},
            "dates": {"publication_date_claim": "2026-10-02", "historical_snapshot_status": "not_verified"}}


class IntakeTests(unittest.TestCase):
    def test_duplicate_identity_and_exact_body_collisions_rejected(self):
        for collision in ("document_id", "canonical_url", "body_hash"):
            a = fixture_record()
            b = copy.deepcopy(a)
            b["document_id"] = "synthetic-other"
            b["source"]["canonical_url"] += "/other"
            a["content"]["body_text"] = {"path": "a", "sha256": sha256(b"synthetic one"), "bytes": 13}
            b["content"]["body_text"] = {"path": "b", "sha256": sha256(b"synthetic two"), "bytes": 13}
            if collision == "document_id":
                b["document_id"] = a["document_id"]
            elif collision == "canonical_url":
                b["source"]["canonical_url"] = a["source"]["canonical_url"]
            else:
                b["content"]["body_text"]["sha256"] = a["content"]["body_text"]["sha256"]
            with tempfile.TemporaryDirectory() as temp:
                data = (json.dumps(a) + "\n" + json.dumps(b) + "\n").encode()
                (Path(temp) / "catalog.jsonl").write_bytes(data)
                registry = {"schema_version": "human-corpus-registry/1.0.0", "catalog": {"path": "catalog.jsonl", "bytes": len(data), "sha256": sha256(data)}}
                path = Path(temp) / "registry.json"
                path.write_text(json.dumps(registry))
                with self.assertRaisesRegex(ValueError, "Duplicate"):
                    load_registry(path)

    def test_reviewed_release_cannot_admit_changed_catalogs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "public"
            root.mkdir()
            for name in APPROVED_CATALOGS:
                (root / name).write_text("{}\n")
            with self.assertRaises(ValueError):
                verify_reviewed_catalogs(temp)

    def test_physical_line_paragraph_consumer_not_silently_supported(self):
        for mode in ("source_units", "full_text_character_only"):
            require_analysis_boundary(mode)
        for mode in ("physical_lines", "punctuation-lines/1.0.0"):
            with self.assertRaises(ValueError):
                require_analysis_boundary(mode)

    def test_unknown_assistance_admitted_operationally(self):
        self.assertEqual(admission_reasons(fixture_record()), [])

    def test_strict_estimand_is_separate_optional_filter(self):
        r = fixture_record()
        self.assertTrue(admission_reasons(r, policy=STRICT_POLICY))
        r["assistance_status"] = "unassisted"
        self.assertEqual(admission_reasons(r, policy=STRICT_POLICY), [])

    def test_dates_missing_recent_and_old_are_not_admission_gates(self):
        for date in (None, "2026-10-02", "2030-01-01", "1900-01-01"):
            r = fixture_record()
            r["dates"]["publication_date_claim"] = date
            self.assertEqual(admission_reasons(r), [])

    def test_absent_human_byline_evidence_is_rejected(self):
        r = fixture_record()
        r["human_origin_evidence"]["byline_verified"] = False
        with self.assertRaises(ValueError):
            admission_reasons(r)

    def test_coauthor_general_included_individual_excluded(self):
        r = fixture_record()
        r["author_unit"].update(kind="coauthored", individual_author_id=None)
        r["author_unit"]["members"].append({"author_id": "fixture-author-two"})
        r["admission"]["single_author_cohort_eligible"] = False
        self.assertEqual(admission_reasons(r), [])
        self.assertTrue(admission_reasons(r, cohort="single_author"))

    def test_coauthor_cannot_masquerade_as_index_author(self):
        r = fixture_record()
        r["author_unit"]["kind"] = "coauthored"
        r["author_unit"]["members"].append({"author_id": "fixture-author-two"})
        r["admission"]["single_author_cohort_eligible"] = False
        with self.assertRaises(ValueError):
            admission_reasons(r)

    def test_no_implicit_experiment_assignment_or_fit(self):
        for key, value in (("experiment_id", "m4"), ("split", "train"), ("fit_authorized", True)):
            r = fixture_record()
            r["analysis_assignment"][key] = value
            with self.assertRaises(ValueError):
                validate_record(r)

    def test_source_blocks_are_not_reflowed_or_missing_gap_prose(self):
        r = fixture_record()
        text = "甲\n乙甲丙長段落不拆分丁"
        blocks = [{"role": "paragraph_element_mixed", "source_tag": "p", "text": "甲"},
                  {"role": "marked_quotation", "source_tag": "p", "text": "甲"},
                  {"role": "division_element_mixed", "source_tag": "div", "text": "長段落不拆分"}]
        units = source_units(r, text, blocks)
        self.assertEqual("".join(u["text"] for u in units), text)
        self.assertEqual([u["source_block_index"] for u in units if u["source_block_index"] is not None], [0, 1, 2])
        self.assertEqual(sum(u["role"] == "marked_quotation" for u in units), 1)
        self.assertEqual(sum(u["role"] == "unmapped_source_text" for u in units), 3)

    def test_block_order_mismatch_is_rejected(self):
        blocks = [{"role": "paragraph_element_mixed", "source_tag": "p", "text": s} for s in ["乙", "甲"]]
        with self.assertRaises(ValueError):
            source_units(fixture_record(), "甲乙", blocks)

    def test_draftjs_native_keys_roles_and_whitespace_survive(self):
        r = fixture_record()
        r["content"]["structure_format"] = "draftjs/1.0.0"
        blocks = [{"key": "a", "type": "unstyled", "text": "甲", "entityRanges": []},
                  {"key": "b", "type": "atomic", "text": " ", "entityRanges": [{"key": 0, "offset": 0, "length": 1}]},
                  {"key": "c", "type": "header-two", "text": "乙", "entityRanges": []}]
        text = "甲\n\n \n\n乙"
        units = source_units(r, text, {"blocks": blocks, "entityMap": {}})
        native = [u for u in units if u["source_block_index"] is not None]
        self.assertEqual([u["source_key"] for u in native], ["a", "b", "c"])
        self.assertEqual([u["role"] for u in native], ["paragraph_element_mixed", "atomic_entity", "heading"])
        self.assertEqual("".join(u["text"] for u in units), text)

    def test_checksum_and_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "fixture.txt"
            p.write_bytes(b"synthetic")
            ref = {"path": p.name, "bytes": 9, "sha256": sha256(b"synthetic")}
            self.assertEqual(checked_file(temp, ref), b"synthetic")
            p.write_bytes(b"tampered!")
            with self.assertRaises(ValueError):
                checked_file(temp, ref)
            ref["path"] = "../fixture.txt"
            with self.assertRaises(ValueError):
                checked_file(temp, ref)

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as outer:
            root = Path(outer) / "cache"
            root.mkdir()
            outside = Path(outer) / "outside.txt"
            outside.write_bytes(b"synthetic")
            (root / "link").symlink_to(outside)
            with self.assertRaises(ValueError):
                checked_file(root, {"path": "link", "bytes": 9, "sha256": sha256(b"synthetic")})

    def test_unknown_policy_or_cohort_rejected(self):
        for kwargs in ({"policy": "typo"}, {"cohort": "train"}):
            with self.assertRaises(ValueError):
                admission_reasons(fixture_record(), **kwargs)


if __name__ == "__main__":
    unittest.main()
