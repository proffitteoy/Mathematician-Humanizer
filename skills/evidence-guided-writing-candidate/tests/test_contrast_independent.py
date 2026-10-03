"""Independent synthetic evidence-card regressions. No corpus read or natural model fit."""
import copy, importlib.util, json, math, pathlib, unittest
def candidate_root():
 for parent in pathlib.Path(__file__).resolve().parents:
  for root in (parent,parent/'repo/skills/evidence-guided-writing-candidate'):
   if (root/'scripts/contrast.py').is_file() and (root/'scripts/bridge.py').is_file():return root
 raise RuntimeError('Candidate package not found; keep tests inside the package or delivery tree')
CANDIDATE=candidate_root()
SOURCE=CANDIDATE/'scripts/contrast.py'
spec=importlib.util.spec_from_file_location('candidate_contrast',SOURCE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def data():
 rows=[]
 for split,n in [('TRAIN',8),('DEV',4)]:
  for domain in ['A','B']:
   for i in range(n):
    for arm in ['HUMAN','CHATGPT']:
     h=arm=='HUMAN'
     rows.append({'pair_id':f'{split}-{domain}-{i}','component_id':f'{split}-{domain}-{i}','domain':domain,'condition':arm,'split':split,'features':{'stable':3. if h else 1.,'reversal': (5. if h else 1.) if split=='TRAIN' else (1. if h else 5.),'domain_conflict':(3. if h else 1.) if domain=='A' else (1. if h else 3.),'zero':2.,'missing':None}})
 return {'schema_version':'paired-style-observations/0.1','role':'synthetic_mechanism_fixture','measurement_identity':'synthetic-deterministic-v1','measurement_profile':{'kind':'synthetic-deterministic-v1'},'measurement_profile_sha256':m.digest({'kind':'synthetic-deterministic-v1'}),'provenance':{'source':'new synthetic fixtures, no corpus'},'rows':rows}

class ContrastIndependentTests(unittest.TestCase):
 def setUp(self): self.d=data()
 def test_hand_computable_stable_contrast(self):
  model=m.fit(self.d,bootstrap=40);card=next(c for c in model['features'] if c['feature_id']=='stable');self.assertEqual(card['train']['human_minus_ai'],2.);self.assertEqual(card['train']['ci95'],[2.,2.]);self.assertEqual(card['train']['components'],16);self.assertTrue(card['train_inspection_eligible'])
 def test_dev_mutation_cannot_change_fit(self):
  before=m.fit(self.d,bootstrap=40);changed=copy.deepcopy(self.d)
  for r in changed['rows']:
   if r['split']=='DEV':r['features']={k:999. if v is not None else None for k,v in r['features'].items()}
  self.assertEqual(before,m.fit(changed,bootstrap=40));self.assertNotEqual(m.audit(before,self.d),m.audit(before,changed))
 def test_dev_reversal_cannot_be_supported(self):
  model=m.fit(self.d,40);audit=m.audit(model,self.d);c=next(c for c in audit['features'] if c['feature_id']=='reversal');self.assertFalse(c['inspection_supported']);self.assertFalse(c['dev_direction_reproduced'])
 def test_domain_conflict_cannot_be_train_eligible(self):
  c=next(c for c in m.fit(self.d,40)['features'] if c['feature_id']=='domain_conflict');self.assertFalse(c['train_inspection_eligible'])
 def test_zero_null_preserve_abstention(self):
  cards={c['feature_id']:c for c in m.fit(self.d,40)['features']};self.assertEqual(cards['zero']['train']['human_minus_ai'],0.);self.assertIsNone(cards['missing']['train']['human_minus_ai']);self.assertFalse(cards['zero']['train_inspection_eligible']);self.assertFalse(cards['missing']['train_inspection_eligible'])
 def test_synthetic_test_split_rejected_without_reading_test(self):
  self.d['rows'][0]['split']='TEST';self.assertRaises(ValueError,m.validate,self.d)
 def test_synthetic_held_out_generator_label_rejected(self):
  self.d['rows'][0]['condition']='DAVINCI';self.assertRaises(ValueError,m.validate,self.d)
 def test_cross_split_component_leakage_rejected(self):
  train=self.d['rows'][0]['component_id']
  for r in self.d['rows']:
   if r['split']=='DEV':r['component_id']=train;break
  self.assertRaises(ValueError,m.validate,self.d)
 def test_duplicate_pair_arm_rejected(self):
  self.d['rows'].append(copy.deepcopy(self.d['rows'][0]));self.assertRaises(ValueError,m.validate,self.d)
 def test_missing_arm_rejected(self):
  self.d['rows'].pop();self.assertRaises(ValueError,m.validate,self.d)
 def test_nonfinite_and_boolean_values_rejected(self):
  for v in [float('nan'),float('inf'),True]:
   d=data();d['rows'][0]['features']['stable']=v;self.assertRaises(ValueError,m.validate,d)
 def test_modified_train_binding_rejected(self):
  model=m.fit(self.d,40);self.d['rows'][0]['features']['stable']=4.;self.assertRaises(ValueError,m.audit,model,self.d)
 def test_instrument_binding_rejected(self):
  model=m.fit(self.d,40);self.d['measurement_identity']='different';self.assertRaises(ValueError,m.audit,model,self.d)
 def test_component_equal_weighted_difference(self):
  pairs=[('many',2.,0.),('many',2.,0.),('many',2.,0.),('one',10.,0.)];self.assertEqual(m.summarize_pairs(pairs)['human_minus_ai'],6.)
 def test_no_quality_probability_or_rewrite_policy_claim(self):
  model=m.fit(self.d,40);self.assertIsNone(model['human_quality_probability']);self.assertIn('not a learned rewrite policy',model['learned_object']);self.assertEqual(model['input_role'],'synthetic_mechanism_fixture')

if __name__=='__main__':unittest.main(verbosity=2)
