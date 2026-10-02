import copy,json,sys,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'scripts'))
from analyze import discover_research
from workflow import Analyzer,binding,check_review,mechanical_checks,finalize,validate_job,diagnose

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.job={'schema_version':'writing-job/0.1','id':'unit','original':'请求可能失败。超时不等于失败。','genre':'technical_commentary',
          'claims':[{'id':'a','commitment':'可能失败','source_evidence':'请求可能失败。'},{'id':'b','commitment':'超时不等于失败','source_evidence':'超时不等于失败。'}],
          'protected':['超时不等于失败'],'candidates':[{'id':'one','text':'请求可能失败。\n超时不等于失败。'}],'selection_preference':['one']}
        c=self.job['candidates'][0]
        c['review']={'reviewer_type':'independent_language_model','verdict':'pass','issues':[],'added_claims':[],
         'claims':[{'id':'a','status':'preserved','candidate_evidence':['请求可能失败。'],'explanation':'same modality'},
                   {'id':'b','status':'preserved','candidate_evidence':['超时不等于失败。'],'explanation':'same negation'}]}
        c['review']['binding_sha256']=binding(self.job,c)
        self.a=Analyzer()
    def test_complete_job_produces_selected_text(self):
        r=finalize(self.job,self.a);self.assertEqual(r['status'],'reviewed_candidate_for_user_test');self.assertEqual(r['final_text'],self.job['candidates'][0]['text'])
    def test_missing_review_abstains_and_retains_original(self):
        self.job['candidates'][0].pop('review');r=finalize(self.job,self.a);self.assertEqual(r['status'],'abstained');self.assertIsNone(r['final_text']);self.assertEqual(r['rollback_text'],self.job['original'])
    def test_stale_review_after_edit_is_rejected(self):
        c=self.job['candidates'][0];c['text']+='还有其他风险。';self.assertEqual(check_review(self.job,c,c['review'])['status'],'fail')
    def test_changed_ledger_invalidates_binding(self):
        c=self.job['candidates'][0];self.job['claims'][0]['commitment']='必然失败';self.assertEqual(check_review(self.job,c,c['review'])['status'],'fail')
    def test_missing_protected_negation_fails(self):
        c=self.job['candidates'][0];c['text']=c['text'].replace('不等于','等于');self.assertEqual(mechanical_checks(self.job,c)['status'],'fail')
    def test_changed_number_detected(self):
        self.job['original']='等待10秒。';c={'text':'等待20秒。'};self.job['protected']=[];self.assertEqual(mechanical_checks(self.job,c)['issues'][0]['code'],'numeric_inventory_changed')
    def test_new_anecdote_cue_detected(self):
        c=self.job['candidates'][0];c['text']+='我曾亲眼见过。';self.assertTrue(any(i['code']=='new_personal_anecdote_cue' for i in mechanical_checks(self.job,c)['issues']))
    def test_new_url_detected(self):
        c=self.job['candidates'][0];c['text']+=' https://example.com';self.assertTrue(any(i['code']=='new_url' for i in mechanical_checks(self.job,c)['issues']))
    def test_review_must_cover_all_claims(self):
        c=self.job['candidates'][0];c['review']['claims'].pop();self.assertEqual(check_review(self.job,c,c['review'])['status'],'fail')
    def test_invented_evidence_fails(self):
        c=self.job['candidates'][0];c['review']['claims'][0]['candidate_evidence']=['不存在'];self.assertEqual(check_review(self.job,c,c['review'])['status'],'fail')
    def test_changed_semantic_claim_rejected_even_if_lexical_checks_pass(self):
        c=self.job['candidates'][0];c['text']=c['text'].replace('可能','一定');self.assertEqual(mechanical_checks(self.job,c)['status'],'pass')
        c['review']['binding_sha256']=binding(self.job,c);c['review']['verdict']='fail';c['review']['claims'][0].update(status='changed',candidate_evidence=['请求一定失败。'])
        self.assertEqual(finalize(self.job,self.a)['status'],'abstained')
    def test_nonblocking_rhetorical_warning_does_not_masquerade_as_error(self):
        c=self.job['candidates'][0];c['review']['issues']=[{'blocking':False,'explanation':'A human may prefer a different rhythm'}]
        self.assertEqual(check_review(self.job,c,c['review'])['status'],'pass')
    def test_blocking_issue_prevents_selection(self):
        c=self.job['candidates'][0];c['review']['issues']=[{'blocking':True,'explanation':'Lost scope'}];self.assertEqual(finalize(self.job,self.a)['status'],'abstained')
    def test_unquoted_source_evidence_rejected(self):
        self.job['claims'][0]['source_evidence']='invented source';self.assertRaises(ValueError,validate_job,self.job)
    def test_missing_parser_is_explicit(self):
        a=self.a.analyze('一个句子。');self.assertEqual(a['linguistic']['status'],'unavailable');self.assertIsNone(a['quality_score']);self.assertIsNone(a['human_probability'])
    def test_source_order_is_retained(self):
        a=self.a.analyze(self.job['original']);d=diagnose(self.job['original'],self.job['genre'],a)
        self.assertEqual([s['text'] for s in d['ordered_source_units']],['请求可能失败。','超时不等于失败。'])
    def test_tampered_cached_measurement_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            a=self.a.analyze('其他内容。');Path(folder,'unit.original.json').write_text(json.dumps(a))
            self.assertRaises(ValueError,finalize,self.job,self.a,folder)
    def test_unknown_selection_id_rejected(self):
        self.job['selection_preference']=['missing'];self.assertRaises(ValueError,finalize,self.job,self.a)
    def test_wrong_formula_fails_exact_protection(self):
        self.job['original']='对所有 n≥N，|a_n-L|<ε。';self.job['protected']=['n≥N','|a_n-L|<ε']
        self.assertEqual(mechanical_checks(self.job,{'text':'对所有 n≥N，|a_n-L|>ε。'})['status'],'fail')
    def test_discovers_repo_when_skill_is_nested(self):
        with tempfile.TemporaryDirectory() as folder:
            repo=Path(folder)/'checkout';(repo/'research/linguistic').mkdir(parents=True);(repo/'src/style_compiler').mkdir(parents=True)
            (repo/'research/linguistic/adapter.py').write_text('# marker')
            nested=repo/'skills/style-writing-prototype';nested.mkdir(parents=True)
            self.assertEqual(discover_research(nested),repo)
    def test_standalone_research_sibling_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            skill=Path(folder)/'prototype';skill.mkdir()
            self.assertEqual(discover_research(skill),Path(folder)/'style-compiler')
    def test_compact_measurements_bind_exact_demo_texts(self):
        from analyze import sha
        for f in (P/'examples').glob('*.json'):
            j=json.loads(f.read_text())
            for variant,text in [('original',j['original'])]+[(c['id'],c['text']) for c in j['candidates']]:
                a=json.loads((P/'measurements-compact'/f'{j["id"]}.{variant}.json').read_text())
                self.assertEqual(a['text_sha256'],sha(text));self.assertRegex(a['full_bundle']['sha256'],r'^[0-9a-f]{64}$')
    def test_compact_summaries_explicitly_omit_raw_graphs_and_vectors(self):
        for f in (P/'measurements-compact').glob('*.json'):
            a=json.loads(f.read_text());self.assertEqual(a['artifact_form'],'compact_measurement_summary_not_full_analysis');self.assertFalse(a['full_bundle']['included_in_publication'])
            self.assertNotIn('graph',a['linguistic']['bundle']['target'])
            for row in a['linguistic']['bundle']['target']['sequence']:self.assertNotIn('vector',row)
    def test_compact_global_values_match_reported_summary(self):
        for f in (P/'measurements-compact').glob('*.json'):
            a=json.loads(f.read_text());values=a['linguistic']['bundle']['target']['global_measurements'];self.assertEqual(len(values),71)
            self.assertEqual(a['summary']['linguistic_values'],{k:v['value'] for k,v in values.items()})
    def test_all_demo_jobs_have_selected_repaired_results(self):
        for f in (P/'examples').glob('*.json'):
            j=json.loads(f.read_text());r=finalize(j,self.a,P/'measurements-compact');self.assertEqual(r['selected_candidate_id'],'repaired',f.name)
            self.assertIsNone(r['quality_score'])

if __name__=='__main__':unittest.main()
