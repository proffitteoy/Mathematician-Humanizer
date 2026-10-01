import collections,copy,hashlib,json,unittest
from pathlib import Path
from labels import *
ROOT=Path(__file__).resolve().parents[1]
class ContractTests(unittest.TestCase):
 def setUp(self):
  self.p=json.loads((ROOT/'private/family-manifest.json').read_text());self.j=json.loads((ROOT/'private/authoring-jobs.json').read_text());self.c=json.loads((ROOT/'public/authoring.contract.json').read_text())
 def test_exact_counts(self):
  self.assertEqual(len(self.p),48);self.assertEqual(len(self.j),384);self.assertEqual(collections.Counter(p['partition'] for p in self.p),{'train':32,'dev':8,'test':8})
 def test_hash_binding(self):
  for key,file in [('family_manifest_sha256','family-manifest.json'),('job_manifest_sha256','authoring-jobs.json')]:self.assertEqual(self.c[key],hashlib.sha256((ROOT/'private'/file).read_bytes()).hexdigest())
 def test_family_wide_split(self):
  for p in self.p:self.assertEqual({j['partition'] for j in self.j if j['family_id']==p['family_id']},{p['partition']})
 def test_every_cell_both_templates_passes(self):
  for p in self.p:
   for c in self.c['nominal_conditions']:
    js=[j for j in self.j if j['family_id']==p['family_id'] and j['nominal_condition']==c];self.assertEqual(len(js),2);self.assertEqual({j['template'] for j in js},{'A','B'});self.assertEqual({j['authoring_pass'] for j in js},{0,1})
 def test_complete_cross_balance(self):
  for g in {p['genre'] for p in self.p}:
   for s in ('train','dev','test'):
    for pa in (0,1):
     for c in self.c['nominal_conditions']:
      n=collections.Counter(j['template'] for j in self.j if (j['genre'],j['partition'],j['authoring_pass'],j['nominal_condition'])==(g,s,pa,c));self.assertEqual(n['A'],n['B'])
 def test_author_does_not_receive_split(self):
  for j in self.j:self.assertNotIn('partition',j['prompt']);self.assertNotIn('family_id',j['prompt']['content_plan'])
 def test_unique_deterministic_order_and_review_ids(self):
  self.assertEqual([j['global_order'] for j in self.j],list(range(384)));self.assertEqual(len({j['review_id'] for j in self.j}),384)
 def test_no_generated_prose(self):
  for pa in (0,1):self.assertFalse((ROOT/f'private/author-pass-{pa}/STARTED.json').exists())
 def test_no_training_inference_or_natural_permissions(self):
  for k in ('model_fit_authorized','natural_source_reads_authorized','owner_text_authorized','counts_towards_1280_natural_works','generic_stage_complete'):self.assertIs(self.c[k],False)
  self.assertEqual(self.c['declared_inference_candidates'],0)
 def test_disjoint_short_mixed(self):
  for t in ['甲。'*100,'甲。'+'乙'*45+'。'+'丙'*45+'。'+'丁'*110+'。']:
   p=observed_properties(t,'甲');self.assertIn(p['rhythm_observed'],('short','mixed','outside_support'))
 def test_whitespace_cannot_move_mainpoint(self):
  a=observed_properties('主旨。甲。乙。丙。','主旨');b=observed_properties(' \n主旨。 甲。乙。丙。   ','主旨');self.assertEqual(a['mainpoint_start_fraction'],b['mainpoint_start_fraction'])
 def test_punctuation_and_final_fragment(self):
  p=observed_properties('甲。乙！？丙!丁?尾','甲');self.assertEqual(p['sentence_lengths'],[1]*5)
 def test_duplicate_mainpoint_unsupported(self):self.assertIsNone(observed_properties('主旨。主旨。乙。丙。','主旨')['mechanical_condition'])
 def test_formal_math_and_headings_unsupported(self):
  for t in ['# 标题\n','∀x ','```','“引用”']:
   self.assertFalse(observed_properties(t+'甲。'+'乙。'*110,'甲')['format_and_length_support'])
 def test_adjudication_never_uses_nominal(self):
  p={'rhythm_observed':'short','placement_observed':'early','mechanical_condition':'short_early'}
  a={'review_id':'x','rater_id':'A','fact_labels':{'P1':'preserved'},'semantic_axes':{k:'pass' for k in SEMANTIC_AXES},'mainpoint_is_real_main_claim':'yes','rhythm_label':'short','placement_label':'early'};b=copy.deepcopy(a);b['rater_id']='B'
  r=adjudicate_pair(a,b,p,['P1']);self.assertEqual(r['realized_condition'],'short_early');self.assertFalse(r['nominal_condition_used']);self.assertFalse(r['semantic_guarantee'])
  b['semantic_axes']['scope']='uncertain';self.assertIsNone(adjudicate_pair(a,b,p,['P1'])['realized_condition'])
 def test_v02_supported_length_boundaries(self):
  for n,expected in ((119,False),(120,True),(400,True),(401,False)):
   t='主旨。'+'甲'*(n-8)+'。乙。丙。';self.assertEqual(len(t),n);self.assertEqual(observed_properties(t,'主旨')['format_and_length_support'],expected)
 def test_v02_prompt_bounds(self):
  self.assertEqual(self.c['text_codepoint_bounds'],[120,400])
  for j in self.j:self.assertIn('120到400',j['prompt']['instruction']);self.assertNotIn('200到700',j['prompt']['instruction'])
 def test_same_rater_rejected(self):
  a={'review_id':'x','rater_id':'A','fact_labels':{'P1':'preserved'},'semantic_axes':{k:'pass' for k in SEMANTIC_AXES},'mainpoint_is_real_main_claim':'yes','rhythm_label':'short','placement_label':'early'}
  with self.assertRaisesRegex(ValueError,'identity'):adjudicate_pair(a,a,{},['P1'])
if __name__=='__main__':unittest.main()
