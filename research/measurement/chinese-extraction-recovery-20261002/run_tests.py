#!/usr/bin/env python3
"""Model-free restored instrument + extraction-wrapper tests; no corpus bodies."""
import io,json,os,pathlib,sys,tempfile,unittest
from types import SimpleNamespace as NS
ROOT=pathlib.Path(__file__).resolve().parents[1];REST=ROOT.parent/'chinese-linguistic-restoration-20261002';REPO=REST/'repo'
sys.path[:0]=[str(ROOT/'public'),str(REPO/'src'),str(REPO),str(REPO/'tests')]
import extract as ex
from research.linguistic.stanza_local import LocalStanza
from research.linguistic.fixtures import annotated,BASIC
from research.linguistic.adapter import ratio
ex.offline()
class WrapperChecks(unittest.TestCase):
    def record(self,text='甲。乙。'):
        raw={'source':'web','source_ID':'synthetic_only','prompt':'人工合成测试','human_text':text,'machine_text':text,'model':'chatgpt'}
        f=json.dumps(['web','str','synthetic_only'],ensure_ascii=False,separators=(',',':'))
        b=ex.serial(raw)+b'\n'; support={'status':'present','chars':len(text),'sentences':2,'block_spans':[[0,len(text)]],'original_text_sha256':ex.digest(text)}
        r={'split':'train','fit_eligible_arms':['human','chatgpt'],'question_family_id':f,'source':'web','source_ID':'synthetic_only',
          'pair_id':ex.digest(json.dumps([f,raw['prompt'],text],ensure_ascii=False,separators=(',',':'))),'prompt_sha256':ex.digest(raw['prompt']),
          'raw_rows':{'chatgpt':{'file':'qazh_chatgpt.jsonl','offset_bytes':11,'length_bytes':len(b),'line':2}},'arms':{'human':support,'chatgpt':support},
          'component_id':'synthetic_only','inference_cluster':'synthetic_only','question_family_answer_count':1,'equal_question_family_answer_weight':1.0,'authorship_status':'synthetic_fixture'}
        return r,raw,b
    def parser(self):
        p=object.__new__(LocalStanza);p.profile=annotated([BASIC])[2].profile
        def pipeline(text):
            return NS(sentences=[NS(words=[NS(id=i+1,text=c,upos='PUNCT' if c=='。' else 'NOUN',head=0 if i==0 else 1,deprel='root' if i==0 else 'punct',start_char=i,end_char=i+1,feats=None) for i,c in enumerate(text)])])
        p.pipeline=pipeline;return p
    def test_exact_byte_only_read(self):
        r,raw,b=self.record()
        class GuardStream(io.BytesIO):
            def read(self,size=-1):
                assert size==len(b) and self.tell()==11
                return super().read(size)
        got,loc=ex.read_approved_row(GuardStream(b'PRIVATEPAD!'+b+b'TESTBODY_MUST_NOT_READ'),r)
        self.assertEqual(got,raw);self.assertEqual(loc['length_bytes'],len(b))
    def test_test_row_blocked_before_read(self):
        r,_,b=self.record();r['split']='test'
        with self.assertRaisesRegex(AssertionError,'unauthorized_row'):ex.read_approved_row(io.BytesIO(b),r)
    def test_raw_model_mismatch_blocked(self):
        r,raw,b=self.record();raw['model']='davinci';bad=ex.serial(raw)+b'\n';r['raw_rows']['chatgpt']['length_bytes']=len(bad)
        with self.assertRaises(AssertionError):ex.read_approved_row(io.BytesIO(b'PRIVATEPAD!'+bad),r)
    def test_pilot_deterministic_family_selection(self):
        rows=[]
        for i in range(40):
            for j in range(2):rows.append({'split':'train' if i<30 else 'dev','question_family_id':str(i),'pair_id':str(j)})
        a=ex.select_pilot(rows);b=ex.select_pilot(list(reversed(rows)))
        self.assertEqual(a,b);self.assertEqual(len(a),20);self.assertEqual(len({r['question_family_id'] for r in a}),20)
        self.assertTrue(all(r['split']=='train' and r['pair_id']=='0' for r in a))
    def test_typed_zero_not_missing(self):
        self.assertEqual(ratio(0,3)['status'],'zero_observed');self.assertIsNone(ratio(0,0)['value']);self.assertEqual(ratio(0,0)['denominator'],0)
    def test_all_channels_flags_and_structure(self):
        r,raw,_=self.record();x=ex.extract_arm(r,'human',raw['human_text'],{},self.parser(),'a'*64)
        self.assertIsNone(x['source_failure']);self.assertEqual(len(x['bundle']['target']['global_measurements']),71)
        self.assertEqual([u['structure.source_sentence_span_codepoints'] for u in x['structural_units']],[2,2])
        self.assertEqual([u['structure.lexical_token_count'] for u in x['structural_units']],[1,1])
        self.assertTrue(all(u['frozen_blank_line_block_memberships']==[0] for u in x['structural_units']))
        self.assertFalse(x['bundle']['empirical_model_admitted']);self.assertEqual(x['bundle']['measurement_status'],'candidate_unvalidated')
        self.assertEqual(x['original_writer_paragraph_view']['missing_reason'],'original_writer_layout_unsupported_unknown')
        self.assertEqual(x['discourse_graph']['missing_reason'],'no_validated_M4_producer')
    def test_resource_failure_preserved_without_truncation(self):
        r,raw,_=self.record('甲'*2049+'。');x=ex.extract_arm(r,'human',raw['human_text'],{},self.parser(),'a'*64)
        self.assertEqual(len(x['structural_units']),1);self.assertIsNone(x['structural_units'][0]['structure.lexical_token_count'])
        self.assertTrue(all(v['value'] is None and v['opportunities'] is None and v['missing_reason']=='resource_limit' for v in x['bundle']['target']['global_measurements'].values()))
    def test_whole_source_failure_preserved(self):
        r,raw,_=self.record('甲'*200001);x=ex.extract_arm(r,'human',raw['human_text'],{},self.parser(),'a'*64)
        self.assertEqual(x['source_failure']['reason'],'source_resource_limit');self.assertEqual(len(x['failure_global_measurements']),71)
loader=unittest.TestLoader()
base=unittest.TestSuite([loader.loadTestsFromNames(['research.linguistic.test_adapter','research.linguistic.test_stanza_local','research.surface.test_adapter','research.linguistic.independent_checks']),loader.discover(str(REPO/'tests'))])
r=unittest.TextTestRunner(verbosity=1).run(base)
w=unittest.TextTestRunner(verbosity=2).run(loader.loadTestsFromTestCase(WrapperChecks))
receipt={'tests_run':r.testsRun+w.testsRun,'restored_tests_run':r.testsRun,'wrapper_tests_run':w.testsRun,
 'failures':len(r.failures)+len(w.failures),'errors':len(r.errors)+len(w.errors),
 'skips':[{'test':str(t),'reason':reason} for t,reason in r.skipped+w.skipped],
 'success':r.wasSuccessful() and w.wasSuccessful(),'wrapper_tests_success':w.wasSuccessful(),'model_free':True,'corpus_bodies_read':0}
ex.write_json(ROOT/'public/model_free_receipt.json',receipt);print(json.dumps(receipt),flush=True)
raise SystemExit(0 if receipt['success'] else 1)
