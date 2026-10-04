"""No downloads or inference. Optional frozen-regression test reuses exact receipts."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from measure_text import diagnose, read_json, sha, verified_files, actual_runtime, SCHEMA, validate_coverage
from check_revision import check
from show_reference import load_card


class LoopTests(unittest.TestCase):
    def setUp(self):
        self.manifest = read_json(ROOT / 'references/runtime-manifest.json')
        card = load_card('web', 'reference')
        self.raw = '例子。\r\n第二行。\n'.encode()
        self.rows = {f['id']: {'value': card['card']['median'][i], 'numerator': None,
                             'denominator': 100, 'opportunities': 100, 'missing_reason': None}
                     for i, f in enumerate(card['features'])}
        self.receipt = {'schema': SCHEMA, 'status': 'MEASURED', 'source': 'web', 'band': 'reference',
                        'text_sha256': sha(self.raw), 'profile_sha256': self.manifest['measurement_profile_sha256'],
                        'reference_sha256': self.manifest['reference_sha256'], 'measurements': self.rows,
                        'coverage': {'source_sentences': 2, 'complete_target_sentences': 2,
                                     'clipped_target_sentences': 0, 'excluded_sentences': 0,
                                     'complete_parse_failures': 0, 'complete_pos_only': 0}}
        self.review = {'schema': 'statistical-writing-semantic-review/1', 'original_sha256': sha(self.raw),
                       'candidate_sha256': sha(self.raw), 'reviewer_kind': 'author_self_check',
                       'meaning_preserved': True, 'voice_preserved': True, 'unsupported_additions': False,
                       'unresolved_items': [], 'ledger': [{'id': '1', 'original_claim': 'Example content',
                                                        'candidate_evidence': 'Same content', 'verdict': 'preserved'}],
                       'dimensional_review': []}

    def test_instrument_is_byte_identical(self):
        verified_files(self.manifest)

    def test_nonfinite_and_nonnumeric_measurements_fail_closed(self):
        for invalid in (float('nan'), float('inf'), -float('inf'), True, '0.5'):
            after = copy.deepcopy(self.receipt)
            after['measurements']['zh:upos.NOUN']['value'] = invalid
            with self.assertRaisesRegex(ValueError, 'nonfinite_or_invalid_measurement'):
                diagnose(after['measurements'], 'web', 'reference')
            out = check(self.receipt, after, self.raw, self.raw, self.review)
            self.assertEqual(out['status'], 'NOT_VERIFIED')
            self.assertTrue(any('nonfinite_or_invalid_measurement' in x for x in out['blockers']))

    def test_measured_label_cannot_override_incomplete_coverage(self):
        for field, value in [('complete_parse_failures', 1), ('complete_pos_only', 1),
                             ('clipped_target_sentences', 1), ('excluded_sentences', 1),
                             ('complete_target_sentences', 1), ('source_sentences', 0)]:
            after = copy.deepcopy(self.receipt)
            after['coverage'][field] = value
            with self.assertRaisesRegex(ValueError, 'incomplete_parser_coverage'):
                validate_coverage(after['coverage'])
            out = check(self.receipt, after, self.raw, self.raw, self.review)
            self.assertEqual(out['status'], 'NOT_VERIFIED')
            self.assertIn('candidate:incomplete_parser_coverage', out['blockers'])

    def test_malformed_semantic_review_fails_closed(self):
        for review in ([], 'review', 1, True):
            out = check(self.receipt, self.receipt, self.raw, self.raw, review)
            self.assertEqual(out['status'], 'NOT_VERIFIED')
            self.assertEqual(out['blockers'], ['semantic_review_not_object'])

    def test_actual_dependency_and_python_mismatches_fail_closed(self):
        def versions(name):
            return self.manifest['package_versions'][name]
        with mock.patch('measure_text.importlib.metadata.version', side_effect=versions), mock.patch('measure_text.platform.python_version', return_value=self.manifest['python']), mock.patch('measure_text.unicodedata.unidata_version', self.manifest['unicode']):
            self.assertEqual(actual_runtime(self.manifest)['package_versions'], self.manifest['package_versions'])
        with mock.patch('measure_text.importlib.metadata.version', return_value='0.0.0'):
            with self.assertRaisesRegex(ValueError, 'dependency_version_mismatch:stanza'):
                actual_runtime(self.manifest)
        with mock.patch('measure_text.importlib.metadata.version', side_effect=versions), mock.patch('measure_text.platform.python_version', return_value='0.0.0'):
            with self.assertRaisesRegex(ValueError, 'python_version_mismatch'):
                actual_runtime(self.manifest)

    def test_missing_model_is_rejected_before_parser_load(self):
        sys.path.insert(0, str(ROOT / 'scripts/vendor'))
        from research.linguistic.stanza_local import verify_models
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'local_model_hash_mismatch:tokenize/gsdsimp.pt'):
                verify_models(temp)

    def test_diagnostics_preserve_actual_values_support_and_missing(self):
        self.rows['zh:upos.NOUN']['value'] = 0.95
        self.rows['zh:upos.VERB']['value'] = None
        out = diagnose(self.rows, 'web', 'reference')['rows']
        self.assertEqual(out[0]['value'], 0.95)
        self.assertEqual(out[0]['diagnostic_status'], 'ABOVE_Q90')
        self.assertEqual(out[0]['reference_components'], 890)
        self.assertIsNone(out[1]['value'])
        self.assertEqual(out[1]['diagnostic_status'], 'UNAVAILABLE')

    def test_range_is_not_semantic_acceptance(self):
        out = check(self.receipt, self.receipt, self.raw, self.raw, None)
        self.assertEqual(out['status'], 'NEEDS_SEMANTIC_REVIEW')

    def test_checked_workflow_and_changed_bytes(self):
        out = check(self.receipt, self.receipt, self.raw, self.raw, self.review)
        self.assertEqual(out['status'], 'MEASURED_AND_REVIEWED')
        self.assertFalse(out['semantic_review_is_automated_proof'])
        out = check(self.receipt, self.receipt, self.raw, self.raw.replace(b'\r\n', b'\n'), self.review)
        self.assertEqual(out['status'], 'NOT_VERIFIED')
        self.assertIn('candidate:text_changed_since_measurement', out['blockers'])

    def test_outlier_needs_specific_retention_reason(self):
        after = copy.deepcopy(self.receipt)
        after['measurements']['zh:upos.NOUN']['value'] = 0.8
        out = check(self.receipt, after, self.raw, self.raw, self.review)
        self.assertEqual(out['status'], 'NEEDS_REVISION_OR_REVIEW')
        review = copy.deepcopy(self.review)
        review['dimensional_review'] = [{'feature_id': 'zh:upos.NOUN',
                                         'decision': 'retain_for_meaning_or_voice',
                                         'reason': 'Required list of technical entities in the source.'}]
        out = check(self.receipt, after, self.raw, self.raw, review)
        self.assertEqual(out['status'], 'MEASURED_AND_REVIEWED')
        self.assertEqual(out['dimensions'][0]['diagnostic_status'], 'ABOVE_Q90')

    def test_no_falsepass_missing_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            inp, out = tmp / 'text.txt', tmp / 'receipt.json'
            inp.write_bytes(self.raw)
            run = subprocess.run([sys.executable, str(ROOT / 'scripts/measure_text.py'), str(inp),
                                  '--source', 'web', '--models', str(tmp / 'absent'), '--output', str(out)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            got = read_json(out)
            self.assertEqual(got['status'], 'NOT_VERIFIED')
            self.assertEqual(got['reason'], 'models_directory_missing')
            self.assertEqual(got['text_sha256'], sha(self.raw))
            self.assertEqual(inp.read_bytes(), self.raw)
            rerun = subprocess.run([sys.executable, str(ROOT / 'scripts/measure_text.py'), str(inp),
                                    '--source', 'web', '--output', str(out)], capture_output=True, text=True)
            self.assertNotEqual(rerun.returncode, 0)
            self.assertEqual(read_json(out), got)

    def test_profile_and_reference_mismatches_block_review(self):
        for key in ('profile_sha256', 'reference_sha256'):
            bad = dict(self.receipt, **{key: '0' * 64})
            self.assertEqual(check(self.receipt, bad, self.raw, self.raw, self.review)['status'], 'NOT_VERIFIED')


    def test_synthetic_frozen_receipt_reuse_without_parser(self):
        row = dict(self.receipt, id='synthetic', values={k: v['value'] for k, v in self.rows.items()},
                   parse_audit={}, measurement_status='SYNTHETIC_TEST_RECEIPT')
        receipt = {'joint_card_sha256': self.manifest['reference_sha256'], 'results': [row]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, frozen, output = root/'source.txt', root/'frozen.json', root/'out.json'
            source.write_bytes(self.raw)
            frozen.write_text(json.dumps(receipt), encoding='utf-8')
            run = subprocess.run([sys.executable, str(ROOT/'scripts/reuse_measurement.py'), str(source),
                '--receipt', str(frozen), '--receipt-sha256', sha(frozen.read_bytes()), '--id', 'synthetic',
                '--source', 'web', '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            got = read_json(output)
            self.assertEqual(got['status'], 'MEASURED_REUSED')
            self.assertFalse(got['provenance']['runtime_reexecuted'])
            self.assertEqual(got['measurements'], self.rows)
            self.assertEqual(got['instrument_measurement_status'], 'SYNTHETIC_TEST_RECEIPT')


if __name__ == '__main__':
    unittest.main()
