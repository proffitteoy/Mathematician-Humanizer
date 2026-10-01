"""Original synthetic checks only; no corpus or pretrained parser access."""
import dataclasses,math,unittest
from types import SimpleNamespace
from style_compiler.segmentation import segment
from research.linguistic.schema import CHANNEL_IDS
from research.observed_sequence.contracts import *
from research.observed_sequence.prepare import *


def row(value=1.0,opportunity=5.0,reason=None):
 return SensorRow(LOCAL_CHANNELS,(value,)*68,(opportunity,)*68,(reason,)*68)
def record(text='甲。\n乙。\n丙。\n丁。\n戊。\n己。\n庚。\n辛。\n壬。\n癸。\n',value=1.0,partition='train',key='original-fixture',group='fixture-lineage'):
 spans=segment(text)[1]
 return ObservedRecord(Provenance('0'*64,digest(text),key,group,partition),text,
  tuple(ObservedUnit(s.index,s.start,s.end,row(value),(5,)+(0,)*13,analysis_status='synthetic_fixture') for s in spans),'1'*64,'2'*64)
def failed(unit):return dataclasses.replace(unit,row=row(None,None,'parse_failed'),target_counts=None,status='failed',failure_reason='parse_failed')

class TestContracts(unittest.TestCase):
 def test_schema_width_and_no_history(self):
  self.assertEqual(len(LOCAL_CHANNELS),68);self.assertFalse(EXCLUDED_HISTORY & set(LOCAL_CHANNELS));record().validate()
 def test_exact_source_hash(self):
  with self.assertRaisesRegex(ValueError,'exact_source'):dataclasses.replace(record(),text='更改正文。').validate()
 def test_source_not_author_truth(self):
  p=dataclasses.replace(record().provenance,author_ground_truth=True)
  with self.assertRaises(ValueError):p.validate()
 def test_values_need_opportunity(self):
  with self.assertRaises(ValueError):row(0,0).validate()
  row(None,0,'zero_denominator').validate()
 def test_failed_unit_no_target(self):
  u=failed(record().units[0]);u.validate()
  with self.assertRaises(ValueError):dataclasses.replace(u,target_counts=(0,)*14).validate()
 def test_no_negative_or_bool_counts(self):
  for x in (-1,True):
   with self.assertRaises(ValueError):dataclasses.replace(record().units[0],target_counts=(x,)+(0,)*13).validate()
 def test_pos_only_cannot_claim_dependency(self):
  with self.assertRaisesRegex(ValueError,'pos_only'):dataclasses.replace(record().units[0],status='pos_only').validate()
 def test_repr_hides_raw_source_and_ids(self):
  r=record(key='PRIVATE_KEY');self.assertNotIn(r.text,repr(r));self.assertNotIn('PRIVATE_KEY',repr(r.provenance))
 def test_group_record_and_content_leakage(self):
  a=record();b=record(partition='test')
  with self.assertRaisesRegex(ValueError,'cross_partition'):check_known_split_isolation([a,b])
  b=record(text='不同原文。\n'*8,partition='test',key='new',group='new');self.assertTrue(check_known_split_isolation([a,b]))
 def test_schema_order_not_width_only(self):
  with self.assertRaises(ValueError):dataclasses.replace(row(),channel_ids=tuple(reversed(LOCAL_CHANNELS))).validate()

