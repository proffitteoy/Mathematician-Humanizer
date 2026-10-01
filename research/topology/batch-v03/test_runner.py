"""Original synthetic records and injected faults only; no natural source/model run."""
import builtins
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import runner as r

CORE = Path(os.environ.get('TOPOLOGY_CORE_DIR',
    str(Path(__file__).resolve().parent.parent/'style-compiler/research/topology')))


class FakeEncoder:
    def __init__(self): self.calls = []; self.repeat_changes = False
    def encode(self, text):
        self.calls.append(text)
        if text.startswith('ENCODE_ERROR'): raise ValueError('RAW_SECRET source text must not escape')
        if text.startswith('NETWORK'):
            # Prove a backend that swallows a network exception still stops batch.
            try: socket.create_connection(('invalid.example', 443))
            except Exception: pass
        n = 20 if text.startswith('SHORT') else 60
        cloud = np.random.default_rng(int(r.digest(text.encode())[:8], 16)).normal(size=(n, 768)).astype(np.float32)
        if text.startswith('ESTIMATE_ERROR'): cloud[0, 0] = -999.
        if text.startswith('INVALID_ESTIMATE'): cloud[0, 0] = -998.
        if text.startswith('NONFINITE'): cloud[0, 0] = np.nan
        if self.repeat_changes and len(self.calls) == 2: cloud[0, 0] += 1
        full = 1000 if text.startswith('TRUNC') else n + 2
        stream = io.BytesIO(); np.save(stream, cloud, allow_pickle=False)
        meta = {'profile_sha256': r.CORE_SHA256['encoder-profile.json'],
            'source': {'utf8_sha256': r.digest(text.encode())},
            'tokenization': {'untruncated_tokens_including_specials': full,
                'input_tokens_including_specials_and_padding': n + 2,
                'retained_tokens': n, 'excluded_special_or_padding_tokens': 2,
                'truncation_configured': True, 'was_truncated': full > n + 2,
                'tokens_removed_by_truncation': full - n - 2},
            'cloud': {'shape': list(cloud.shape), 'dtype': 'float32',
                      'npy_sha256': r.digest(stream.getvalue())}}
        return cloud, meta


