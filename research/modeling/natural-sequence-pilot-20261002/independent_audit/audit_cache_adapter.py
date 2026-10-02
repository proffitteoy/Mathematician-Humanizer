#!/usr/bin/env python3
"""Synthetic cache/firewall checks reconstructed after executor replacement.

No natural I/O. Prior receipts do not validate reconstructed code.
"""
import copy
import dataclasses
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import torch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
torch.set_num_threads(2)
from experimental_natural.schema import Catalog, FitAuthorization
from experimental_natural.cache_adapter import CacheDescriptor, from_cache_payload, load_train_dev_cache


def fixture():
    catalog = Catalog.from_contract()
    descriptor = CacheDescriptor('/NEVER_READ_SYNTHETIC', 'a' * 64,
        '["baike","str","synthetic"]', 'synthetic_pair', 'synthetic_component',
        'baike', 'train', 'human', 'b' * 64)
    measurements = {name: {'value': float(j + 1), 'opportunities': j + 2,
        'numerator': None, 'denominator': None, 'missing_reason': None,
        'status': 'observed', 'comparison_eligible': False}
        for j, name in enumerate(catalog.all_71_ids)}
    measurements[catalog.ids[0]].update(value=None, opportunities=None,
        missing_reason='parse_failure', status='unavailable')
    measurements[catalog.ids[1]].update(value=0., opportunities=7, status='zero_observed')
    unit = {'source_sentence_index': 0, 'source_span': [30, 37],
        catalog.ids[-2]: 7, catalog.ids[-1]: 0, 'lexical_token_count_status': 'observed',
        'lexical_token_count_missing_reason': None}
    payload = {
        'cohort': {'question_family_id': descriptor.question, 'pair_id': descriptor.answer,
            'component_id': descriptor.component, 'source': descriptor.source,
            'split': descriptor.split, 'arm': descriptor.arm},
        'protocol_sha256': descriptor.protocol_sha256,
        'history_channel_ids_audit_only': ['zh:lexical.content_overlap',
            'zh:lexical.trigram_reuse', 'zh:syntax.initial_pos_reuse'],
        'information_mode': 'supplied_complete_unit_annotation_sequence_not_certified_live_prefix',
        'structural_units': [unit], 'source_failure': None,
        'bundle': {'measurement_status': 'candidate_unvalidated',
            'empirical_model_admitted': False, 'learned_contract_compatible': False,
            'target': {'sequence': [{'source_sentence_index': 0, 'source_span': [30, 37],
                'parse_status': 'pos_only', 'parse_reason': None,
                'vector': {'channel_ids': list(catalog.all_71_ids)},
                'measurements': measurements}]}}}
    return catalog, descriptor, payload


