"""Independent synthetic-only fault probes; no natural source/model execution."""
import importlib.util
import json
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

DRAFT = pathlib.Path(__file__).resolve().parent
CORE = pathlib.Path('/workspace/shared/style-compiler/research/topology')
sys.path.insert(0, str(DRAFT))
import runner as r
from test_runner import FakeEncoder, fake_estimate


class IndependentFaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.sources = self.root/'synthetic-sources'; self.sources.mkdir()
        self.out = self.root/'fresh-output'
        self.enc = FakeEncoder()
        self.manifest = {'schema':'topology-fixed-inputs/0.2', 'data_kind':'synthetic_fixture', 'records':[]}
        for i in range(3):
            name = f'synthetic-{i}.txt'; raw = f'original synthetic text {i}'.encode()
            (self.sources/name).write_bytes(raw)
            self.manifest['records'].append({'record_id':f'case-{i}', 'relative_path':name, 'sha256':r.digest(raw)})

    def run_fixture(self, **kwargs):
        return r.run_batch(manifest=self.manifest, manifest_sha256=r.digest(r.encoded(self.manifest)),
            source_root=self.sources, model_dir=self.root/'nonexistent-model',
            topology_dir=self.root/'synthetic-core', out=self.out,
            core_loader=lambda _:(lambda _:self.enc, fake_estimate),
            budget_factory=lambda out,limits:r.Budget(out,limits,clock=lambda:0.,rss=lambda:100),
            **kwargs)

    def rows(self):
        return json.loads((self.out/'ledger.private.json').read_text())['records']

    def test_second_result_write_failure_preserves_only_previous_success(self):
        original = r.os.link
        def injected(src,dst):
            if pathlib.Path(dst).name == 'result-000001.private.json': raise OSError('synthetic')
            return original(src,dst)
        with patch.object(r.os,'link',side_effect=injected): report=self.run_fixture()
        self.assertEqual(report['stop_reason'],'output_io_failure')
        self.assertEqual([x['status'] for x in self.rows()],['ok','failed','not_run'])
        self.assertEqual(report['dimension_conditional_on_numerical_success']['n'],1)
        self.assertTrue(report['partial_numeric_diagnostics_only'])
        self.assertTrue((self.out/'run-finished.private.json').exists())

    def test_post_result_ledger_failure_does_not_keep_current_success(self):
        original = r.os.replace; hit=False
        def injected(src,dst):
            nonlocal hit
            if pathlib.Path(dst).name=='ledger.private.json' and not hit:
                data=json.loads(pathlib.Path(src).read_text())
                if data['records'][0]['status']=='ok':
                    hit=True; raise OSError('synthetic ledger error')
            return original(src,dst)
        with patch.object(r.os,'replace',side_effect=injected):report=self.run_fixture()
        self.assertTrue(hit)
        self.assertEqual([x['status'] for x in self.rows()],['failed','not_run','not_run'])
        self.assertEqual(report['dimension_conditional_on_numerical_success']['n'],0)
        self.assertEqual(report['stop_reason'],'output_io_failure')

    def test_aggregate_failure_never_returns_success_or_finish_marker(self):
        original=r.os.link
        def injected(src,dst):
            if pathlib.Path(dst).name=='aggregate.public.json':raise OSError('synthetic')
            return original(src,dst)
        with patch.object(r.os,'link',side_effect=injected):
            with self.assertRaisesRegex(r.FatalRunError,'output_io_failure'):self.run_fixture()
        self.assertFalse((self.out/'run-finished.private.json').exists())

    def test_finish_marker_failure_never_returns_success(self):
        original=r.os.link
        def injected(src,dst):
            if pathlib.Path(dst).name=='run-finished.private.json':raise OSError('synthetic')
            return original(src,dst)
        with patch.object(r.os,'link',side_effect=injected):
            with self.assertRaisesRegex(r.FatalRunError,'output_io_failure'):self.run_fixture()
        self.assertFalse((self.out/'run-finished.private.json').exists())

    def test_cloud_digest_failure_is_global(self):
        original=self.enc.encode
        def injected(text):
            cloud,meta=original(text);meta['cloud']['npy_sha256']='0'*64
            return cloud,meta
        self.enc.encode=injected
        report=self.run_fixture()
        self.assertEqual(report['stop_reason'],'cloud_hash_mismatch')
        self.assertEqual([x['status'] for x in self.rows()],['failed','not_run','not_run'])

    def test_first_missing_does_not_repeat_later_record(self):
        del self.manifest['records'][0]['relative_path']
        report=self.run_fixture()
        self.assertEqual(len(self.enc.calls),2)
        self.assertEqual(report['repeat_status'],'first_selected_unavailable')
        self.assertEqual([x['status'] for x in self.rows()],['failed','ok','ok'])

    def test_repeat_source_identity_change_is_global(self):
        original=self.enc.encode
        def injected(text):
            cloud,meta=original(text)
            if len(self.enc.calls)==2:meta['source']['utf8_sha256']='f'*64
            return cloud,meta
        self.enc.encode=injected
        report=self.run_fixture()
        self.assertEqual(report['stop_reason'],'encoder_source_hash_mismatch')
        self.assertEqual(len(self.enc.calls),2)

    def test_runner_self_digest_change_detected_at_final_gate(self):
        fake_runner=self.root/'synthetic-runner.py';fake_runner.write_text('original synthetic bytes')
        original=self.enc.encode
        def injected(text):
            fake_runner.write_text('changed synthetic bytes');return original(text)
        self.enc.encode=injected
        with patch.object(r,'__file__',str(fake_runner)):report=self.run_fixture()
        self.assertEqual(report['stop_reason'],'runner_changed_during_run')
        self.assertTrue(report['partial_numeric_diagnostics_only'])
        self.assertFalse(report['fixed_selection_processing_complete'])

    def test_cli_bad_manifest_hash_never_opens_sources(self):
        file=self.root/'manifest.json';file.write_bytes(r.encoded(self.manifest))
        args=['--authorized-local-run','--manifest',str(file),'--manifest-sha256','0'*64,
              '--source-root',str(self.sources),'--model-dir',str(self.root/'no-model'),
              '--topology-dir',str(CORE),'--out',str(self.out)]
        with patch.object(r,'source_text',side_effect=AssertionError('source read forbidden')):
            with self.assertRaisesRegex(r.FatalRunError,'manifest_hash_mismatch'):r.main(args)
        self.assertFalse(self.out.exists())

    def test_no_clouds_default_and_durable_hash_chain(self):
        report=self.run_fixture()
        self.assertEqual(list(self.out.glob('*.npy')),[])
        final=json.loads((self.out/'run-finished.private.json').read_text())
        self.assertEqual(final['aggregate_sha256'],r.digest((self.out/'aggregate.public.json').read_bytes()))
        self.assertEqual(final['ledger_sha256'],r.digest((self.out/'ledger.private.json').read_bytes()))
        for row in self.rows():
            private=row['private_result']
            self.assertEqual(private['sha256'],r.digest((self.out/private['file']).read_bytes()))

    def test_paths_with_spaces_and_unicode_remain_portable(self):
        self.out=self.root/'中文 space output'
        report=self.run_fixture()
        self.assertEqual(report['run_status'],'complete')
        self.assertTrue((self.out/'run-finished.private.json').exists())

    def test_zero_disk_allowance_stops_before_model(self):
        with self.assertRaisesRegex(r.FatalRunError,'ledger_reserve_exceeds_budget'):
            self.run_fixture(limits=r.Limits(private_bytes=100))
        self.assertEqual(self.enc.calls,[])
        self.assertFalse((self.out/'run-finished.private.json').exists())


if __name__=='__main__':unittest.main(verbosity=2)
