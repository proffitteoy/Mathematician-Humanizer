"""Synthetic fixtures only. Never opens empirical data or creates root GO."""
import copy, datetime as dt, hashlib, json, tempfile, unittest
from unittest import mock
from pathlib import Path
import controller_v03 as C
import labels_v02 as L
import fit_wrapper as W


def toy_text(condition,variant=0):
    mainpoint='记录让交接更清楚'
    short=['这是明确标记的合成接口测试句不涉及实际人物']*7
    mixed=['这是合成短句','这是明确标记的合成接口测试文字仅为检查软件流程而设计并不来自任何实际成文或真实研究记录不含实验观测结果','这是合成测试中的另一个较长句子用来改变句长分布所有相同文字都只代表单元测试夹具不可作为实证研究证据','这是普通测试句用于检查结尾位置']
    parts=short if condition.startswith('short') else mixed
    parts=([mainpoint]+parts) if condition.endswith('early') else (parts+[mainpoint])
    return '。'.join(parts)+'。',mainpoint


def fixtures():
    data={'schema':'sanitized-controlled-train-dev/v1','provenance':'synthetic_fixture','source_draft_manifest_sha256':'1'*64,'family_split_manifest_sha256':'2'*64,'slots':[]}
    a={'schema':'sanitized-blind-reviews/v1','reviews':[]};b=copy.deepcopy(a)
    for f in range(40):
        partition='train' if f<32 else 'dev';genre=C.GENRES[(f if f<32 else f-32)//(8 if f<32 else 2)]
        for condition in C.CONDITIONS:
            for rep in range(2):
                rid=f'synthetic-{f}-{condition}-{rep}';text,main=toy_text(condition)
                assert L.observed_properties(text,main)['mechanical_condition']==condition
                row={'id':rid,'family':f'synthetic-family-{f}','partition':partition,'genre':genre,'status':'completed','text':text,'text_sha256':C.text_hash(text),'mainpoint_exact':main,'fact_ids':['P1','P2','P3','P4','P5','P6'],'review_id':rid,'realized_condition':condition,'exclusion_reason':None};data['slots'].append(row)
                for payload,rater in ((a,'synthetic-a'),(b,'synthetic-b')):
                    payload['reviews'].append({'review_id':rid,'rater_id':rater,'fact_labels':{k:'preserved' for k in row['fact_ids']},'semantic_axes':{k:'pass' for k in L.SEMANTIC_AXES},'mainpoint_is_real_main_claim':'yes','rhythm_label':condition.split('_')[0],'placement_label':condition.split('_')[1]})
    receipts={'schema':'dual-blind-label-receipts/v1','dataset_file_sha256':C.digest(data),'review_files_sha256':{'a':C.digest(a),'b':C.digest(b)},'raters':[],'review_scope':'all_completed_train_dev_slots_only_test_sealed'}
    for key in ('a','b'):
        receipts['raters'].append({'rater_id':'synthetic-'+key,'review_context_id':'synthetic-context-'+key,'independent_of_authoring':True,'independent_of_fit':True,'blind_to':W.BLIND_TO,'review_file_sha256':receipts['review_files_sha256'][key]})
    receipts['projection_receipt']={'schema':'root-train-dev-review-projection/v1','actor':'root','original_review_files_sha256':{'a':'3'*64,'b':'4'*64},'original_review_row_counts':{'a':384,'b':384},'subset_review_files_sha256':receipts['review_files_sha256'].copy(),'selected_review_ids':sorted(r['review_id'] for r in a['reviews']),'selected_review_ids_sha256':C.digest(sorted(r['review_id'] for r in a['reviews'])),'test_rows_exported':0}
    return data,a,b,receipts


def get_rows():
    return W.validate_data(*fixtures(),synthetic=True)


class WrapperTests(unittest.TestCase):
    def setUp(self): self.args=fixtures()
    def validate(self): return W.validate_data(*self.args,synthetic=True)
    def test_complete_support_and_denominators(self):
        v=self.validate();self.assertEqual([len(v['eligible'][p]) for p in ('train','dev')],[256,64]);self.assertEqual(set(v['family_support']['train'].values()),{32});self.assertEqual(set(v['family_support']['dev'].values()),{8})
    def test_synthetic_provenance_rejected_by_empirical_validation(self):
        with self.assertRaisesRegex(C.ContractError,'provenance'):W.validate_data(*self.args)
    def test_test_partition_rejected(self):
        self.args[0]['slots'][0]['partition']='test'
        with self.assertRaisesRegex(C.ContractError,'test_or_unknown'):self.validate()
    def test_nominal_target_cannot_enter_export(self):
        self.args[0]['slots'][0]['nominal_target']='short_early'
        with self.assertRaisesRegex(C.ContractError,'no_nominal'):self.validate()
    def test_family_leakage_rejected(self):
        self.args[0]['slots'][0]['family']=self.args[0]['slots'][-1]['family']
        with self.assertRaisesRegex(C.ContractError,'family_leakage'):self.validate()
    def test_missing_original_slot_rejected(self):
        self.args[0]['slots'].pop()
        with self.assertRaisesRegex(C.ContractError,'320'):self.validate()
    def test_text_tamper_rejected(self):
        self.args[0]['slots'][0]['text']+='甲'
        with self.assertRaisesRegex(C.ContractError,'text_hash'):self.validate()
    def test_same_rater_rejected(self):
        self.args[3]['raters'][1]['rater_id']='synthetic-a'
        with self.assertRaisesRegex(C.ContractError,'independent_raters'):self.validate()
    def test_shared_review_context_rejected(self):
        self.args[3]['raters'][1]['review_context_id']='synthetic-context-a'
        with self.assertRaisesRegex(C.ContractError,'independent_raters'):self.validate()
    def test_nonblind_receipt_rejected(self):
        self.args[3]['raters'][0]['blind_to']=[]
        with self.assertRaisesRegex(C.ContractError,'blind_receipt'):self.validate()
    def test_wrong_actual_label_rejected(self):
        self.args[0]['slots'][0]['realized_condition']='mixed_late'
        with self.assertRaisesRegex(C.ContractError,'actual_label'):self.validate()
    def test_disagreement_is_excluded_not_relabelled(self):
        self.args[2]['reviews'][0]['rhythm_label']='uncertain';self.args[0]['slots'][0]['realized_condition']=None;self.args[0]['slots'][0]['exclusion_reason']='synthetic_rater_uncertainty'
        v=self.validate();self.assertEqual(len(v['eligible']['train']),255);self.assertEqual(v['exclusions']['dual_review_or_support_excluded'],1)
    def test_semantic_failure_is_excluded(self):
        self.args[1]['reviews'][0]['semantic_axes']['scope']='fail';self.args[0]['slots'][0]['realized_condition']=None;self.args[0]['slots'][0]['exclusion_reason']='synthetic_scope_failure'
        self.assertEqual(len(self.validate()['eligible']['train']),255)
    def test_realized_condition_is_not_nominal_request(self):
        # Replace one short/early fixture by a mixed/late fixture and label its
        # actual properties. There is no requested target field to recover.
        row=self.args[0]['slots'][0];text,main=toy_text('mixed_late');row.update(text=text,text_sha256=C.text_hash(text),mainpoint_exact=main,realized_condition='mixed_late')
        for p in self.args[1:3]:p['reviews'][0].update(rhythm_label='mixed',placement_label='late')
        self.assertEqual(self.validate()['eligible']['train'][0]['condition'],'mixed_late')
    def test_minimum_train_support_fail_closed(self):
        for i,row in enumerate(self.args[0]['slots']):
            if row['partition']=='train' and row['realized_condition']=='short_early' and int(row['family'].split('-')[-1])>=15:
                row['realized_condition']=None;row['exclusion_reason']='synthetic_uncertain';self.args[1]['reviews'][i]['rhythm_label']='uncertain'
        with self.assertRaisesRegex(C.ContractError,'insufficient_train'):self.validate()
    def test_minimum_dev_support_fail_closed(self):
        for i,row in enumerate(self.args[0]['slots']):
            if row['partition']=='dev' and row['realized_condition']=='short_early' and int(row['family'].split('-')[-1])>=35:
                row['realized_condition']=None;row['exclusion_reason']='synthetic_uncertain';self.args[1]['reviews'][i]['rhythm_label']='uncertain'
        with self.assertRaisesRegex(C.ContractError,'insufficient_dev'):self.validate()
    def test_missing_review_rejected(self):
        self.args[1]['reviews'].pop()
        with self.assertRaisesRegex(C.ContractError,'coverage'):self.validate()
    def test_failure_retains_slot_denominator(self):
        row=self.args[0]['slots'][0];rid=row['review_id'];row.update(status='technical_failed',text=None,text_sha256=None,mainpoint_exact=None,fact_ids=[],review_id=None,realized_condition=None,exclusion_reason='synthetic failure')
        for p in self.args[1:3]:p['reviews']=[x for x in p['reviews'] if x['review_id']!=rid]
        selected=sorted(x['review_id'] for x in self.args[1]['reviews']);self.args[3]['projection_receipt']['selected_review_ids']=selected;self.args[3]['projection_receipt']['selected_review_ids_sha256']=C.digest(selected)
        v=self.validate();self.assertEqual(len(v['all_slots']['train']),256);self.assertEqual(len(v['eligible']['train']),255)
    def test_projection_exact_subset_ids_required(self):
        self.args[3]['projection_receipt']['selected_review_ids'][0]='synthetic-unknown'
        with self.assertRaisesRegex(C.ContractError,'projection_selected'):self.validate()
    def test_original_review_paths_cannot_enter_projection(self):
        self.args[3]['projection_receipt']['original_path']='/forbidden/source.json'
        with self.assertRaisesRegex(C.ContractError,'projection_receipt_schema'):self.validate()
    def test_projection_rejects_exported_test_rows(self):
        self.args[3]['projection_receipt']['test_rows_exported']=1
        with self.assertRaisesRegex(C.ContractError,'test_rows_forbidden'):self.validate()
    def test_projection_subset_hash_binding(self):
        self.args[3]['projection_receipt']['subset_review_files_sha256']['a']='0'*64
        with self.assertRaisesRegex(C.ContractError,'projection_subset_hash'):self.validate()
    def test_json_duplicate_nonfinite_rejected(self):
        for text in ('{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}'):
            with self.assertRaises(C.ContractError):W.strict_json(text)
    def test_checkpoint_and_marker_cannot_overwrite(self):
        with tempfile.TemporaryDirectory(dir=W.ROOT) as temp:
            p=Path(temp)/'marker.json';W.write_once(p,{'fixture':True})
            with self.assertRaises(FileExistsError):W.write_once(p,{'fixture':False})
    def test_symlink_input_rejected(self):
        with tempfile.TemporaryDirectory(dir=W.ROOT) as temp:
            p=Path(temp)/'x';p.write_text('{}');q=Path(temp)/'y';q.symlink_to(p)
            with self.assertRaisesRegex(C.ContractError,'symlink'):W.safe_bytes(q,100)
    def test_storage_cap_is_enforced_without_private_reads(self):
        receipt={'schema':'controlled-artifact-budget-receipt/v1','actor':'root','measured_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'excluded_root':str(W.ROOT),'external_controlled_bytes':W.LIMIT,'controlled_byte_cap':W.LIMIT,'exclusive_budget_reservation':True,'reserved_output_bytes':W.OUTPUT_RESERVE,'no_other_controlled_writes_until_release':True}
        with self.assertRaisesRegex(C.ContractError,'cap_exceeded'):W.verify_storage(receipt,{})
        receipt['external_controlled_bytes']=0;self.assertEqual(W.verify_storage(receipt,{}),0)
        receipt['no_other_controlled_writes_until_release']=False
        with self.assertRaisesRegex(C.ContractError,'exclusive_storage'):W.verify_storage(receipt,{})
    def test_stale_budget_receipt_fails_closed(self):
        receipt={'schema':'controlled-artifact-budget-receipt/v1','actor':'root','measured_at_utc':'2000-01-01T00:00:00+00:00','excluded_root':str(W.ROOT),'external_controlled_bytes':0,'controlled_byte_cap':W.LIMIT,'exclusive_budget_reservation':True,'reserved_output_bytes':W.OUTPUT_RESERVE,'no_other_controlled_writes_until_release':True}
        with self.assertRaisesRegex(C.ContractError,'stale'):W.verify_storage(receipt,{})
    def test_fixed_input_hash_checked_before_json_or_corpus(self):
        with tempfile.TemporaryDirectory(dir=W.ROOT) as temp:
            p=Path(temp)/'ROOT_GO.json';p.write_text('SYNTHETIC INVALID AUTHORITY, MUST NOT PARSE')
            with self.assertRaisesRegex(C.ContractError,'root_GO_file_hash_mismatch'):W.read_authorized_inputs(temp,'0'*64)
    def test_no_root_hash_no_input_read(self):
        with self.assertRaisesRegex(C.ContractError,'explicit_expected'):W.read_authorized_inputs('/does/not/exist',None)


class CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v=get_rows();cls.rows=cls.v['eligible']['train'];cls.model=C.fit(cls.rows,[],provenance='synthetic_fixture',epochs=150,lr=.05)
    def test_one_actual_fit_gradient_replay_u_zero(self):
        r=W.gradient_replay(self.rows,self.model);self.assertGreater(r['first_gradient_l2'],0);self.assertLessEqual(r['max_abs_weight_replay_error'],1e-12);self.assertTrue(r['preference_weights_exact_zero'])
    def test_altered_weights_fail_replay(self):
        m=copy.deepcopy(self.model);m['condition_weights'][0][0]+=.01
        with self.assertRaisesRegex(C.ContractError,'replay_mismatch'):W.gradient_replay(self.rows,m)
    def test_dev_extremes_never_affect_scaler(self):
        expected=C.scale_fit([r['features'] for r in self.rows]);dev=copy.deepcopy(self.v['eligible']['dev']);dev[0]['features']=[1e20]*12
        W.family_metrics(self.model,dev,self.v['all_slots']['dev']);self.assertEqual(self.model['transform'],expected)
    def test_metrics_family_macro_and_coverage(self):
        eligible=self.rows[1:];m=W.family_metrics(self.model,eligible,self.v['all_slots']['train'])
        self.assertEqual(m['all_slots'],256);self.assertEqual(m['eligible_rows'],255);self.assertAlmostEqual(m['family_macro_coverage_over_all_original_slots'],255/256);self.assertEqual(m['exact_threshold_rule']['family_macro_accuracy_on_eligible'],1)
    def test_threshold_comparator_recomputes_text_not_provided_label(self):
        rows=copy.deepcopy(self.rows);rows[0]['condition']='mixed_late'
        metrics=W.family_metrics(self.model,rows,self.v['all_slots']['train'])
        self.assertLess(metrics['exact_threshold_rule']['family_macro_accuracy_on_eligible'],1)
    def test_family_macro_is_not_pooled_rows(self):
        rows=copy.deepcopy(self.rows)
        # Leave one family with a single row, all other families with eight.
        rows=[r for i,r in enumerate(rows) if i==0 or r['family']!=rows[0]['family']]
        metrics=W.family_metrics(self.model,rows,self.v['all_slots']['train'])
        components=metrics['by_family'];expected=sum(v['ce']/v['eligible'] for v in components.values())/32
        self.assertAlmostEqual(metrics['family_macro_cross_entropy_on_eligible'],expected)
    def test_saved_checkpoint_drives_edit_and_strict_candidate_schema(self):
        main='记录让交接更清楚';source,_=toy_text('mixed_late');target,_=toy_text('mixed_early')
        # Same sentences, different ordering. Review is fixture-only.
        parts=source[:-1].split('。');other='。'.join([parts[0],parts[-1]]+parts[1:-1])+'。';fourth='。'.join(parts[:2]+[parts[-1]]+parts[2:-1])+'。';texts=[target,other,fourth,source]
        def receipt(t):return {'source_sha256':C.text_hash(source),'candidate_sha256':C.text_hash(t),'decision':'pass','reviewer_profile':'independent_preservation_review/v1','review_id':'synthetic-fixture-only','checks':['facts','negation','modality','quantifiers','scope']}
        class Generator:
            profile={'kind':'synthetic_fixture_only'}
            def __init__(self):self.cs=[{'text':t,'semantic_review':receipt(t)} for t in texts]
            def generate(self,text,target,k):return self.cs
        gen=Generator()
        with tempfile.TemporaryDirectory(dir=W.ROOT) as temp:
            p=Path(temp)/'synthetic.weights.json';h=C.save_checkpoint(self.model,p);self.assertEqual(C.load_checkpoint(p,h),self.model)
            limits=C.EditLimits(str(p),h,'general_explanation',main,[],gen,C.digest(gen.profile),frozenset(C.digest(c['semantic_review']) for c in gen.cs),'synthetic_test')
            result=C.edit(source,'mixed_early',limits);self.assertEqual(result['status'],'selected');self.assertEqual(result['text'],target);self.assertEqual(result['checkpoint_sha256'],h)
            gen.cs.reverse();self.assertEqual(C.edit(source,'mixed_early',limits),result)
            zero=copy.deepcopy(self.model);zero['condition_weights']=[[0.]*13 for _ in range(4)];zp=Path(temp)/'synthetic-zero.weights.json';zh=C.save_checkpoint(zero,zp)
            zero_limits=copy.copy(limits);zero_limits.checkpoint=str(zp);zero_limits.checkpoint_sha256=zh
            self.assertEqual(C.edit(source,'mixed_early',zero_limits)['reason'],'insufficient_score_margin')
            gen.cs[0]['label']='mixed_early';self.assertEqual(C.edit(source,'mixed_early',limits)['reason'],'candidate_fields_only_no_labels');del gen.cs[0]['label']
            for candidate in gen.cs:candidate['semantic_review']['condition']='mixed_early'
            limits.approved_semantic_review_hashes=frozenset(C.digest(c['semantic_review']) for c in gen.cs)
            self.assertEqual(C.edit(source,'mixed_early',limits)['status'],'abstain')
    def test_nonboolean_constant_mask_rejected(self):
        model=copy.deepcopy(self.model);model['transform']['constant'][0]='false'
        with tempfile.TemporaryDirectory(dir=W.ROOT) as temp:
            p=Path(temp)/'bad.weights.json';h=C.save_checkpoint(model,p)
            with self.assertRaisesRegex(C.ContractError,'transform_invalid'):C.load_checkpoint(p,h)
    def test_synthetic_checkpoint_empirical_edit_abstains(self):
        with tempfile.TemporaryDirectory(dir=W.ROOT) as temp:
            p=Path(temp)/'synthetic.weights.json';h=C.save_checkpoint(self.model,p);source,main=toy_text('mixed_late')
            limits=C.EditLimits(str(p),h,'general_explanation',main,[],None,'',frozenset(),'empirical')
            self.assertEqual(C.edit(source,'mixed_early',limits)['reason'],'synthetic_checkpoint_not_for_empirical_editing')

if __name__=='__main__':unittest.main(verbosity=2)
