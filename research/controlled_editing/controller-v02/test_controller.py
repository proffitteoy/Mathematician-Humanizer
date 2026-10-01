import copy,json,math,tempfile,unittest
from pathlib import Path
from controller import *


def fixture_rows():
    rows=[]
    for family in range(4):
        for c,name in enumerate(CONDITIONS):
            v=[0.]*len(FEATURES);v[0]=family*.01;v[2]=10 if c<2 else 40;v[3]=2 if c<2 else 20;v[10]=.05 if c%2==0 else .8;v[11]=v[10]+.1
            rows.append({'id':f'{family}:{c}','family':f'fixture-family{family}','partition':'train','condition':name,'meaning_verified':True,'realized_condition_verified':True,'features':v})
    return rows


class Generator:
    profile={'name':'synthetic-candidate-fixture','version':'1'}
    def __init__(self,candidates):self.candidates=candidates;self.calls=0
    def generate(self,text,target,k):self.calls+=1;return self.candidates


def receipt(source,candidate):
    return {'source_sha256':text_hash(source),'candidate_sha256':text_hash(candidate),'decision':'pass','reviewer_profile':'independent_preservation_review/v1','review_id':'synthetic-review-only','checks':['facts','negation','modality','quantifiers','scope']}


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'weights.json';self.model=fit(fixture_rows(),[],provenance='synthetic_fixture',epochs=200);self.h=save_checkpoint(self.model,self.path)
        self.claim='记录让交接更清楚。';parts=[('这是合成测试的普通说明文字用于检查接口与权重读取，内容本身不代表任何真实研究结果。')]*5
        self.source=''.join(parts)+self.claim
        self.texts=[self.claim+''.join(parts),parts[0]+self.claim+''.join(parts[1:]),''.join(parts[:3])+self.claim+''.join(parts[3:]),self.source]
        cs=[{'text':t,'semantic_review':receipt(self.source,t)} for t in self.texts];self.gen=Generator(cs)
        self.limits=EditLimits(str(self.path),self.h,'general_explanation',self.claim,[],self.gen,digest(self.gen.profile),frozenset(digest(c['semantic_review']) for c in cs),'synthetic_test')
    def tearDown(self):self.temp.cleanup()
    def test_actual_gradient_fit_not_handpicked(self):
        self.assertTrue(any(abs(v)>0 for row in self.model['condition_weights'] for v in row));self.assertEqual(self.model['training']['status'],'completed_actual_gradient_fit')
    def test_checkpoint_roundtrip(self):self.assertEqual(load_checkpoint(self.path,self.h),self.model)
    def test_feature_mainpoint_whitespace_not_position_cheat(self):
        t='甲。主旨。乙。';a=t.index('主旨');x=features(t,[a,a+2]);s=' \n甲。  主旨。乙。 ';b=s.index('主旨');y=features(s,[b,b+2]);self.assertEqual(x[-2:],y[-2:])
    def test_saved_model_drives_actual_edit(self):
        r=edit(self.source,'short_early',self.limits);self.assertEqual(r['status'],'selected');self.assertEqual(r['text'],self.texts[0]);self.assertEqual(r['checkpoint_sha256'],self.h)
    def test_candidate_order_invariance(self):
        a=edit(self.source,'short_early',self.limits);self.gen.candidates.reverse();b=edit(self.source,'short_early',self.limits);self.assertEqual(a,b)
    def test_synthetic_checkpoint_blocked_in_empirical_mode(self):
        self.limits.mode='empirical';r=edit(self.source,'short_early',self.limits);self.assertEqual(r['reason'],'synthetic_checkpoint_not_for_empirical_editing');self.assertEqual(self.gen.calls,0)
    def test_changed_checkpoint_fails_closed(self):
        self.path.write_text('{}');r=edit(self.source,'short_early',self.limits);self.assertEqual(r['reason'],'checkpoint_file_hash_mismatch')
    def test_unknown_condition_refused_before_generator(self):
        self.assertEqual(edit(self.source,'human_style',self.limits)['reason'],'unsupported_condition');self.assertEqual(self.gen.calls,0)
    def test_unsupported_genre_refusal(self):
        self.limits.genre='legal_advice';self.assertEqual(edit(self.source,'short_early',self.limits)['reason'],'unsupported_genre')
    def test_long_text_refusal(self):self.assertEqual(edit(self.source*4,'short_early',self.limits)['reason'],'unsupported_source_length')
    def test_math_quantifier_refusal(self):
        r=edit(self.source+'∀x P(x)', 'short_early', self.limits);self.assertEqual(r['reason'],'formal_math_out_of_support');self.assertEqual(self.gen.calls,0)
    def test_missing_semantic_review_abstains(self):
        self.limits.approved_semantic_review_hashes=frozenset();r=edit(self.source,'short_early',self.limits);self.assertEqual(r['status'],'abstain');self.assertEqual(r['text'],self.source)
    def test_review_tamper_not_trusted(self):
        r=self.gen.candidates[0]['semantic_review'];r['decision']='uncertain';self.assertFalse(semantic_receipt_ok(self.source,self.texts[0],r,self.limits.approved_semantic_review_hashes))
    def test_protected_names_numbers_negation_modal_quantifier(self):
        for a,b in [('甲站有3个入口。','甲站有4个入口。'),('没有改变输入。','改变输入。'),('至少需要2次核对。','需要2次核对。'),('可以提交。','必须提交。')]:self.assertFalse(mechanical_preservation(a,b,[])['mechanical_pass'])
        self.assertFalse(mechanical_preservation('甲站开放。','乙站开放。',['甲站'])['mechanical_pass'])
    def test_identical_counts_do_not_claim_semantic_guarantee(self):
        r=mechanical_preservation('甲不支持乙。','乙不支持甲。',[]);self.assertTrue(r['mechanical_pass']);self.assertFalse(r['semantic_guarantee'])
    def test_mainpoint_support_missing(self):
        self.limits.mainpoint_text='未见主旨';self.assertEqual(edit(self.source,'short_early',self.limits)['reason'],'unique_verified_mainpoint_required')
    def test_generator_profile_tamper(self):
        self.limits.generator_profile_sha256='a'*64;self.assertEqual(edit(self.source,'short_early',self.limits)['reason'],'generator_profile_changed')
    def test_fixed_candidate_count(self):
        self.gen.candidates.pop();self.assertEqual(edit(self.source,'short_early',self.limits)['reason'],'fixed_candidate_budget_required')
    def test_no_labels_in_candidate_input(self):
        self.gen.candidates[0]['preference_label']=1;self.assertEqual(edit(self.source,'short_early',self.limits)['reason'],'candidate_fields_only_no_labels')
    def test_train_only_transforms(self):
        rows=fixture_rows();rows[-1]['partition']='test'
        with self.assertRaisesRegex(ContractError,'train_rows_only'):fit(rows,[],provenance='synthetic_fixture')
    def test_real_labels_and_authority_required(self):
        with self.assertRaisesRegex(ContractError,'GO_required'):fit(fixture_rows(),[],provenance='assistant_authored_controlled')
        rows=fixture_rows();rows[0]['realized_condition_verified']=False
        with self.assertRaisesRegex(ContractError,'realized_labels'):fit(rows,[],provenance='synthetic_fixture')
    def test_constant_feature_zero_after_scaling(self):
        t=scale_fit([[1/3]*len(FEATURES)]*3);self.assertTrue(all(t['constant']));self.assertEqual(scaled([1/3]*len(FEATURES),t),[0.]*len(FEATURES)+[1.])
    def test_same_family_preference_required(self):
        pair={'better':'0:0','worse':'1:0','target':'short_early','independently_reviewed':True}
        with self.assertRaisesRegex(ContractError,'share_content_family'):fit(fixture_rows(),[pair],provenance='synthetic_fixture')
    def test_preference_weights_really_train(self):
        pair={'better':'0:0','worse':'0:1','target':'short_early','independently_reviewed':True}
        m=fit(fixture_rows(),[pair],provenance='synthetic_fixture');self.assertTrue(any(abs(x)>0 for x in m['preference_weights'][0]))
    def test_missing_checkpoint_abstains(self):
        self.limits.checkpoint=str(Path(self.temp.name)/'absent.json');r=edit(self.source,'short_early',self.limits);self.assertEqual(r['status'],'abstain');self.assertEqual(r['reason'],'FileNotFoundError')
    def test_checkpoint_limit_checked_before_parse(self):
        self.path.write_bytes(b'x'*(1024**2+1))
        with self.assertRaisesRegex(ContractError,'size_limit'):load_checkpoint(self.path,'not-a-hash')
    def test_duplicate_checkpoint_json_rejected(self):
        raw=b'{"model":{},"model":{}}';self.path.write_bytes(raw)
        with self.assertRaisesRegex(ContractError,'duplicate_checkpoint_key'):load_checkpoint(self.path,hashlib.sha256(raw).hexdigest())
    def test_nonfinite_checkpoint_json_rejected(self):
        raw=b'{"model":NaN}';self.path.write_bytes(raw)
        with self.assertRaisesRegex(ContractError,'nonfinite_checkpoint_json'):load_checkpoint(self.path,hashlib.sha256(raw).hexdigest())
    def test_invalid_execution_mode(self):
        self.limits.mode='bypass';self.assertEqual(edit(self.source,'short_early',self.limits)['reason'],'execution_mode_invalid')
    def test_unsupported_source_structure(self):
        for text in ['# 标题\n'+self.source, '“引用”'+self.source, ('abc def. '*20)]:
            self.assertEqual(edit(text,'short_early',self.limits)['status'],'abstain')
        self.assertEqual(self.gen.calls,0)
    def test_v02_support_card(self):
        self.assertEqual(self.model['support']['min_source_codepoints'],120);self.assertEqual(self.model['support']['max_source_codepoints'],400)
    def test_no_overwrite_checkpoint(self):
        with self.assertRaises(FileExistsError):save_checkpoint(self.model,self.path)

if __name__=='__main__':unittest.main()
