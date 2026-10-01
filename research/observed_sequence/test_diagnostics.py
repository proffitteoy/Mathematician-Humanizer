"""Original endpoint-semantic tests; no natural source or model fit."""
from collections import defaultdict
from dataclasses import replace
import unittest
from research.observed_sequence.test_prepare import record
from research.observed_sequence.diagnostics import endpoint_flags,summarize_buckets
class TestEndpointDiagnostics(unittest.TestCase):
 def test_unfinished_source_eof_target(self):
  r=record('甲。\n乙。\n丙。\n丁。\n戊');f=endpoint_flags(r,4);self.assertTrue(f['terminal_source_unit']);self.assertTrue(f['plain_character_extensible'])
 def test_terminal_punctuation_only_closer_extensible(self):
  r=record('甲。\n乙。\n丙。\n丁。\n戊。');f=endpoint_flags(r,4);self.assertTrue(f['terminal_source_unit']);self.assertFalse(f['plain_character_extensible']);self.assertTrue(f['closer_or_terminal_extensible'])
 def test_terminal_with_observed_newline_can_be_stable(self):
  r=record('甲。\n乙。\n丙。\n丁。\n戊。\n');f=endpoint_flags(r,4);self.assertTrue(f['terminal_source_unit']);self.assertFalse(f['plain_character_extensible']);self.assertFalse(f['closer_or_terminal_extensible'])
 def test_parse_cap_is_not_source_eof(self):
  r=record('甲。\n'*34);r=replace(r,units=r.units[:32]);r.validate();self.assertFalse(endpoint_flags(r,31)['terminal_source_unit'])
 def test_conditional_macro_not_pair_mean_and_empty_is_none(self):
  a=defaultdict(list,all=[1,1,1],interior=[1,1,1]);b=defaultdict(list,all=[3],interior=[3]);s=summarize_buckets([a,b]);self.assertEqual(s['all']['conditional_record_equal_ce'],2);self.assertIsNone(s['terminal_source_unit']['conditional_record_equal_ce'])
if __name__=='__main__':unittest.main()