class TestPreparation(unittest.TestCase):
 def test_primitive_other_counts(self):
  ts=[SimpleNamespace(form=x,upos=p) for x,p in [('甲','NOUN'),('啊','INTJ'),('符','SYM'),('詞','X'),('。','PUNCT'),('!','NOUN')]]
  c=lexical_pos_counts(ts);self.assertEqual(sum(c),4);self.assertEqual(c[13],3)
 def test_full_schema_conversion(self):
  v={'channel_ids':CHANNEL_IDS,'values':tuple(range(71)),'opportunities':(1,)*71,'missing_reasons':(None,)*71}
  r=local_row(v);self.assertEqual(len(r.values),68)
  v['channel_ids']=tuple(reversed(CHANNEL_IDS))
  with self.assertRaises(ValueError):local_row(v)
 def test_terminal_eof_not_enough(self):
  # No whitespace proving termination of the first punctuation run.
  self.assertFalse(closed_boundary('甲。乙。',1));self.assertTrue(closed_boundary('甲。 乙。',1));self.assertTrue(closed_boundary('甲\n乙',1))
 def test_whitespace_boundary_suffix_invariance(self):
  for prefix in ['甲。 ','甲。！”\n','數字3.14。\n','片段\n']:
   before=segment(prefix)[1]
   for suffix in ['！下一句。','”下一句。','甲。','\n乙。','3.14接續']:
    after=segment(prefix+suffix)[1][:len(before)];self.assertEqual([(s.start,s.end) for s in before],[(s.start,s.end) for s in after])
 def test_ledger_preserves_all_candidates(self):
  r=record();p=pair_ledger(r);self.assertEqual(len(p),6);self.assertTrue(all(x.eligible for x in p));self.assertEqual([x.target_index for x in p],list(range(4,10)))
 def test_failed_prefix_never_bridged(self):
  r=record();us=list(r.units);us[2]=failed(us[2]);r=dataclasses.replace(r,units=tuple(us));p=pair_ledger(r)
  self.assertEqual([x.missing_reason for x in p[:3]],['insufficient_contiguous_prefix']*3)
  self.assertEqual(p[3].input_indices,(3,4,5,6));self.assertEqual(p[3].target_index,7)
 def test_target_failure_and_zero_in_coverage(self):
  r=record();us=list(r.units);us[4]=failed(us[4]);us[5]=dataclasses.replace(us[5],target_counts=(0,)*14);p=pair_ledger(dataclasses.replace(r,units=tuple(us)))
  self.assertEqual(len(p),6);self.assertEqual(p[0].missing_reason,'parse_failed')
  r=record();us=list(r.units);us[4]=dataclasses.replace(us[4],target_counts=(0,)*14);p=pair_ledger(dataclasses.replace(r,units=tuple(us)))
  self.assertEqual(p[0].missing_reason,'zero_lexical_target');self.assertTrue(p[1].eligible)
 def test_transform_train_only(self):
  with self.assertRaisesRegex(ValueError,'train_only'):fit_train_transform([record(partition='test')])
 def test_transform_record_equal_not_unit_equal(self):
  a=record(value=0);b=record(text='甲。\n乙。\n',value=2,key='second',group='second');t=fit_train_transform([a,b]);self.assertEqual(t.value_mean,(1.0,)*68);self.assertEqual(t.value_scale,(1.0,)*68);self.assertEqual(t.value_support_records,(2,)*68);self.assertEqual(t.value_observation_count,(12,)*68)
 def test_constant_and_unavailable_channels_encode_zero(self):
  t=fit_train_transform([record()]);x=t.encode(row(9));self.assertEqual(len(x),272);self.assertTrue(all(x[i]==0 for i in range(0,272,4)));self.assertTrue(all(x[i]==0 for i in range(2,272,4)))
  x=t.encode(row(None,None,'parse_failed'));self.assertEqual(x,(0.0,)*272)
 def test_fraction_constant_and_log_opportunity_constant(self):
  t=fit_train_transform([record(value=1/3)]);self.assertEqual(t.value_scale,(0.0,)*68);self.assertEqual(t.opportunity_scale,(0.0,)*68);x=t.encode(row(1/3+1,9));self.assertEqual(x[0],0);self.assertEqual(x[2],0)
 def test_near_constant_variance_not_epsilon_erased(self):
  a=1/3;b=math.nextafter(a,math.inf);t=fit_train_transform([record(value=a),record(value=b,key='other',group='other')]);self.assertGreater(t.value_scale[0],0);self.assertAlmostEqual(t.encode(row(a))[0],-1);self.assertAlmostEqual(t.encode(row(b))[0],1)
 def test_all_missing_support_is_distinct_from_constant(self):
  r=record();r=dataclasses.replace(r,units=tuple(failed(u) for u in r.units));t=fit_train_transform([r]);self.assertEqual(t.value_support_records,(0,)*68);self.assertEqual(t.value_scale,(0.0,)*68);self.assertEqual(t.encode(row(99))[0],0)
 def test_lengths_only_visible_component(self):
  r=record();p=pair_ledger(r)[0];v=prefix_lengths(r,p);self.assertEqual(v[0],math.log1p(4));self.assertEqual(v[1],math.log1p(p.input_cutoff-p.component_start))
 def test_forged_spans_rejected(self):
  r=record();us=list(r.units);us[4]=dataclasses.replace(us[4],end=us[4].end-1)
  with self.assertRaisesRegex(ValueError,'span_alignment'):pair_ledger(dataclasses.replace(r,units=tuple(us)))

if __name__=='__main__':unittest.main()
