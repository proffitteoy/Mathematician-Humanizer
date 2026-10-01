"""Independent synthetic-only faults. Never opens empirical TEST/labels/exports.

No real ROOT_GO or global TEST_START is created. Temporary output trees use
SYNTHETIC-prefixed paths under this review directory. No fit is executed.
"""
import ast
import copy
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest import mock

PACKAGE = Path('/workspace/shared/style-controlled-test-v01')
REVIEW = Path('/workspace/shared/style-controlled-test-review-v01')
sys.path.insert(0, str(PACKAGE))
import test_evaluator as W
import inference_core as C
import labels_v02 as L


def fixture():
    main = '合成测试的主张是清楚记录'
    text = main + '。' + '这是只用于接口检验的合成句子没有真实事件。' * 7
    assert L.observed_properties(text, main)['mechanical_condition'] == 'short_early'
    rows = []
    reviews = [[], []]
    for family in range(8):
        for slot in range(8):
            sid = f'SYNTHETIC-{family}-{slot}'
            rows.append(dict(id=sid, family=f'SYNTHETIC-F{family}', partition='test',
                genre=C.GENRES[family // 2], status='completed', text=text,
                text_sha256=C.text_hash(text), mainpoint_exact=main,
                fact_ids=['P1','P2','P3','P4','P5','P6'], review_id=sid))
            for i in range(2):
                reviews[i].append(dict(review_id=sid,rater_id=f'SYNTHETIC-R{i}',
                    fact_labels={f'P{j}':'preserved' for j in range(1,7)},
                    semantic_axes={axis:'pass' for axis in L.SEMANTIC_AXES},
                    mainpoint_is_real_main_claim='yes',rhythm_label='short',placement_label='early'))
    data=dict(schema='sanitized-controlled-test/v1',provenance='synthetic_fixture',
        source_draft_manifest_sha256='a'*64,family_split_manifest_sha256='b'*64,slots=rows)
    a,b=[dict(schema='sanitized-blind-reviews/v1',reviews=r) for r in reviews]
    hs=dict(a=C.digest(a),b=C.digest(b))
    ids=sorted(r['review_id'] for r in rows)
    receipts=dict(schema='dual-blind-label-receipts/v1',dataset_file_sha256=C.digest(data),
        review_files_sha256=hs,review_scope='all_completed_test_slots_only_train_dev_excluded',
        raters=[dict(rater_id=f'SYNTHETIC-R{i}',review_context_id=f'SYNTHETIC-C{i}',
            independent_of_authoring=True,independent_of_fit=True,blind_to=list(W.BLIND_TO),
            review_file_sha256=hs[k]) for i,k in enumerate(('a','b'))],
        projection_receipt=dict(schema='root-test-review-projection/v1',actor='root',
            original_review_files_sha256=dict(a='c'*64,b='d'*64),
            original_review_row_counts=dict(a=384,b=384),subset_review_files_sha256=hs.copy(),
            selected_review_ids=ids,selected_review_ids_sha256=C.digest(ids),train_dev_rows_exported=0))
    return data,a,b,receipts


def model():
    return dict(schema=C.VERSION,feature_schema_sha256=C.SCHEMA_SHA,feature_names=list(C.FEATURES),
        conditions=list(C.CONDITIONS),training=dict(status='completed_actual_gradient_fit',
        training_only=True,provenance='synthetic_fixture',epochs=150,lr=.05,preference_pairs=0),
        condition_weights=[[0.]*12+[math.log(p)] for p in (.4,.3,.2,.1)],
        preference_weights=[[0.]*13 for _ in range(4)],
        transform=dict(fit_partition='train',center=[0.]*12,scale=[1.]*12,constant=[False]*12))


class IndependentFaultTests(unittest.TestCase):
    def setUp(self): self.args=fixture(); self.m=model()
    def predictions(self):return W.predict_all(self.m,self.args[0],synthetic=True)
    def validated(self):return W.validate_data(*self.args,synthetic=True)
    def test_no_fit_edit_generate_import_or_call(self):
        allowed={'__future__','argparse','datetime','hashlib','json','math','os','re','resource','signal','stat','sys','time','pathlib','inference_core','labels_v02'}
        for name in ('test_evaluator.py','inference_core.py','labels_v02.py'):
            tree=ast.parse((PACKAGE/name).read_text())
            for n in ast.walk(tree):
                if isinstance(n,ast.Import):self.assertTrue(all(x.name in allowed for x in n.names))
                elif isinstance(n,ast.ImportFrom):self.assertIn(n.module,allowed)
                elif isinstance(n,ast.Call):
                    fn=n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id if isinstance(n.func,ast.Name) else None
                    self.assertNotIn(fn,('fit','edit','generate','scale_fit','eval','exec','compile','__import__'))
    def test_feature_ast_identical_to_frozen_fit(self):
        old=ast.parse((W.FIT_ROOT/'controller_v03.py').read_text());new=ast.parse((PACKAGE/'inference_core.py').read_text())
        def function(tree,name):return ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
        for n in ('features','scaled','softmax','canonical','digest','text_hash','finite'):
            self.assertEqual(function(old,n),function(new,n))
    def test_manifest_exact_bytes(self):
        manifest=json.loads((PACKAGE/'FILE_HASHES.json').read_text())
        for item in manifest['files']:
            raw=(PACKAGE/item['path']).read_bytes()
            self.assertEqual(len(raw),item['bytes']);self.assertEqual(hashlib.sha256(raw).hexdigest(),item['sha256'])
    def test_checkpoint_and_completion_hash_binding(self):
        self.assertEqual(hashlib.sha256(W.CHECKPOINT.read_bytes()).hexdigest(),W.CHECKPOINT_SHA)
        self.assertEqual(hashlib.sha256(W.FIT_RECEIPT.read_bytes()).hexdigest(),W.FIT_RECEIPT_SHA)
        self.assertEqual(hashlib.sha256(W.FIT_COMPLETE.read_bytes()).hexdigest(),W.FIT_COMPLETE_SHA)
        frozen=W.load_frozen_model();self.assertEqual(frozen['transform']['fit_partition'],'train')
        self.assertTrue(all(v==0 for row in frozen['preference_weights'] for v in row))
    def test_no_label_or_source_path_channel(self):
        for field in ('actual_realized_condition','realized_condition','semantic_consensus_pass','semantic_pass','exclusion_reason','nominal_target','source_path','template','pass'):
            d=copy.deepcopy(self.args[0]);d['slots'][0][field]='forbidden'
            with self.assertRaises(C.ContractError):W.predict_all(self.m,d,synthetic=True)
    def test_all64_before_review_or_diagnostics(self):
        with mock.patch.object(L,'observed_properties',side_effect=AssertionError('diagnostics before freeze')),mock.patch.object(L,'adjudicate_pair',side_effect=AssertionError('labels before freeze')):
            p=self.predictions()
        self.assertEqual(len(p['predictions']),64);self.assertTrue(all(x['prediction_status']=='predicted' for x in p['predictions']))
    def test_outside_support_still_predicted(self):
        r=self.args[0]['slots'][0];r['text']=r['mainpoint_exact']+'。';r['text_sha256']=C.text_hash(r['text'])
        self.assertEqual(self.predictions()['predictions'][0]['prediction_status'],'predicted')
        self.assertEqual(len(self.validated()['eligible']['test']),63)
    def test_actual_disagreement_excluded_no_nominal_relabel(self):
        self.args[2]['reviews'][0]['placement_label']='late'
        self.assertEqual(len(self.validated()['eligible']['test']),63)
    def test_semantic_fail_excluded_only_after_predictions(self):
        before=self.predictions();self.args[1]['reviews'][0]['semantic_axes']['scope']='fail'
        self.assertEqual(before,self.predictions());self.assertEqual(len(self.validated()['eligible']['test']),63)
    def test_uncertain_fact_excluded(self):
        self.args[2]['reviews'][0]['fact_labels']['P5']='uncertain'
        self.assertEqual(len(self.validated()['eligible']['test']),63)
    def test_zero_eligible_family_whole_denominator(self):
        for r in self.args[1]['reviews'][:8]:r['semantic_axes']['facts']='fail'
        m=W.family_metrics(self.predictions(),self.validated())
        self.assertEqual((m['all_slots'],m['all_families'],m['eligible_rows'],m['eligible_families']),(64,8,56,7))
        self.assertEqual(m['family_macro_coverage_over_all_original_slots'],7/8)
        self.assertAlmostEqual(m['family_macro_cross_entropy_on_eligible'],-math.log(.4))
    def test_all_ineligible_still64_and8(self):
        for r in self.args[1]['reviews']:r['semantic_axes']['facts']='uncertain'
        m=W.family_metrics(self.predictions(),self.validated())
        self.assertEqual((m['all_slots'],m['all_families'],m['eligible_rows']),(64,8,0))
        self.assertIsNone(m['family_macro_accuracy_on_eligible']);self.assertIsNone(m['family_macro_cross_entropy_on_eligible'])
        self.assertEqual(m['family_macro_coverage_over_all_original_slots'],0)
    def test_macro_weighting_not_row_pooling(self):
        for r in self.args[1]['reviews'][1:8]:r['semantic_axes']['facts']='fail'
        p=self.predictions();p['predictions'][0]['probabilities']=[.1,.2,.3,.4];p['predictions'][0]['predicted_condition']='mixed_late'
        m=W.family_metrics(p,self.validated())
        self.assertAlmostEqual(m['family_macro_cross_entropy_on_eligible'],(-math.log(.1)-7*math.log(.4))/8)
        self.assertAlmostEqual(m['family_macro_accuracy_on_eligible'],7/8)
        self.assertEqual(m['family_macro_coverage_over_all_original_slots'],57/64)
        self.assertEqual(m['exact_threshold_rule']['family_macro_accuracy_on_eligible'],1)
        self.assertIn('tautological',m['exact_threshold_rule']['interpretation'])
    def test_training_scaler_and_constant_mask_only(self):
        m=copy.deepcopy(self.m);m['transform']['fit_partition']='test'
        with self.assertRaises(C.ContractError):W.validate_model(m,synthetic=True)
        m=copy.deepcopy(self.m);m['transform']['constant'][0]=1
        with self.assertRaises(C.ContractError):W.validate_model(m,synthetic=True)
        m=copy.deepcopy(self.m);m['transform']['scale'][0]=0
        with self.assertRaises(C.ContractError):W.validate_model(m,synthetic=True)
    def test_missing_extra_review_and_original_paths_refused(self):
        d,a,b,r=copy.deepcopy(self.args);a['reviews'].append(dict(a['reviews'][0],review_id='SYNTHETIC-extraneous'))
        with self.assertRaises(C.ContractError):W.validate_data(d,a,b,r,synthetic=True)
        d,a,b,r=copy.deepcopy(self.args);r['projection_receipt']['original_files']=['/never/open']
        with self.assertRaises(C.ContractError):W.validate_data(d,a,b,r,synthetic=True)
    def test_wrong_bound_input_hash_fails_before_parse(self):
        with mock.patch.object(W,'safe_bytes',return_value=b'not json'):
            with self.assertRaisesRegex(C.ContractError,'input_hash_mismatch'):W.read_bound(Path('/SYNTHETIC'), 'test.json', {'input_sha256':{'test.json':'0'*64}})
    def test_unapproved_input_name_never_opened(self):
        with mock.patch.object(W,'safe_bytes',side_effect=AssertionError('read forbidden')):
            with self.assertRaisesRegex(C.ContractError,'unapproved_input_name'):W.read_bound(Path('/SYNTHETIC'),'../source.json',{})
    def test_marker_binding_mismatch_no_test_read(self):
        with mock.patch.object(W,'safe_bytes',return_value=C.canonical({'root_GO_file_sha256':'0'*64})),mock.patch.object(W,'read_bound',side_effect=AssertionError('read before claim')):
            with self.assertRaises(C.ContractError):W.evaluate_after_start(Path('/SYNTHETIC'),{},self.m,Path('/SYNTHETIC'),'1'*64)
    def test_existing_marker_blocks_even_new_go_without_read(self):
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=REVIEW) as td:
            marker=Path(td)/'SYNTHETIC_MARKER';marker.write_text('{}')
            with mock.patch.object(W,'GLOBAL_TEST_START',marker),mock.patch.object(W,'safe_bytes',side_effect=AssertionError('read forbidden')):
                with self.assertRaisesRegex(C.ContractError,'already_started'):W.authorize_go('/SYNTHETIC','2'*64)
    def test_readonly_freeze_fsync_file_and_parent(self):
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=REVIEW) as td:
            p=Path(td)/'SYNTHETIC_FREEZE.json';real_fsync=os.fsync;fsynced=[]
            def sync(fd):fsynced.append(os.fstat(fd).st_mode);return real_fsync(fd)
            with mock.patch.object(W.os,'fsync',side_effect=sync):W.write_once(p,{'synthetic_only':True})
            import stat
            self.assertEqual(len(fsynced),2);self.assertTrue(stat.S_ISREG(fsynced[0]));self.assertTrue(stat.S_ISDIR(fsynced[1]))
            self.assertEqual(p.stat().st_mode&0o222,0)
            with self.assertRaises(FileExistsError):W.write_once(p,{})
    def test_parent_and_leaf_symlink_rejected(self):
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=REVIEW) as td:
            p=Path(td);(p/'real').mkdir();(p/'real'/'data').write_text('{}');(p/'alias').symlink_to(p/'real',target_is_directory=True)
            with self.assertRaisesRegex(C.ContractError,'symlink'):W.safe_bytes(p/'alias'/'data',100)
    def test_terminal_writes_in_cumulative_output_budget(self):
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=REVIEW) as td,mock.patch.object(W,'ROOT',Path(td)):
            p=Path(td);(p/'run_state').mkdir();(p/'runs').mkdir();payload={'status':'synthetic failure'}
            rawlen=len(C.canonical(payload))+1
            (p/'runs'/'SYNTHETIC.bin').write_bytes(b'x'*(W.OUTPUT_RESERVE-rawlen))
            W.write_run_output(p/'runs'/'FAILED.json',payload)
            with self.assertRaisesRegex(C.ContractError,'cumulative_output'):W.write_run_output(p/'run_state'/'TEST_COMPLETE.json',{})
    def test_future_and_stale_storage_receipts_rejected(self):
        r=dict(schema='controlled-artifact-budget-receipt/v1',actor='root',excluded_root=str(W.ROOT),
            external_controlled_bytes=0,controlled_byte_cap=W.LIMIT,exclusive_budget_reservation=True,
            reserved_output_bytes=W.OUTPUT_RESERVE,no_other_controlled_writes_until_release=True)
        for delta in (-700,700):
            r['measured_at_utc']=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=delta)).isoformat()
            with self.assertRaisesRegex(C.ContractError,'stale'):W.verify_storage(r)
    def test_cap_includes_current_package_and_full_output_reservation(self):
        r=dict(schema='controlled-artifact-budget-receipt/v1',actor='root',excluded_root=str(W.ROOT),
            measured_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),external_controlled_bytes=W.LIMIT-W.OUTPUT_RESERVE,
            controlled_byte_cap=W.LIMIT,exclusive_budget_reservation=True,reserved_output_bytes=W.OUTPUT_RESERVE,
            no_other_controlled_writes_until_release=True)
        with mock.patch.object(W,'package_bytes',return_value=1):
            with self.assertRaisesRegex(C.ContractError,'cap_exceeded'):W.verify_storage(r)
    def test_durable_mkdir_syncs_new_entry_in_parent(self):
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=REVIEW) as td:
            path=Path(td)/'SYNTHETIC-DIR';calls=[];real=W.fsync_directory
            def sync(p):calls.append(Path(p));return real(p)
            with mock.patch.object(W,'fsync_directory',side_effect=sync):W.durable_mkdir(path)
            self.assertEqual(calls,[path,path.parent])
    def test_parent_directory_sync_failure_before_start_means_no_test_read(self):
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=REVIEW) as td:
            root=Path(td);marker=root/'run_state'/'SYNTHETIC_START.json';calls=[];real=W.fsync_directory
            def sync(p):
                calls.append(Path(p))
                if Path(p)==root:raise OSError('SYNTHETIC parent fsync failure')
                return real(p)
            with mock.patch.object(W,'ROOT',root),mock.patch.object(W,'GLOBAL_TEST_START',marker),mock.patch.object(W,'apply_limits',return_value={}),mock.patch.object(W,'authorize_go',return_value=(root,{'run_id':'SYNTHETIC'},0)),mock.patch.object(W,'load_frozen_model',return_value=self.m),mock.patch.object(W,'fsync_directory',side_effect=sync),mock.patch.object(W,'evaluate_after_start',side_effect=AssertionError('TEST must stay unopened')):
                with self.assertRaisesRegex(OSError,'parent fsync failure'):W.run(root,'a'*64)
            self.assertFalse(marker.exists());self.assertEqual(calls,[root/'run_state',root])
    def test_output_parent_sync_failure_consumes_start_without_read(self):
        go=dict(run_id='SYNTHETIC',package_manifest_sha256='a'*64,protocol_sha256='b'*64,code_sha256={},input_sha256={})
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=REVIEW) as td:
            root=Path(td);marker=root/'run_state'/'SYNTHETIC_START.json';real=W.fsync_directory
            def sync(p):
                if Path(p)==root/'runs' and (root/'runs'/'SYNTHETIC').exists():raise OSError('SYNTHETIC output parent fsync failure')
                return real(p)
            with mock.patch.object(W,'ROOT',root),mock.patch.object(W,'CANONICAL_ROOT',root),mock.patch.object(W,'GLOBAL_TEST_START',marker),mock.patch.object(W,'apply_limits',return_value={}),mock.patch.object(W,'authorize_go',return_value=(root,go,0)),mock.patch.object(W,'load_frozen_model',return_value=self.m),mock.patch.object(W,'fsync_directory',side_effect=sync),mock.patch.object(W,'evaluate_after_start',side_effect=AssertionError('TEST must stay unopened')):
                with self.assertRaisesRegex(OSError,'output parent fsync failure'):W.run(root,'a'*64)
            self.assertTrue(marker.exists());self.assertTrue((root/'runs'/'SYNTHETIC'/'FAILED.json').exists())
            self.assertFalse((root/'run_state'/'TEST_COMPLETE.json').exists())
            with mock.patch.object(W,'ROOT',root),mock.patch.object(W,'CANONICAL_ROOT',root),mock.patch.object(W,'GLOBAL_TEST_START',marker),mock.patch.object(W,'safe_bytes',side_effect=AssertionError('retry read forbidden')):
                with self.assertRaisesRegex(C.ContractError,'already_started'):W.authorize_go(root,'b'*64)
    def test_lexical_parent_alias_blocked_before_input_read(self):
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=REVIEW) as td:
            root=Path(td);(root/'a').mkdir();(root/'b').mkdir()
            with mock.patch.object(W,'safe_bytes',side_effect=AssertionError('alias read forbidden')):
                with self.assertRaisesRegex(C.ContractError,'noncanonical'):W.authorize_go(root/'a'/'..'/'b','a'*64)
    def _terminal_harness(self,root,*,sync_fault=False,stdout_fault=False):
        from contextlib import ExitStack
        go=dict(run_id='SYNTHETIC',package_manifest_sha256='a'*64,protocol_sha256='b'*64,code_sha256={},input_sha256={})
        marker=root/'run_state'/'SYNTHETIC_START.json';original_write=W.write_run_output;real_fsync=os.fsync;tripped=[]
        def write(path,obj):return original_write(path,dict(obj,synthetic_only=True))
        def fsync(fd):
            control=root/'run_state';complete=control/'TEST_COMPLETE.json'
            if sync_fault and not tripped and complete.exists() and os.fstat(fd).st_ino==control.stat().st_ino:
                tripped.append(True);raise OSError('SYNTHETIC actual completion fsync fault')
            return real_fsync(fd)
        with ExitStack() as stack:
            for name,val in (('ROOT',root),('GLOBAL_TEST_START',marker)):
                stack.enter_context(mock.patch.object(W,name,val))
            for name,val in (('apply_limits',{}),('authorize_go',(root,go,0)),('load_frozen_model',self.m),('evaluate_after_start',('c'*64,{},dict(family_support={'test':{}},exclusions={}),{}))):
                stack.enter_context(mock.patch.object(W,name,return_value=val))
            stack.enter_context(mock.patch.object(W,'write_run_output',side_effect=write))
            stack.enter_context(mock.patch.object(W.os,'fsync',side_effect=fsync))
            stack.enter_context(mock.patch('builtins.print',side_effect=BrokenPipeError('SYNTHETIC stdout fault') if stdout_fault else None))
            W.run(root,'d'*64)
    def test_actual_completion_parent_fsync_failure_retains_failed_state(self):
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=REVIEW) as td:
            root=Path(td)
            with self.assertRaisesRegex(OSError,'actual completion fsync fault'):self._terminal_harness(root,sync_fault=True)
            self.assertTrue((root/'run_state'/'SYNTHETIC_START.json').exists())
            self.assertTrue((root/'run_state'/'TEST_COMPLETE.json').exists())
            self.assertTrue((root/'runs'/'SYNTHETIC'/'FAILED.json').exists())
    def test_broken_stdout_cannot_create_failed_after_commit(self):
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=REVIEW) as td:
            root=Path(td);self._terminal_harness(root,stdout_fault=True)
            self.assertTrue((root/'run_state'/'TEST_COMPLETE.json').exists())
            self.assertFalse((root/'runs'/'SYNTHETIC'/'FAILED.json').exists())
    def test_duplicate_keys_and_explicit_nonfinite_refused(self):
        for raw in ('{"a":1,"a":2}','{"a":NaN}','{"a":-Infinity}'):
            with self.assertRaises(C.ContractError):W.strict_json(raw)

if __name__=='__main__':unittest.main(verbosity=2)
