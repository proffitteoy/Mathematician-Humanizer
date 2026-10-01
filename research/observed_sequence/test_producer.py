"""Producer tests use invented text and an original deterministic fake parser."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from research.linguistic.contracts import ParserProfile
from research.observed_sequence.contracts import Provenance,digest
from research.observed_sequence.prepare import pair_ledger
from research.observed_sequence.producer import SentenceLocalProducer

class FakeBackend:
 def __init__(self,fail_on=None):
  self.profile=ParserProfile('original-fixture','0.1','no_model_loaded','0'*64);self.inputs=[];self.fail_on=fail_on
 def pipeline(self,text):
  self.inputs.append(text)
  if self.fail_on and self.fail_on in text:raise RuntimeError('synthetic error with source that must not be echoed')
  words=[]
  for i,c in enumerate(text):
   if c.isspace():continue
   idx=len(words)+1;punct=c in '。！？'
   words.append(SimpleNamespace(id=idx,start_char=i,end_char=i+1,text=c,upos='PUNCT' if punct else 'NOUN',head=0 if idx==1 else 1,deprel='root' if idx==1 else 'punct' if punct else 'dep',feats=None))
  return SimpleNamespace(sentences=[SimpleNamespace(words=words)])

def prov(text):return Provenance('0'*64,digest(text),'synthetic-record','synthetic-group','train')
class TestProducer(unittest.TestCase):
 def setUp(self):self.text='甲。\n乙。\n丙。\n丁。\n戊。\n己。\n庚。\n辛。\n'
 def test_only_isolated_units_reach_backend(self):
  b=FakeBackend();p=SentenceLocalProducer(b,analysis_status='synthetic_fixture');r=p.record(self.text,prov(self.text));self.assertEqual(len(b.inputs),8);self.assertTrue(all('\n' not in x and len(x)==2 for x in b.inputs));self.assertEqual(len(r.units[0].row.values),68)
 def test_cache_exact_identity(self):
  b=FakeBackend();p=SentenceLocalProducer(b,analysis_status='synthetic_fixture');p.record(self.text,prov(self.text));p.record(self.text,prov(self.text));self.assertEqual(p.parser_calls,8);p.record(self.text,prov(self.text),use_cache=False);self.assertEqual(p.parser_calls,16)
 def test_prefix_recomputed_uncached_matches(self):
  p=SentenceLocalProducer(FakeBackend(),analysis_status='synthetic_fixture');r=p.record(self.text,prov(self.text))
  for pair in pair_ledger(r):self.assertEqual(p.prefix_units(self.text,r.provenance,pair.input_cutoff,use_cache=False),r.units[:pair.target_index])
 def test_suffix_changes_do_not_change_prefix_observations(self):
  p=SentenceLocalProducer(FakeBackend(),analysis_status='synthetic_fixture');r=p.record(self.text,prov(self.text));cut=pair_ledger(r)[0].input_cutoff
  left=p.prefix_units(self.text,r.provenance,cut,use_cache=False)
  for suffix in ['！後來。\n','”新的。\n','3.14不同。\n']:
   t=self.text[:cut]+suffix;self.assertEqual(left,p.prefix_units(t,prov(t),cut,use_cache=False))
 def test_failure_keeps_source_unit_and_no_target(self):
  p=SentenceLocalProducer(FakeBackend('戊'),analysis_status='synthetic_fixture');r=p.record(self.text,prov(self.text));self.assertEqual(len(r.units),8);self.assertEqual(r.units[4].status,'failed');self.assertIsNone(r.units[4].target_counts);self.assertEqual(pair_ledger(r)[0].missing_reason,'parse_failed')
 def test_terminal_prefix_without_whitespace_rejected(self):
  p=SentenceLocalProducer(FakeBackend(),analysis_status='synthetic_fixture')
  with self.assertRaisesRegex(ValueError,'boundary_unconfirmed'):p.prefix_units(self.text,prov(self.text),2)
 def test_no_human_or_author_upgrade(self):
  p=SentenceLocalProducer(FakeBackend(),analysis_status='synthetic_fixture');r=p.record(self.text,prov(self.text));self.assertFalse(r.provenance.author_ground_truth);self.assertFalse(r.provenance.human_origin_ground_truth)
if __name__=='__main__':unittest.main()
