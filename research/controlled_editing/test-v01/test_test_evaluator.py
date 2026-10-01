"""Synthetic fixtures only. No actual TEST, fit, root GO or empirical marker."""
import ast,copy,datetime as dt,json,math,os,tempfile,unittest
from pathlib import Path
from unittest import mock
from concurrent.futures import ThreadPoolExecutor
import inference_core as C
import labels_v02 as L
import test_evaluator as W

def toy_text(condition,variant=0):
    mainpoint='记录让交接更清楚'
    short=['这是明确标记的合成接口测试句不涉及实际人物']*7
    mixed=['这是合成短句','这是明确标记的合成接口测试文字仅为检查软件流程而设计并不来自任何实际成文或真实研究记录不含实验观测结果','这是合成测试中的另一个较长句子用来改变句长分布所有相同文字都只代表单元测试夹具不可作为实证研究证据','这是普通测试句用于检查结尾位置']
    parts=short if condition.startswith('short') else mixed
    parts=([mainpoint]+parts) if condition.endswith('early') else (parts+[mainpoint])
    return '。'.join(parts)+'。',mainpoint


def fixtures():
    data={'schema':'sanitized-controlled-test/v1','provenance':'synthetic_fixture','source_draft_manifest_sha256':'1'*64,'family_split_manifest_sha256':'2'*64,'slots':[]}
    a={'schema':'sanitized-blind-reviews/v1','reviews':[]};b=copy.deepcopy(a)
    for f in range(8):
        partition='test';genre=C.GENRES[f//2]
        for condition in C.CONDITIONS:
            for rep in range(2):
                rid=f'synthetic-{f}-{condition}-{rep}';text,main=toy_text(condition)
                assert L.observed_properties(text,main)['mechanical_condition']==condition
                row={'id':rid,'family':f'synthetic-family-{f}','partition':partition,'genre':genre,'status':'completed','text':text,'text_sha256':C.text_hash(text),'mainpoint_exact':main,'fact_ids':['P1','P2','P3','P4','P5','P6'],'review_id':rid};data['slots'].append(row)
                for payload,rater in ((a,'synthetic-a'),(b,'synthetic-b')):
                    payload['reviews'].append({'review_id':rid,'rater_id':rater,'fact_labels':{k:'preserved' for k in row['fact_ids']},'semantic_axes':{k:'pass' for k in L.SEMANTIC_AXES},'mainpoint_is_real_main_claim':'yes','rhythm_label':condition.split('_')[0],'placement_label':condition.split('_')[1]})
    receipts={'schema':'dual-blind-label-receipts/v1','dataset_file_sha256':C.digest(data),'review_files_sha256':{'a':C.digest(a),'b':C.digest(b)},'raters':[],'review_scope':'all_completed_test_slots_only_train_dev_excluded'}
    for key in ('a','b'):
        receipts['raters'].append({'rater_id':'synthetic-'+key,'review_context_id':'synthetic-context-'+key,'independent_of_authoring':True,'independent_of_fit':True,'blind_to':W.BLIND_TO,'review_file_sha256':receipts['review_files_sha256'][key]})
    receipts['projection_receipt']={'schema':'root-test-review-projection/v1','actor':'root','original_review_files_sha256':{'a':'3'*64,'b':'4'*64},'original_review_row_counts':{'a':384,'b':384},'subset_review_files_sha256':receipts['review_files_sha256'].copy(),'selected_review_ids':sorted(r['review_id'] for r in a['reviews']),'selected_review_ids_sha256':C.digest(sorted(r['review_id'] for r in a['reviews'])),'train_dev_rows_exported':0}
    return data,a,b,receipts


def model():
    # Analytic uniform-probability fixture. Never fitted; not a deployment model.
    return {'schema':C.VERSION,'feature_schema_sha256':C.SCHEMA_SHA,'feature_names':list(C.FEATURES),'conditions':list(C.CONDITIONS),'training':{'status':'completed_actual_gradient_fit','training_only':True,'provenance':'synthetic_fixture','epochs':150,'lr':.05,'preference_pairs':0},'condition_weights':[[0.]*13 for _ in range(4)],'preference_weights':[[0.]*13 for _ in range(4)],'transform':{'fit_partition':'train','center':[0.]*12,'scale':[1.]*12,'constant':[False]*12}}


def refresh_receipts(data,a,b,r):
    r['dataset_file_sha256']=C.digest(data);r['review_files_sha256']={'a':C.digest(a),'b':C.digest(b)}
    for i,k in enumerate(('a','b')):r['raters'][i]['review_file_sha256']=r['review_files_sha256'][k]
    p=r['projection_receipt'];p['subset_review_files_sha256']=r['review_files_sha256'].copy();p['selected_review_ids']=sorted(x['review_id'] for x in a['reviews']);p['selected_review_ids_sha256']=C.digest(p['selected_review_ids'])


class EvaluatorTests(unittest.TestCase):
    def setUp(self):self.args=fixtures();self.model=model()
    def validate(self):return W.validate_data(*self.args,synthetic=True)
    def predictions(self):return W.predict_all(self.model,self.args[0],synthetic=True)
    def metrics(self):return W.family_metrics(self.predictions(),self.validate())
    def test_all_original_slots_and_eight_families(self):
        m=self.metrics();self.assertEqual(m['all_slots'],64);self.assertEqual(m['all_families'],8);self.assertEqual(m['eligible_rows'],64);self.assertEqual(m['family_macro_coverage_over_all_original_slots'],1)
    def test_uniform_cross_entropy_and_tie_accuracy(self):
        m=self.metrics();self.assertAlmostEqual(m['family_macro_cross_entropy_on_eligible'],math.log(4));self.assertEqual(m['family_macro_accuracy_on_eligible'],.25)
    def test_rule_comparator_is_tautological(self):
        m=self.metrics()['exact_threshold_rule'];self.assertEqual(m['family_macro_accuracy_on_eligible'],1);self.assertLess(m['family_macro_cross_entropy_on_eligible'],1e-14)
    def test_empirical_rejects_synthetic_data(self):
        with self.assertRaisesRegex(C.ContractError,'provenance'):W.validate_data(*self.args)
    def test_empirical_rejects_synthetic_model(self):
        with self.assertRaisesRegex(C.ContractError,'trained_checkpoint'):W.validate_model(self.model)
    def test_synthetic_model_validation(self):self.assertEqual(W.validate_model(self.model,synthetic=True),self.model)
    def test_no_train_dev_or_unknown_partition(self):
        for partition in ('train','dev','unknown'):
            self.args[0]['slots'][0]['partition']=partition
            with self.assertRaisesRegex(C.ContractError,'partition'):self.validate()
    def test_no_label_or_semantic_columns_in_prediction_data(self):
        for key in ('realized_condition','exclusion_reason','nominal_target','semantic_pass','template','pass'):
            self.args[0]['slots'][0][key]=None
            with self.assertRaisesRegex(C.ContractError,'slot_schema'):self.predictions()
            del self.args[0]['slots'][0][key]
    def test_missing_slot_rejected_no_replacements(self):
        self.args[0]['slots'].pop()
        with self.assertRaisesRegex(C.ContractError,'64'):self.validate()
    def test_duplicate_slot_rejected(self):
        self.args[0]['slots'][1]['id']=self.args[0]['slots'][0]['id']
        with self.assertRaisesRegex(C.ContractError,'duplicate'):self.validate()
    def test_family_genre_change_rejected(self):
        self.args[0]['slots'][0]['genre']=C.GENRES[1]
        with self.assertRaisesRegex(C.ContractError,'family_leakage'):self.validate()
    def test_text_tamper_rejected(self):
        self.args[0]['slots'][0]['text']+='甲'
        with self.assertRaisesRegex(C.ContractError,'text_hash'):self.predictions()
    def test_reviews_do_not_change_predictions(self):
        before=self.predictions();self.args[1]['reviews'][0]['semantic_axes']['facts']='fail'
        self.assertEqual(before,self.predictions());self.assertEqual(self.metrics()['eligible_rows'],63)
    def test_rater_uncertainty_excluded_not_relabelled(self):
        self.args[2]['reviews'][0]['rhythm_label']='uncertain';v=self.validate();self.assertEqual(v['exclusions'],{'dual_review_or_support_excluded':1});self.assertEqual(self.metrics()['all_slots'],64)
    def test_zero_eligible_family_in_coverage(self):
        for x in self.args[1]['reviews'][:8]:x['semantic_axes']['facts']='fail'
        m=self.metrics();self.assertEqual(m['eligible_families'],7);self.assertEqual(m['all_families'],8);self.assertEqual(m['family_macro_coverage_over_all_original_slots'],7/8)
    def test_zero_eligible_total_reports_null_metrics(self):
        for x in self.args[1]['reviews']:x['semantic_axes']['facts']='fail'
        m=self.metrics();self.assertIsNone(m['family_macro_accuracy_on_eligible']);self.assertIsNone(m['family_macro_cross_entropy_on_eligible']);self.assertEqual(m['family_macro_coverage_over_all_original_slots'],0)
    def test_failed_slot_kept_in_denominator(self):
        row=self.args[0]['slots'][0];rid=row['review_id'];row.update(status='technical_failed',text=None,text_sha256=None,mainpoint_exact=None,review_id=None,fact_ids=[])
        for p in self.args[1:3]:p['reviews']=[x for x in p['reviews'] if x['review_id']!=rid]
        refresh_receipts(*self.args)
        self.assertEqual(self.predictions()['predictions'][0]['prediction_status'],'unproduced_original_slot');self.assertEqual(self.metrics()['family_macro_coverage_over_all_original_slots'],63/64)
    def test_duplicate_mainpoint_retains_null_prediction(self):
        row=self.args[0]['slots'][0];row['mainpoint_exact']='这是';self.assertGreater(row['text'].count('这是'),1)
        self.assertEqual(self.predictions()['predictions'][0]['prediction_status'],'mainpoint_span_unavailable');self.assertEqual(self.metrics()['eligible_rows'],63)
    def test_outside_mechanical_support_still_predicted(self):
        row=self.args[0]['slots'][0];row['text']=row['mainpoint_exact']+'。短句。';row['text_sha256']=C.text_hash(row['text'])
        self.assertEqual(self.predictions()['predictions'][0]['prediction_status'],'predicted');self.assertEqual(self.metrics()['eligible_rows'],63)
    def test_same_raters_or_context_rejected(self):
        for key in ('rater_id','review_context_id'):
            save=self.args[3]['raters'][1][key];self.args[3]['raters'][1][key]=self.args[3]['raters'][0][key]
            with self.assertRaisesRegex(C.ContractError,'independent_raters'):self.validate()
            self.args[3]['raters'][1][key]=save
    def test_no_unblinded_review_receipt(self):
        self.args[3]['raters'][0]['blind_to']=[]
        with self.assertRaisesRegex(C.ContractError,'blind_receipt'):self.validate()
    def test_missing_review_rejected(self):
        self.args[1]['reviews'].pop()
        with self.assertRaisesRegex(C.ContractError,'coverage'):self.validate()
    def test_full384_reviews_rejected(self):
        self.args[1]['reviews'].append(dict(self.args[1]['reviews'][0],review_id='SYNTHETIC-extra'))
        with self.assertRaisesRegex(C.ContractError,'coverage'):self.validate()
    def test_projection_hash_only_no_source_paths(self):
        self.args[3]['projection_receipt']['original_path']='/forbidden'
        with self.assertRaisesRegex(C.ContractError,'projection_receipt_schema'):self.validate()
    def test_projection_original384_hash_required(self):
        self.args[3]['projection_receipt']['original_review_row_counts']['a']=64
        with self.assertRaisesRegex(C.ContractError,'row_counts'):self.validate()
    def test_projection_exact_selected_ids(self):
        self.args[3]['projection_receipt']['selected_review_ids'].pop()
        with self.assertRaisesRegex(C.ContractError,'selected_ids'):self.validate()
    def test_no_train_dev_projected_review_rows(self):
        self.args[3]['projection_receipt']['train_dev_rows_exported']=1
        with self.assertRaisesRegex(C.ContractError,'train_dev_rows'):self.validate()
    def test_projection_subset_hash_bound(self):
        self.args[3]['projection_receipt']['subset_review_files_sha256']['a']='0'*64
        with self.assertRaisesRegex(C.ContractError,'subset_hash'):self.validate()
    def test_family_macro_not_pooled(self):
        for x in self.args[1]['reviews'][1:8]:x['semantic_axes']['facts']='fail'
        p=self.predictions();p['predictions'][0]['probabilities']=[.7,.1,.1,.1];v=self.validate();m=W.family_metrics(p,v)
        expected=(-math.log(.7)+7*math.log(4))/8
        self.assertAlmostEqual(m['family_macro_cross_entropy_on_eligible'],expected)
    def test_scoring_does_not_recompute_predictions(self):
        pred=self.predictions();v=self.validate()
        with mock.patch.object(W,'probabilities',side_effect=AssertionError('must not score again')):W.family_metrics(pred,v)
    def test_checkpoint_fixed_epochs_lr_preference_zero(self):
        for mutate in (lambda m:m['training'].update(epochs=149),lambda m:m['training'].update(lr=.1),lambda m:m['preference_weights'][0].__setitem__(0,.01)):
            m=copy.deepcopy(self.model);mutate(m)
            with self.assertRaises(C.ContractError):W.validate_model(m,synthetic=True)
    def test_finite_tensor_and_boolean_mask_required(self):
        m=copy.deepcopy(self.model);m['condition_weights'][0][0]=float('nan')
        with self.assertRaises(C.ContractError):W.validate_model(m,synthetic=True)
        m=copy.deepcopy(self.model);m['transform']['constant'][0]=1
        with self.assertRaises(C.ContractError):W.validate_model(m,synthetic=True)
    def test_duplicate_and_nonfinite_json_rejected(self):
        for text in ('{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}'):
            with self.assertRaises(C.ContractError):W.strict_json(text)
    def test_no_expected_root_hash_means_no_input_read(self):
        with mock.patch.object(W,'safe_bytes',side_effect=AssertionError('unauthorized read')):
            with self.assertRaisesRegex(C.ContractError,'explicit_expected'):W.authorize_go('/does/not/exist',None)
    def test_global_marker_blocks_different_runs_before_input_read(self):
        with tempfile.TemporaryDirectory(dir=W.ROOT) as td:
            marker=Path(td)/'SYNTHETIC_START.json';W.write_once(marker,{'synthetic_only':True})
            with mock.patch.object(W,'GLOBAL_TEST_START',marker),mock.patch.object(W,'safe_bytes',side_effect=AssertionError('must not read')):
                with self.assertRaisesRegex(C.ContractError,'already_started'):W.authorize_go('/does/not/exist','1'*64)
    def test_exclusive_marker_race_and_readonly(self):
        with tempfile.TemporaryDirectory(dir=W.ROOT) as td:
            path=Path(td)/'SYNTHETIC_START.json'
            def attempt(i):
                try:W.write_once(path,{'synthetic_only':i});return True
                except FileExistsError:return False
            with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sum(pool.map(attempt,range(8))),1)
            self.assertEqual(path.stat().st_mode&0o222,0)
    def test_parent_traversal_alias_rejected_before_input_open(self):
        with tempfile.TemporaryDirectory(dir=W.ROOT) as td:
            root=Path(td);(root/'a').mkdir();(root/'b').mkdir()
            with mock.patch.object(W,'safe_bytes',side_effect=AssertionError('must not read')):
                with self.assertRaisesRegex(C.ContractError,'noncanonical'):W.authorize_go(root/'a'/'..'/'b','1'*64)

    def test_symlink_file_and_parent_rejected(self):
        with tempfile.TemporaryDirectory(dir=W.ROOT) as td:
            root=Path(td);(root/'real').mkdir();(root/'real'/'x').write_text('{}');(root/'file').symlink_to(root/'real'/'x');(root/'dir').symlink_to(root/'real',target_is_directory=True)
            for p in (root/'file',root/'dir'/'x'):
                with self.assertRaisesRegex(C.ContractError,'symlink'):W.safe_bytes(p,100)
    def test_cumulative_output_cap_before_write(self):
        with tempfile.TemporaryDirectory(dir=W.ROOT) as td,mock.patch.object(W,'ROOT',Path(td)):
            root=Path(td);(root/'runs').mkdir();(root/'runs'/'SYNTHETIC.bin').write_bytes(b'x'*(W.OUTPUT_RESERVE-4096))
            with self.assertRaisesRegex(C.ContractError,'cumulative_output'):W.write_run_output(root/'runs'/'SYNTHETIC.json',{'x':1})
            self.assertFalse((root/'runs'/'SYNTHETIC.json').exists())
    def test_fresh_exclusive_storage_and_cap(self):
        r={'schema':'controlled-artifact-budget-receipt/v1','actor':'root','measured_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'excluded_root':str(W.ROOT),'external_controlled_bytes':0,'controlled_byte_cap':W.LIMIT,'exclusive_budget_reservation':True,'reserved_output_bytes':W.OUTPUT_RESERVE,'no_other_controlled_writes_until_release':True}
        self.assertEqual(W.verify_storage(r),0);r['external_controlled_bytes']=W.LIMIT
        with self.assertRaisesRegex(C.ContractError,'cap_exceeded'):W.verify_storage(r)
        r['external_controlled_bytes']=0;r['measured_at_utc']='2000-01-01T00:00:00+00:00'
        with self.assertRaisesRegex(C.ContractError,'stale'):W.verify_storage(r)
    def test_prediction_file_exists_before_any_label_read(self):
        data,a,b,r=self.args;refresh_receipts(*self.args)
        blobs={'test.json':data,'labels_a.json':a,'labels_b.json':b,'label_receipts.json':r}
        go={'input_sha256':{k:C.digest(v) for k,v in blobs.items()},'review_approval_sha256':C.digest(r)}
        marker={'root_GO_file_sha256':'5'*64,'input_sha256':go['input_sha256'],'checkpoint_sha256':W.CHECKPOINT_SHA,'fit_receipt_sha256':W.FIT_RECEIPT_SHA}
        trace=[];orig_predict=W.predict_all;orig_validate=W.validate_data;orig_safe=W.safe_bytes
        with tempfile.TemporaryDirectory(dir=W.ROOT) as td:
            out=Path(td);marker_path=out/'NOT_AN_EMPIRICAL_MARKER'
            def read(folder,name,g):
                trace.append(name)
                if name!='test.json':self.assertTrue((out/'PREDICTIONS_FROZEN.json').exists());self.assertEqual((out/'PREDICTIONS_FROZEN.json').stat().st_mode&0o222,0)
                return blobs[name]
            def safe(p,limit):return C.canonical(marker) if Path(p)==marker_path else orig_safe(p,limit)
            with mock.patch.object(W,'GLOBAL_TEST_START',marker_path),mock.patch.object(W,'safe_bytes',side_effect=safe),mock.patch.object(W,'read_bound',side_effect=read),mock.patch.object(W,'predict_all',side_effect=lambda m,d:orig_predict(m,d,synthetic=True)),mock.patch.object(W,'validate_data',side_effect=lambda *args:orig_validate(*args,synthetic=True)):
                sha,metrics,v,audit=W.evaluate_after_start(out,go,self.model,out,'5'*64)
            self.assertEqual(trace,['test.json','labels_a.json','labels_b.json','label_receipts.json']);self.assertEqual(len(audit),64);self.assertEqual(metrics['all_slots'],64)
    def test_durable_mkdir_syncs_directory_and_parent_before_return(self):
        with tempfile.TemporaryDirectory(dir=W.ROOT) as td:
            path=Path(td)/'SYNTHETIC_DIRECTORY';events=[]
            def sync(p):self.assertTrue(path.is_dir());events.append(Path(p))
            with mock.patch.object(W,'fsync_directory',side_effect=sync):W.durable_mkdir(path)
            self.assertEqual(events,[path,path.parent])
    def test_directory_sync_failure_prevents_START_and_test_open(self):
        go={'run_id':'SYNTHETIC_RUN_ONLY'}
        with tempfile.TemporaryDirectory(dir=W.ROOT) as td:
            root=Path(td);marker=root/'synthetic_state'/'SYNTHETIC_START.json'
            with mock.patch.object(W,'ROOT',root),mock.patch.object(W,'GLOBAL_TEST_START',marker),mock.patch.object(W,'apply_limits',return_value={}),mock.patch.object(W,'authorize_go',return_value=(root,go,0)),mock.patch.object(W,'load_frozen_model',return_value=self.model),mock.patch.object(W,'fsync_directory',side_effect=OSError('synthetic fsync failure')),mock.patch.object(W,'write_run_output',side_effect=AssertionError('START forbidden')),mock.patch.object(W,'evaluate_after_start',side_effect=AssertionError('TEST forbidden')):
                with self.assertRaisesRegex(OSError,'synthetic fsync failure'):W.run(root,'4'*64)
            self.assertFalse(marker.exists())
    def test_original_counts_must_be_integer(self):
        self.args[3]['projection_receipt']['original_review_row_counts']['a']=384.0
        with self.assertRaisesRegex(C.ContractError,'row_counts'):self.validate()

    def test_run_claim_precedes_any_test_read_and_failure_is_closed(self):
        events=[]
        go={'run_id':'SYNTHETIC_RUN_ONLY','package_manifest_sha256':'1'*64,'protocol_sha256':'2'*64,'code_sha256':{},'input_sha256':{}}
        with tempfile.TemporaryDirectory(dir=W.ROOT) as td:
            root=Path(td);marker=root/'synthetic_state'/'SYNTHETIC_START.json'
            def write(p,obj):events.append(Path(p).name);return '3'*64
            def evaluation(*args):
                self.assertEqual(events,['SYNTHETIC_START.json']);events.append('SIMULATED_TEST_READ');raise C.ContractError('synthetic deliberate interruption')
            with mock.patch.object(W,'ROOT',root),mock.patch.object(W,'GLOBAL_TEST_START',marker),mock.patch.object(W,'apply_limits',return_value={}),mock.patch.object(W,'authorize_go',return_value=(root,go,0)),mock.patch.object(W,'load_frozen_model',return_value=self.model),mock.patch.object(W,'write_run_output',side_effect=write),mock.patch.object(W,'evaluate_after_start',side_effect=evaluation):
                with self.assertRaisesRegex(C.ContractError,'synthetic deliberate'):W.run(root,'4'*64)
            self.assertEqual(events,['SYNTHETIC_START.json','SIMULATED_TEST_READ','FAILED.json']);self.assertFalse(marker.exists());self.assertFalse((root/'synthetic_state'/'TEST_COMPLETE.json').exists())

    def terminal_fixture(self,root,*,completion_sync_error=False):
        go={'run_id':'SYNTHETIC_RUN_ONLY','package_manifest_sha256':'1'*64,'protocol_sha256':'2'*64,'code_sha256':{},'input_sha256':{}}
        marker=root/'run_state'/'SYNTHETIC_START.json';actual_write=W.write_run_output
        def synthetic_write(path,obj):
            obj=dict(obj,schema='synthetic-mock-artifact/v1',synthetic_only=True)
            sha=actual_write(path,obj)
            if completion_sync_error and Path(path).name=='TEST_COMPLETE.json':raise OSError('synthetic completion directory fsync failure')
            return sha
        value=('3'*64,{}, {'family_support':{'test':{}},'exclusions':{}},{})
        from contextlib import ExitStack
        stack=ExitStack()
        for name,value2 in (('ROOT',root),('GLOBAL_TEST_START',marker)):
            stack.enter_context(mock.patch.object(W,name,value2))
        for name,value2 in (('apply_limits',{}),('authorize_go',(root,go,0)),('load_frozen_model',self.model),('evaluate_after_start',value)):
            stack.enter_context(mock.patch.object(W,name,return_value=value2))
        stack.enter_context(mock.patch.object(W,'write_run_output',side_effect=synthetic_write))
        return stack
    def test_completion_fsync_error_is_failure_even_if_complete_bytes_exist(self):
        with tempfile.TemporaryDirectory(dir=W.ROOT) as td:
            root=Path(td)
            with self.terminal_fixture(root,completion_sync_error=True),mock.patch('builtins.print',side_effect=AssertionError('must not report success')):
                with self.assertRaisesRegex(OSError,'completion directory fsync'):W.run(root,'4'*64)
            self.assertTrue((root/'run_state'/'TEST_COMPLETE.json').exists());self.assertTrue((root/'runs'/'SYNTHETIC_RUN_ONLY'/'FAILED.json').exists())
    def test_broken_stdout_does_not_retroactively_fail_durable_complete(self):
        with tempfile.TemporaryDirectory(dir=W.ROOT) as td:
            root=Path(td)
            with self.terminal_fixture(root),mock.patch('builtins.print',side_effect=BrokenPipeError('synthetic closed stdout')):W.run(root,'4'*64)
            self.assertTrue((root/'run_state'/'TEST_COMPLETE.json').exists());self.assertFalse((root/'runs'/'SYNTHETIC_RUN_ONLY'/'FAILED.json').exists())

    def test_no_fitter_editor_or_generator_in_inference_module(self):
        self.assertFalse(hasattr(C,'fit'));self.assertFalse(hasattr(C,'edit'));self.assertFalse(hasattr(C,'scale_fit'))
        tree=ast.parse((W.ROOT/'test_evaluator.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):self.assertNotIn(node.func.attr,('fit','edit','generate','scale_fit'))
    def test_feature_functions_match_frozen_public_source(self):
        old=ast.parse((W.FIT_ROOT/'controller_v03.py').read_text());new=ast.parse((W.ROOT/'inference_core.py').read_text())
        extract=lambda tree,name:ast.dump(next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name==name),include_attributes=False)
        for name in ('features','scaled','softmax','canonical','digest'):self.assertEqual(extract(old,name),extract(new,name))

if __name__=='__main__':unittest.main()
