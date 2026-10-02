"""Execution-cost denominators come from the paired scoring population."""
import dataclasses,importlib.util,unittest
from pathlib import Path
import torch
from test_core import fixture
from experimental_natural.cache_adapter import CacheDescriptor
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('profile_counts_under_test',ROOT/'profile_natural.py');profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)
class ProfileCountsTests(unittest.TestCase):
    def fixture(self):
        _,_,transform=fixture();desc=[];counts={}
        for q,answer,h,g in [('q0','a0',4,2),('q1','a1',5,1),('q2','a2',2,2),('q2','a3',3,2)]:
            for arm,n in [('human',h),('chatgpt',g)]:
                desc.append(CacheDescriptor('/never_read','a'*64,q,answer,q,'baike','dev',arm,'b'*64));counts[(answer,arm)]=n
        return desc,counts,transform
    def test_unverified_count_metadata_fails_before_read(self):
        from unittest.mock import patch
        with patch('pathlib.Path.read_text',side_effect=AssertionError('must not read')):
            with self.assertRaises(PermissionError):profile.unit_count_metadata(Path('/never_read'),[])
    def test_joint_prefix_counts_not_all_documents(self):
        d,c,t=self.fixture();r=profile.metadata_prefix_support(d,c,t,'dev')
        self.assertTrue(r['exact']);self.assertEqual(r['questions'],2);self.assertEqual(r['answers'],3);self.assertEqual(r['documents'],6);self.assertEqual(r['scored_prefixes'],9)
    def test_no_active_span_target_labels_upper_bound(self):
        d,c,t=self.fixture();mask=t.score_eligible.clone();mask[t.structural_indices[0]]=False;t=dataclasses.replace(t,score_eligible=mask)
        r=profile.metadata_prefix_support(d,c,t,'dev');self.assertFalse(r['exact']);self.assertTrue(r['counts_are_upper_bounds'])
if __name__=='__main__':unittest.main(verbosity=2)