class CacheAudit(unittest.TestCase):
    def test_exact_history_filter_and_lengths(self):
        catalog, descriptor, payload = fixture()
        record = from_cache_payload(payload, descriptor, catalog, kind='synthetic')
        self.assertEqual(record.values.shape, (1, 70))
        self.assertTrue(torch.isnan(record.values[0, 0]))
        self.assertEqual(float(record.values[0, 1]), 0.)
        for j, name in enumerate(catalog.ids[2:-2], start=2):
            self.assertEqual(float(record.values[0, j]), catalog.all_71_ids.index(name) + 1)
        self.assertEqual(record.values[0, -2:].tolist(), [7., 0.])
        self.assertTrue(torch.isnan(record.opportunity[0, -2:]).all())
        self.assertEqual(float(record.opportunity[0, 1]), 7.)
        self.assertEqual(record.measurement_audit['missing_reason_counts']['parse_failure'], 1)
        self.assertEqual(record.measurement_audit['full_exact_71_audit'], 'unchanged_private_cache')

    def test_source_failure_preserves_span_length(self):
        catalog, descriptor, payload = fixture()
        payload['source_failure'] = {'reason': 'source_resource_limit'}
        payload['bundle'] = None
        payload['structural_units'][0][catalog.ids[-1]] = None
        payload['structural_units'][0]['lexical_token_count_missing_reason'] = 'source_resource_limit'
        record = from_cache_payload(payload, descriptor, catalog, kind='synthetic')
        self.assertTrue(torch.isnan(record.values[0, :68]).all())
        self.assertEqual(float(record.values[0, 68]), 7.)
        self.assertTrue(torch.isnan(record.values[0, 69]))
        self.assertTrue(torch.isnan(record.opportunity).all())

    def test_join_cannot_silently_use_row_order(self):
        catalog, descriptor, payload = fixture()
        for key in ('question_family_id', 'component_id'):
            changed = copy.deepcopy(payload)
            changed['cohort'][key] = 'another'
            with self.assertRaises(ValueError):
                from_cache_payload(changed, descriptor, catalog, kind='synthetic')
        payload['bundle']['target']['sequence'][0]['source_span'] = [31, 38]
        with self.assertRaises(ValueError):
            from_cache_payload(payload, descriptor, catalog, kind='synthetic')

    def test_nonfinite_and_unaudited_zero_rejected(self):
        catalog, descriptor, payload = fixture()
        for value, opportunity in [(float('inf'), 7), (0., None), (0., 0)]:
            changed = copy.deepcopy(payload)
            changed['bundle']['target']['sequence'][0]['measurements'][catalog.ids[1]].update(
                value=value, opportunities=opportunity)
            with self.assertRaises(ValueError):
                from_cache_payload(changed, descriptor, catalog, kind='synthetic')

    def test_instrument_cannot_be_promoted(self):
        catalog, descriptor, payload = fixture()
        for key, value in [('measurement_status', 'validated'),
                           ('empirical_model_admitted', True),
                           ('learned_contract_compatible', True)]:
            changed = copy.deepcopy(payload)
            changed['bundle'][key] = value
            with self.assertRaises(ValueError):
                from_cache_payload(changed, descriptor, catalog, kind='synthetic')

    def test_test_davinci_denied_before_open(self):
        catalog, descriptor, _ = fixture()
        authorization = FitAuthorization(True, 'synthetic_test', ('read_train_dev_features',))
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('must not open')):
            for changes in ({'split': 'test'}, {'arm': 'davinci'}):
                with self.assertRaises(PermissionError):
                    load_train_dev_cache(dataclasses.replace(descriptor, **changes), catalog, authorization)

    def test_missing_approval_denied_before_open(self):
        catalog, descriptor, _ = fixture()
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('must not open')):
            with self.assertRaises(PermissionError):
                load_train_dev_cache(descriptor, catalog)

    def test_hash_bound_loader_preserves_natural_kind(self):
        catalog, descriptor, payload = fixture()
        authorization = FitAuthorization(True, 'synthetic_fixture', ('read_train_dev_features',))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.json.gz'
            blob = gzip.compress(json.dumps(payload).encode())
            path.write_bytes(blob)
            descriptor = dataclasses.replace(descriptor, path=str(path), sha256=hashlib.sha256(blob).hexdigest())
            record = load_train_dev_cache(descriptor, catalog, authorization)
            self.assertEqual(record.kind, 'natural')
            self.assertFalse(record.measurement_audit['comparison_eligible'])
            with self.assertRaises(ValueError):
                load_train_dev_cache(dataclasses.replace(descriptor, sha256='0' * 64), catalog, authorization)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CacheAudit))
    receipt = {'kind': 'synthetic_cache_audit_after_reconstruction', 'tests_run': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'success': result.wasSuccessful(),
        'natural_record_bodies_read': 0, 'test_or_davinci_bodies_read': 0, 'empirical_fits': 0,
        'cache_adapter_sha256': hashlib.sha256((ROOT / 'experimental_natural/cache_adapter.py').read_bytes()).hexdigest()}
    (Path(__file__).parent / 'CACHE_AUDIT_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))
    sys.exit(not result.wasSuccessful())
