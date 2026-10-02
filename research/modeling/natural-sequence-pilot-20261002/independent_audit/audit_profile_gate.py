#!/usr/bin/env python3
"""Synthetic prerequisite/selection checks reconstructed after executor reset.

Imports the profile module but never calls main or reads natural record bodies.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('profile_under_test', ROOT / 'profile_natural.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)
from experimental_natural.cache_adapter import CacheDescriptor


class ProfileGate(unittest.TestCase):
    def test_frozen_component_selection_is_order_and_arm_independent(self):
        descriptors = []
        for split in ('train', 'dev', 'test'):
            for i in range(60):
                for arm in ('human', 'chatgpt'):
                    descriptors.append(CacheDescriptor('/never_open', 'a' * 64,
                        'q' + str(i), 'a' + str(i), 'c' + str(i), 'baike', split, arm, 'b' * 64))
        train = profile.choose_components(descriptors, 'train', 32)
        dev = profile.choose_components(descriptors, 'dev', 16)
        self.assertEqual(len(train), 32)
        self.assertEqual(len(dev), 16)
        self.assertEqual(train, profile.choose_components(list(reversed(descriptors)), 'train', 32))
        self.assertEqual(train, profile.choose_components([d for d in descriptors if d.arm == 'human'], 'train', 32))

    def test_prerequisites_require_every_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / 'public'
            public.mkdir()
            approval = root / 'approval.json'
            approved = {'approved': True, 'independent_review_passed': True,
                        'max_train_components': 32, 'max_dev_components': 16, 'receipt': 'synthetic'}
            full = {'arm_records': 4814}
            verified = {'records': 4814, 'verified': True,
                        'all_cache_hashes_and_annotation_fingerprints_verified': True,
                        'test_raw_bodies_read': 0, 'davinci_bodies_read': 0}
            protocol = {'cohort_manifest_sha256': profile.EXPECTED_COHORT}
            def write_all():
                approval.write_text(json.dumps(approved))
                (public / 'full_receipt.json').write_text(json.dumps(full))
                (public / 'verification_receipt.json').write_text(json.dumps(verified))
                (public / 'extraction_protocol.json').write_text(json.dumps(protocol))
            write_all()
            result = profile.prerequisites(root, approval)
            self.assertEqual(result[2], hashlib.sha256(profile.canonical(protocol)).hexdigest())
            for key, value in [('approved', False), ('independent_review_passed', False),
                               ('max_train_components', 33), ('max_dev_components', 17)]:
                original = approved[key]
                approved[key] = value
                write_all()
                with self.assertRaises(PermissionError):
                    profile.prerequisites(root, approval)
                approved[key] = original
            for key, value in [('records', 4813), ('verified', False),
                               ('all_cache_hashes_and_annotation_fingerprints_verified', False)]:
                original = verified[key]
                verified[key] = value
                write_all()
                with self.assertRaises(PermissionError):
                    profile.prerequisites(root, approval)
                verified[key] = original
            for key in ('test_raw_bodies_read', 'davinci_bodies_read'):
                verified[key] = 1
                write_all()
                with self.assertRaises(ValueError):
                    profile.prerequisites(root, approval)
                verified[key] = 0
            protocol['cohort_manifest_sha256'] = 'incorrect'
            write_all()
            with self.assertRaises(ValueError):
                profile.prerequisites(root, approval)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProfileGate))
    receipt = {'kind': 'synthetic_profile_gate_audit_after_reconstruction', 'tests_run': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors), 'success': result.wasSuccessful(),
               'natural_body_reads': 0, 'profile_executed': False,
               'source_sha256': hashlib.sha256((ROOT / 'profile_natural.py').read_bytes()).hexdigest()}
    (Path(__file__).parent / 'PROFILE_GATE_AUDIT_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))
    sys.exit(not result.wasSuccessful())
