"""Independent synthetic fault probes; no production cache/signature scan."""
import collections, hashlib, importlib.machinery, json, pathlib, random, sys, tempfile, unittest
from unittest.mock import patch
importlib.machinery.SourceFileLoader.get_code=lambda self,fullname:compile(self.get_data(self.path),self.path,'exec',dont_inherit=True)
sys.path.insert(0,'/workspace/shared/style-scale10-calibration-gate-v01/public')
import calibration_gate as g
import verify_gate as v
from test_calibration_gate import member,row,package,text

class Independent(unittest.TestCase):
 def test_budget_full_does_not_mutate(self):
  b={'used':299999999,'cap':300000000}
  with self.assertRaises(g.GateError):g.precharge_comparisons(b,2)
  self.assertEqual(b['used'],299999999)
 def test_bad_budget_types_fail(self):
  for b,n in [({'used':True},1),({'used':-1},1),({'used':0},True),({'used':0,'cap':300000001},0)]:
   with self.assertRaises(g.GateError):g.precharge_comparisons(b,n)
 def test_completed_delta_chain_must_match(self):
  base={'status':'calibration_underfilled','comparison_budget_scope':g.COMPARISON_SCOPE,'comparison_prior_increment_count':251617,'comparison_increment_delta':19,'comparison_increment_count':251636}
  self.assertEqual(g.checked_comparison_total(251617,base),251636)
  for key,value in [('status','stopped_partial_no_retry'),('comparison_prior_increment_count',0),('comparison_increment_delta',20),('comparison_increment_count',0)]:
   with self.assertRaises(g.GateError):g.checked_comparison_total(251617,dict(base,**{key:value}))
 def test_verifier_charges_before_shared_structure_update(self):
  with tempfile.TemporaryDirectory()as root:
   raw=text(876);p=package(pathlib.Path(root)/'p.sqlite',[(raw,member(1))],'synthetic')
   sig=g.signature(raw+'末尾改写','s','raw')
   # Hash fields differ, so no raw/full equality consumes the one-unit budget.
   class CounterProbe(collections.Counter):
    def update(self, iterable=None, **kwargs):
     if iterable:
      assert budget['used']>=len(iterable), 'postings updated before precharge'
     return super().update(iterable,**kwargs)
   budget={'used':g.INCREMENT_CAP,'cap':g.INCREMENT_CAP}
   with patch.object(v,'Counter',CounterProbe):
    with self.assertRaises(g.GateError):v.replay(p,[sig],type('Guard',(),{'check':lambda self:None})(),budget)
   self.assertEqual(budget['used'],g.INCREMENT_CAP);p.close()
 def test_namespaces_do_not_union_same_numeric_page(self):
  d=g.DSU();rows=[]
  for source,project in [('discussion','zhwiki'),('news_prose','zhwikinews'),('guide_prose','zhwikivoyage')]:
   for i in range(32):
    r=row(i,source);r['member_key']=member(i,project);d.add(r['member_key']);rows.append(r)
  _,a=g.finish_graph(d,rows)
  self.assertEqual(a['all_calibration_distinct_components'],96)
  self.assertEqual(a['status'],'calibration_copy_gate_complete_pending_independent_review')
 def test_cross_source_union_is_underfilled_even_when_each_has32(self):
  d=g.DSU();rows=[]
  for j,source in enumerate(g.SOURCES):
   for i in range(32):
    r=row(j*1000+i,source);d.add(r['member_key']);rows.append(r)
  d.union(rows[0]['member_key'],rows[32]['member_key'],'copy_edge')
  _,a=g.finish_graph(d,rows)
  self.assertEqual(a['calibration_final_components'],{s:32 for s in g.SOURCES});self.assertEqual(a['all_calibration_distinct_components'],95);self.assertEqual(a['status'],'calibration_underfilled')
 def test_json_duplicate_and_nonfinite_rejected(self):
  for raw in ['{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}']:
   with self.assertRaises(g.GateError):g.strict_json(raw)

if __name__=='__main__':unittest.main(verbosity=2)
