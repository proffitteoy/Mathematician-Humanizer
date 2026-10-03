"""Independent bridge regression with synthetic observations, no corpus read."""
import copy, hashlib, importlib.util, json, pathlib, sys, unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from test_contrast_independent import CANDIDATE, data
ROOT=CANDIDATE/'scripts';sys.path.insert(0,str(ROOT))
import bridge as b
import contrast as m

def evidence():
 d=data();d['measurement_identity']='surface-source-units-gap-safe/0.1.0'
 a=b.Analyzer().analyze('这是一句话。');d['measurement_profile']=a['surface']['measurement_profile'];d['measurement_profile_sha256']=a['surface']['measurement_profile_sha256']
 for row in d['rows']:row['features']={'F013':row['features']['stable']}
 model=m.fit(d,40);return {'model':model,'development_audit':m.audit(model,d)}

def job(e):
 j={'schema_version':'writing-job/0.1','id':'independent','original':'请求可能失败。超时不等于失败。','genre':'technical_commentary','claims':[{'id':'a','commitment':'可能失败','source_evidence':'请求可能失败。'},{'id':'b','commitment':'超时不等于失败','source_evidence':'超时不等于失败。'}],'protected':['超时不等于失败'],'candidates':[{'id':'one','text':'请求可能失败。\n超时不等于失败。','evidence_card_ids':['F013'],'source_problem_evidence':'请求可能失败。'}],'selection_preference':['one'],'evidence_sha256':m.digest(e),'evidence_domain':'A','domain':'A'}
 c=j['candidates'][0];c['review']={'reviewer_type':'independent_language_model','verdict':'pass','issues':[],'added_claims':[],'claims':[{'id':'a','status':'preserved','candidate_evidence':'请求可能失败。','explanation':'same modality'},{'id':'b','status':'preserved','candidate_evidence':'超时不等于失败。','explanation':'same negation'}],'ledger_completeness':'checked_no_omissions','relations_and_scope':'checked_preserved'};c['review']['binding_sha256']=b.binding(j,c);return j

class BridgeIndependentTests(unittest.TestCase):
 def setUp(self):self.e=evidence();self.j=job(self.e);self.a=b.Analyzer()
 def test_end_to_end_control(self):
  result=b.evaluate(self.j,self.a,self.e,'A');self.assertEqual(result['selected_candidate_id'],'one');self.assertIsNone(result['quality_score']);self.assertFalse(result['personal_stage_enabled']);self.assertIn('unvalidated',result['style_benefit'])
 def test_stale_evidence_job_hash(self):
  self.j['evidence_sha256']='stale';self.assertRaises(ValueError,b.evaluate,self.j,self.a,self.e,'A')
 def test_tampered_model_audit_binding(self):
  self.e['model']['features'][0]['direction']*=-1;self.assertRaises(ValueError,b.validate_evidence,self.e)
 def test_unknown_card_citation(self):
  self.j['candidates'][0]['evidence_card_ids']=['not-a-card'];self.assertRaises(ValueError,b.evaluate,self.j,self.a,self.e,'A')
 def test_unsupported_domain_citation(self):self.assertRaises(ValueError,b.evaluate,self.j,self.a,self.e,'not-a-domain')
 def test_new_domain_must_require_new_inspection(self):self.assertRaises(ValueError,b.evaluate,self.j,self.a,self.e,'B')
 def test_missing_source_problem(self):
  self.j['candidates'][0].pop('source_problem_evidence');self.assertRaises(ValueError,b.evaluate,self.j,self.a,self.e,'A')
 def test_nonexact_source_problem(self):
  self.j['candidates'][0]['source_problem_evidence']='invented';self.assertRaises(ValueError,b.evaluate,self.j,self.a,self.e,'A')
 def test_no_scope_review_abstains(self):
  self.j['candidates'][0]['review'].pop('relations_and_scope');result=b.evaluate(self.j,self.a,self.e,'A');self.assertEqual(result['status'],'abstained');self.assertEqual(result['rollback_text'],self.j['original'])
 def test_reviewer_failure_cannot_be_overridden_by_style(self):
  self.j['candidates'][0]['review']['verdict']='fail';result=b.evaluate(self.j,self.a,self.e,'A');self.assertEqual(result['status'],'abstained')
 def test_no_editorial_preference_abstains(self):
  self.j['selection_preference']=[];self.assertEqual(b.evaluate(self.j,self.a,self.e,'A')['status'],'abstained')
 def test_incompatible_requested_instrument_has_no_cards(self):
  self.e['model']['measurement_identity']='different';self.e['development_audit']['model_sha256']=m.digest(self.e['model']);self.j['evidence_sha256']=m.digest(self.e);self.assertRaises(ValueError,b.evaluate,self.j,self.a,self.e,'A')
 def test_actual_profile_mismatch_cannot_be_relabelled(self):
  actual=self.a
  class DifferentAnalyzer:
   def analyze(self,text,label='input'):
    result=actual.analyze(text,label);result['surface']['measurement_profile']['version']='incompatible-profile/999';return result
  self.assertRaises(ValueError,b.evaluate,self.j,DifferentAnalyzer(),self.e,'A')
 def test_missing_actual_profile_cannot_be_relabelled(self):
  actual=self.a
  class MissingAnalyzer:
   def analyze(self,text,label='input'):
    result=actual.analyze(text,label);result['surface'].pop('measurement_profile');return result
  self.assertRaises(ValueError,b.evaluate,self.j,MissingAnalyzer(),self.e,'A')

 def test_observed_evidence_missing_source_pins_rejected(self):
  self.assertRaises(ValueError,b.verify_instrument,self.a,{'input_role':'observational_train_dev','provenance':{}})
 def test_unknown_source_names_rejected(self):
  pins={name:hashlib.sha256((self.a.repo/name).read_bytes()).hexdigest() for name in b.INSTRUMENT_FILES};pins['../other.py']='0'*64
  self.assertRaises(ValueError,b.verify_instrument,self.a,{'input_role':'observational_train_dev','provenance':{'instrument_source_sha256':pins}})
 def test_tampered_source_hash_rejected(self):
  pins={name:hashlib.sha256((self.a.repo/name).read_bytes()).hexdigest() for name in b.INSTRUMENT_FILES};pins['research/surface/adapter.py']='0'*64
  self.assertRaises(ValueError,b.verify_instrument,self.a,{'input_role':'observational_train_dev','provenance':{'instrument_source_sha256':pins}})
 def test_exact_source_pins_verified(self):
  pins={name:hashlib.sha256((self.a.repo/name).read_bytes()).hexdigest() for name in b.INSTRUMENT_FILES}
  self.assertTrue(b.verify_instrument(self.a,{'input_role':'observational_train_dev','provenance':{'instrument_source_sha256':pins}}))

if __name__=='__main__':unittest.main(verbosity=2)