def fake_estimate(cloud):
    if cloud[0, 0] == -999: raise ArithmeticError('RAW_SECRET numerical failure text')
    if cloud[0, 0] == -998: return {'status': 'ok', 'dimension': math.nan, 'n_points': len(cloud)}
    if len(cloud) < 50:
        return {'status': 'unavailable', 'dimension': None, 'n_points': len(cloud),
                'reason': 'fewer_than_50_points'}
    return {'status': 'ok', 'dimension': 2.5, 'n_points': len(cloud), 'reason': None}


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.sources = self.root/'sources'; self.sources.mkdir()
        self.out = self.root/'out'; self.encoder = FakeEncoder(); self.factory_calls = 0
        self.now = 0.; self.rss = 100

    def manifest(self, texts):
        rows = []
        for i, text in enumerate(texts):
            raw = text.encode() if isinstance(text, str) else text
            name = f'RAW_SECRET-{i}.txt'; (self.sources/name).write_bytes(raw)
            rows.append({'record_id': f'RAW_SECRET_RECORD-{i}', 'relative_path': name, 'sha256': r.digest(raw)})
        return {'schema': 'topology-fixed-inputs/0.2', 'data_kind': 'synthetic_fixture', 'records': rows}

    def run_it(self, manifest, *, loader=None, **kwargs):
        def factory(path): self.factory_calls += 1; return self.encoder
        return r.run_batch(manifest=manifest, manifest_sha256=r.digest(r.encoded(manifest)),
            source_root=self.sources, model_dir=self.root/'NO_MODEL', topology_dir=self.root/'fake_core',
            out=self.out, core_loader=loader or (lambda _: (factory, fake_estimate)),
            budget_factory=lambda out, limits: r.Budget(out, limits, clock=lambda:self.now, rss=lambda:self.rss), **kwargs)

    def ledger(self): return json.loads((self.out/'ledger.private.json').read_text())

    def test_encode_and_estimate_exceptions_keep_every_record_and_continue(self):
        m = self.manifest(['ENCODE_ERROR', 'good after encode error', 'ESTIMATE_ERROR', 'good after estimate error'])
        result = self.run_it(m)
        self.assertEqual([x['status']for x in self.ledger()['records']], ['failed','ok','failed','ok'])
        self.assertEqual(result['selected_records'], 4)
        self.assertEqual(result['record_failure_reasons'], {'encode_exception':1,'estimate_exception':1})
        self.assertEqual(result['dimension_conditional_on_numerical_success']['n'], 2)
        self.assertEqual(len(self.encoder.calls), 4)  # No replacement for first repeat.
        self.assertEqual(result['repeat_status'], 'first_selected_unavailable')
        self.assertEqual(result['run_status'], 'complete_with_unavailable_records')

    def test_missing_path_missing_file_empty_whitespace_and_bad_utf8_retained(self):
        m = self.manifest(['placeholder','placeholder','placeholder','',' \n\t',b'\xff','last valid'])
        del m['records'][0]['relative_path']; m['records'][1]['relative_path']=''
        (self.sources/m['records'][2]['relative_path']).unlink()
        result = self.run_it(m)
        self.assertEqual(result['record_status_counts'], {'failed':6,'ok':1})
        self.assertEqual(result['record_failure_reasons'], {'missing_source_path':1,'empty_source_path':1,
            'missing_source':1,'empty_source':2,'invalid_utf8':1})
        self.assertEqual(len(self.encoder.calls), 1)
        self.assertEqual(result['truncation_unknown_records'], 6)

    def test_all_missing_or_empty_never_initializes_encoder(self):
        m = self.manifest(['','x']); del m['records'][1]['relative_path']
        result = self.run_it(m)
        self.assertEqual(self.factory_calls, 0)
        self.assertEqual(result['dimension_conditional_on_numerical_success'], {'n':0,'min':None,'max':None,'median':None})
        self.assertEqual(result['retained_points_range'], None)

    def test_short_cloud_is_numerical_abstention_and_remains_in_denominator(self):
        result = self.run_it(self.manifest(['SHORT original source','good']))
        self.assertEqual(result['record_status_counts'], {'unavailable':1,'ok':1})
        self.assertEqual(result['numerical_abstention_reasons'], {'fewer_than_50_points':1})
        self.assertEqual(result['selected_records'], 2)
        self.assertEqual(result['extraction_metadata_records'], 2)

    def test_real_frozen_estimator_short_cloud_without_encoder_or_model(self):
        _, estimate = r.load_core(CORE)
        result = self.run_it(self.manifest(['SHORT original source']),
                             loader=lambda _: (lambda __:self.encoder, estimate))
        self.assertEqual(result['numerical_abstention_reasons'], {'fewer_than_50_points':1})

    def test_truncation_denominators_full_source_and_prefix_are_explicit(self):
        result = self.run_it(self.manifest(['TRUNC original','normal']))
        self.assertEqual(result['truncated_records'], 1)
        self.assertEqual(result['untruncated_token_count_range'], [62,1000])
        self.assertEqual(result['retained_points_range'], [60,60])
        self.assertEqual(result['truncation_unknown_records'], 0)
        self.assertEqual(result['repeat_status'], 'exact_same_process_cloud_match')

    def test_invalid_extraction_or_estimate_does_not_create_success(self):
        result = self.run_it(self.manifest(['NONFINITE', 'INVALID_ESTIMATE', 'valid']))
        self.assertEqual(result['record_status_counts'], {'failed':2,'ok':1})
        self.assertEqual(result['record_failure_reasons'], {'invalid_extraction':1,'invalid_estimate_result':1})

    def test_source_hash_mismatch_is_global_not_local_dropout(self):
        m = self.manifest(['first good','changed','never run']); m['records'][1]['sha256']='0'*64
        result = self.run_it(m, repeat_first=False)
        self.assertEqual(result['run_status'], 'stopped');self.assertEqual(result['stop_reason'], 'source_hash_mismatch')
        self.assertEqual([x['status']for x in self.ledger()['records']], ['ok','failed','not_run'])
        self.assertEqual(len(self.encoder.calls), 1)

    def test_path_escape_is_global_stop_without_reading_target(self):
        m = self.manifest(['first','second']);m['records'][0]['relative_path']='../outside.txt'
        result = self.run_it(m)
        self.assertEqual(result['stop_reason'], 'source_path_escape')
        self.assertEqual(result['record_status_counts'], {'failed':1,'not_run':1})
        self.assertEqual(self.factory_calls, 0)

    def test_symlink_escape_is_global_stop(self):
        m = self.manifest(['first']);path=self.sources/m['records'][0]['relative_path'];path.unlink()
        outside=self.root/'outside.txt';outside.write_text('secret');path.symlink_to(outside)
        result=self.run_it(m);self.assertEqual(result['stop_reason'],'source_path_escape')

    def test_repeat_mismatch_stops_batch_without_substituting_next_source(self):
        self.encoder.repeat_changes=True
        result=self.run_it(self.manifest(['first','second']))
        self.assertEqual(result['stop_reason'],'repeat_mismatch')
        self.assertEqual(result['record_status_counts'], {'failed':1,'not_run':1})
        self.assertEqual(len(self.encoder.calls),2)

    def test_repeat_exception_is_record_local_and_following_record_runs(self):
        original=self.encoder.encode
        def encode(text):
            if len(self.encoder.calls)==1:
                self.encoder.calls.append(text);raise ValueError('repeat failed')
            return original(text)
        self.encoder.encode=encode
        result=self.run_it(self.manifest(['first','second']))
        self.assertEqual(result['record_failure_reasons'],{'repeat_encode_exception':1})
        self.assertEqual(result['record_status_counts'],{'failed':1,'ok':1})

    def test_network_even_swallowed_by_encoder_stops_all_remaining_records(self):
        result=self.run_it(self.manifest(['first good','NETWORK swallowed','last']),repeat_first=False)
        self.assertEqual(result['stop_reason'],'network_attempt')
        self.assertEqual(result['resources']['network_attempts'],1)
        self.assertEqual([x['status']for x in self.ledger()['records']],['ok','failed','not_run'])

    def test_network_guard_blocks_dns_udp_and_restores_functions(self):
        original=socket.getaddrinfo;budget=r.Budget(self.out,r.Limits(),rss=lambda:100)
        with r.offline_guard(budget):
            for function,args in [(socket.getaddrinfo,('invalid.example',443)),(socket.create_connection,(('invalid.example',443),))]:
                with self.assertRaisesRegex(r.FatalRunError,'network_attempt'):function(*args)
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM)as sock:
                with self.assertRaisesRegex(r.FatalRunError,'network_attempt'):sock.sendto(b'x',('127.0.0.1',9))
        self.assertIs(socket.getaddrinfo,original);self.assertEqual(budget.network_attempts,3)

    def test_wall_cap_preserves_previous_and_marks_active_and_unrun(self):
        original=self.encoder.encode
        def encode(text):
            out=original(text)
            if text=='timeout':self.now=1801
            return out
        self.encoder.encode=encode
        result=self.run_it(self.manifest(['good','timeout','never']),repeat_first=False)
        self.assertEqual(result['stop_reason'],'wall_cap')
        self.assertEqual([x['status']for x in self.ledger()['records']],['ok','failed','not_run'])
        self.assertTrue((self.out/'run-finished.private.json').exists())

    def test_rss_cap_is_global_and_not_reported_as_encode_failure(self):
        original=self.encoder.encode
        def encode(text):
            out=original(text);self.rss=4*1024**2;return out
        self.encoder.encode=encode
        result=self.run_it(self.manifest(['first','second']))
        self.assertEqual(result['stop_reason'],'rss_cap')
        self.assertEqual(result['record_status_counts'],{'failed':1,'not_run':1})

    def test_memory_error_is_global_stop(self):
        self.encoder.encode=lambda _:(_ for _ in ()).throw(MemoryError())
        result=self.run_it(self.manifest(['first','second']))
        self.assertEqual(result['stop_reason'],'memory_error')
        self.assertEqual(result['record_status_counts'],{'failed':1,'not_run':1})

    def test_disk_cap_has_reserved_terminal_ledger_and_no_false_success(self):
        result=self.run_it(self.manifest(['first','second']),save_clouds=True,
                          limits=r.Limits(private_bytes=180_000))
        self.assertEqual(result['stop_reason'],'private_disk_cap')
        self.assertEqual(result['record_status_counts'],{'failed':1,'not_run':1})
        self.assertEqual(result['dimension_conditional_on_numerical_success']['n'],0)
        self.assertTrue((self.out/'run-finished.private.json').exists())
        self.assertLessEqual(sum(p.stat().st_size for p in self.out.iterdir()),180_000)

    def test_default_does_not_save_clouds_optional_save_is_exact(self):
        result=self.run_it(self.manifest(['first']))
        self.assertEqual(list(self.out.glob('*.npy')),[])
        self.out=self.root/'out2'
        self.run_it(self.manifest(['second']),save_clouds=True)
        cloud=np.load(self.out/'cloud-000000.npy',allow_pickle=False)
        detail=json.loads((self.out/'result-000000.private.json').read_text())
        self.assertEqual(r.digest((self.out/'cloud-000000.npy').read_bytes()),detail['extraction']['cloud']['npy_sha256'])
        self.assertEqual(cloud.shape,(60,768))

    def test_private_result_and_ledger_commitments_match(self):
        result=self.run_it(self.manifest(['first']))
        ledger=self.ledger();row=ledger['records'][0]
        self.assertEqual(r.digest((self.out/row['private_result']['file']).read_bytes()),row['private_result']['sha256'])
        self.assertEqual(r.digest((self.out/'ledger.private.json').read_bytes()),result['private_ledger_sha256'])
        final=json.loads((self.out/'run-finished.private.json').read_text())
        self.assertEqual(r.digest((self.out/'aggregate.public.json').read_bytes()),final['aggregate_sha256'])

    def test_one_shot_directory_refuses_retry(self):
        m=self.manifest(['first']);self.run_it(m)
        with self.assertRaisesRegex(r.FatalRunError,'one_shot_output_directory_not_empty'):self.run_it(m)

    def test_public_aggregate_has_no_raw_text_ids_paths_or_exception_messages(self):
        result=self.run_it(self.manifest(['ENCODE_ERROR RAW_SECRET','good RAW_SECRET']))
        public=json.dumps(result)
        for forbidden in ['RAW_SECRET',str(self.root),'record_id','relative_path','traceback']:
            self.assertNotIn(forbidden,public)
        self.assertIn('RAW_SECRET_RECORD',json.dumps(self.ledger()))

    def test_model_initialization_failure_retains_full_selection(self):
        def fail(_):raise ValueError('model hash details RAW_SECRET')
        result=self.run_it(self.manifest(['first','second']),loader=lambda _:(fail,fake_estimate))
        self.assertEqual(result['stop_reason'],'model_initialization_failed')
        self.assertEqual(result['record_status_counts'],{'failed':1,'not_run':1})

    def test_encoder_profile_or_source_digest_mismatch_is_global(self):
        original=self.encoder.encode
        def bad(text):
            cloud,meta=original(text);meta['profile_sha256']='f'*64;return cloud,meta
        self.encoder.encode=bad
        result=self.run_it(self.manifest(['first','second']))
        self.assertEqual(result['stop_reason'],'encoder_profile_mismatch')

    def test_missing_manifest_digest_does_not_read_sources(self):
        m=self.manifest(['first']);del m['records'][0]['sha256']
        with patch.object(r,'source_text',side_effect=AssertionError('read forbidden')):
            with self.assertRaisesRegex(r.FatalRunError,'missing_or_invalid_source_digest'):self.run_it(m)

    def test_pinned_core_tamper_global_with_all_rows_not_run(self):
        def loader(_):
            core=self.root/'copiedcore';core.mkdir()
            for name in r.CORE_SHA256:(core/name).write_bytes((CORE/name).read_bytes())
            (core/'encoder.py').write_text('changed')
            return r.load_core(core)
        result=self.run_it(self.manifest(['first','second']),loader=loader)
        self.assertEqual(result['stop_reason'],'core_hash_mismatch')
        self.assertEqual(result['record_status_counts'],{'not_run':2})

    def test_missing_local_model_rejected_before_torch_or_transformers_loader(self):
        factory,_=r.load_core(CORE);original=builtins.__import__;seen=[]
        def guarded(name,*args,**kwargs):
            if name in ('torch','transformers'):
                seen.append(name);raise AssertionError('loader must not be reached')
            return original(name,*args,**kwargs)
        with patch.object(builtins,'__import__',side_effect=guarded):
            with self.assertRaisesRegex(r.FatalRunError,'model_asset_verification_failed'):
                factory(self.root/'definitely-not-a-model')
        self.assertEqual(seen,[])

    def test_source_cap_is_record_local_no_silent_truncation_of_bytes(self):
        result=self.run_it(self.manifest(['larger than cap','x']),limits=r.Limits(source_bytes=2))
        self.assertEqual(result['record_failure_reasons'],{'source_byte_cap':1})
        self.assertEqual(result['record_status_counts'],{'failed':1,'ok':1})

    def test_input_crlf_is_preserved_and_empty_hash_mismatch_is_not_empty_failure(self):
        m=self.manifest(['original\r\nsource'])
        self.run_it(m);self.assertTrue(all(x=='original\r\nsource'for x in self.encoder.calls))
        self.out=self.root/'out2';m=self.manifest(['']);m['records'][0]['sha256']='a'*64
        result=self.run_it(m);self.assertEqual(result['stop_reason'],'source_hash_mismatch')

    def test_invalid_estimator_mapping_missing_dimension_is_record_failure(self):
        result=self.run_it(self.manifest(['x']),loader=lambda _:(lambda __:self.encoder,
                            lambda x:{'status':'unavailable','n_points':len(x),'reason':'fewer_than_50_points'}))
        self.assertEqual(result['record_failure_reasons'],{'invalid_estimate_result':1})

    def test_output_io_error_does_not_claim_current_record_success(self):
        original=r.os.link
        def link(src,dst):
            if Path(dst).name.startswith('result-'):raise OSError('injected disk failure')
            return original(src,dst)
        with patch.object(r.os,'link',side_effect=link):
            result=self.run_it(self.manifest(['first','second']))
        self.assertEqual(result['stop_reason'],'output_io_failure')
        self.assertEqual(result['record_status_counts'],{'failed':1,'not_run':1})
        self.assertEqual(result['dimension_conditional_on_numerical_success']['n'],0)


if __name__=='__main__':unittest.main()
