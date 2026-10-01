"""Synthetic-only independent matching and bounded-work checks."""
import importlib.util,pathlib,random,re,sys,tempfile,unittest
ROOT=pathlib.Path('/workspace/shared/style-scale10-source-v01/public');sys.path.insert(0,str(ROOT))
import matcher as m
from test_matcher import fixture_db,fake_sig,projection
spec=importlib.util.spec_from_file_location('independent_frozen_segment','/workspace/shared/style-compiler/src/style_compiler/segmentation.py');seg=importlib.util.module_from_spec(spec);sys.modules[spec.name]=seg;spec.loader.exec_module(seg)

class IndependentMatcherTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.packages=[]
 def tearDown(self):
  for p in self.packages:p.close()
 def package(self,sigs,name='one',reverse=False):
  p=fixture_db(pathlib.Path(self.temp.name)/(name+'.sqlite'),sigs,reverse);self.packages.append(p);return p
 def test_every_postings_increment_is_charged_before_execution(self):
  grams=[m.gram_hash('token'+str(i))for i in range(100)];p=self.package([fake_sig('ref',grams)]);budget={'used':0,'cap':50}
  with self.assertRaisesRegex(m.BoundExceeded,'aggregate_comparison_increment_cap'):p.compare([fake_sig('query',grams)],comparison_budget=budget)
  self.assertEqual(budget['used'],51)
 def test_all_unseen_grams_still_deny_containment(self):
  common=[m.gram_hash('same'+str(i))for i in range(40)]
  ref=common+[m.gram_hash('old-only'+str(i))for i in range(60)];query=common+[m.gram_hash('new-only'+str(i))for i in range(60)]
  p=self.package([fake_sig('old',ref)]);r=p.compare([fake_sig('new',query)])
  self.assertEqual(r['candidate_full_gram_counts'],[100]);self.assertEqual(r['candidate_mapped_gram_counts'],[40]);self.assertEqual(r['hits'],[])
 def test_cross_dictionary_reverse_insertion_does_not_change_matches(self):
  grams=[m.gram_hash(str(i))for i in range(75)]
  one=self.package([fake_sig('ref',grams)],'one');two=self.package([fake_sig('ref',grams)],'two',True)
  query=fake_sig('query',grams)
  self.assertEqual(one.compare([query])['hits'][0]['shared_distinct_grams'],75)
  self.assertEqual(two.compare([query])['hits'][0]['shared_distinct_grams'],75)
 def test_clean_candidate_different_old_markup_stays_quarantined(self):
  clean=''.join(chr(0x4e00+i)for i in range(100));old=''.join('{{标签|'+c+'}}'for c in clean)
  p=self.package([m.signature(old,'ref','raw')]);r=m.match_record(clean,projection(clean),packages=[p],expected_raw_sha256=m.sha(clean.encode()))
  self.assertTrue(r['complete_declared_view_comparisons']);self.assertFalse(r['cross_projection_coverage_certified'])
  self.assertFalse(r['admission_authorized']);self.assertEqual(r['status'],'quarantine_unmatched_cross_projection_coverage')
 def test_long_blocks_equal_actual_frozen_segmenter_on200random_cases(self):
  rng=random.Random(2193321);alphabet='甲乙丙丁abcdefgh12345。！？!?．. “”,\t\n\r'
  for _ in range(200):
   text=''.join(rng.choice(alphabet)for _ in range(rng.randrange(50,600)))
   blocks=[('physical_blankline_block',i,s)for i,s in enumerate(re.split(r'(?:\r?\n[\t ]*){2,}',text))]
   blocks += [('punctuation_line_unit',i,text[u.start:u.end])for i,u in enumerate(seg.segment(text)[1])]
   expected=[(kind,i,m.norm_hash(n),len(n))for kind,i,s in blocks if len(n:=m.normalize(s))>=64]
   self.assertEqual(m.long_blocks(text),expected)
 def test_final_callback_runs_even_on_tiny_package(self):
  p=self.package([m.signature('a','ref','raw')]);seen=[];p.compare([m.signature('b','query','raw')],resource_callback=seen.append);self.assertTrue(seen)

if __name__=='__main__':unittest.main(verbosity=2)
