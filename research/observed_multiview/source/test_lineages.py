import unittest
from build_lineages import finish_gate,validate_edge,alloc


def key(i):return alloc.wiki_member_key('mediawiki','zhwiki',str(i))
def data():
    members=[key(i) for i in range(110)]
    base={m:str(i) for i,m in enumerate(members)}
    calibration=[{'member_key':key(i),'source_frame':list(alloc.QUOTAS)[i//32]} for i in range(96)]
    rows=[]
    for i in range(96,108):
        rows.append({'record_key':str(i),'member_key':key(i),'source_frame':list(alloc.QUOTAS)[(i-96)//4],'source_sha256':'a'*64,'projection_sha256':'b'*64,'projection_profile':'fixture','preparse_eligible':True,'matching_coverage_complete':True,'rights_role_resolution':'calibrated_allowlist','frozen_candidate':True})
    return rows,members,base,calibration

def edge(a,b):return {'a':key(a),'b':key(b),'kind':'concrete_unresolved','evidence':{'metadata_evidence_sha256':'c'*64}}
SMALL={s:(2,1,1) for s in alloc.QUOTAS}

class LineageTests(unittest.TestCase):
    def run_gate(self,rows=None,edges=(),old=(),cal=None):
        r,m,b,c=data();return finish_gate(r if rows is None else rows,m,b,old,edges,c if cal is None else cal,[],SMALL)
    def test_complete_is_not_admitted(self):
        r=self.run_gate();self.assertEqual(len(r['private']['proposal']['selected_records']),12);self.assertFalse(r['public']['G2_admitted'])
    def test_multihop_old_contamination_different_component_id(self):
        r=self.run_gate(edges=[edge(109,96),edge(96,97)],old=[key(109)])
        self.assertEqual(r['public']['status'],'underfilled_stop');self.assertEqual(r['public']['selected_old_or_exposed_components'],0)
        self.assertNotIn('96',{x['record_key'] for x in r['private']['proposal']['selected_records']})
    def test_calibration_union_underfill(self):
        with self.assertRaisesRegex(ValueError,'calibration_underfilled'):self.run_gate(edges=[edge(1,2)])
    def test_calibration_old_contamination(self):
        with self.assertRaisesRegex(ValueError,'calibration_underfilled'):self.run_gate(edges=[edge(1,109)],old=[key(109)])
    def test_missing_comparison_quarantines(self):
        rows,_,_,_=data();rows[0]['matching_coverage_complete']=False;r=self.run_gate(rows=rows)
        self.assertEqual(r['public']['counts']['quarantined_missing_comparable_signatures'],1);self.assertEqual(r['public']['status'],'underfilled_stop')
    def test_unknown_rights_quarantines(self):
        rows,_,_,_=data();rows[0]['rights_role_resolution']='unknown';r=self.run_gate(rows=rows);self.assertEqual(r['public']['status'],'underfilled_stop')
    def test_no_backfill(self):
        rows,_,_,_=data();rows[0]['frozen_candidate']=False
        with self.assertRaisesRegex(ValueError,'posthoc'):self.run_gate(rows=rows)
    def test_generator_edges_and_exclusions(self):
        expected=self.run_gate(edges=[edge(109,96)],old=[key(109)])
        actual=self.run_gate(edges=(e for e in [edge(109,96)]),old=(m for m in [key(109)]));self.assertEqual(expected,actual)
    def test_near_copy_full_denominator_and_domain(self):
        e={'a':key(1),'b':key(2),'kind':'near_copy','evidence':{'shared_distinct_grams':80,'left_distinct_grams':100,'right_distinct_grams':200,'gram_domain':'char5-nfkc-no-ws/v1','unicode_version':'15.0.0','full_distinct_counts':True}}
        self.assertEqual(validate_edge(e),(key(1),key(2)))
        e['evidence']['full_distinct_counts']=False
        with self.assertRaisesRegex(ValueError,'truncated'):validate_edge(e)
    def test_threshold_reject(self):
        e={'a':key(1),'b':key(2),'kind':'near_copy','evidence':{'shared_distinct_grams':39,'left_distinct_grams':40,'right_distinct_grams':40}}
        with self.assertRaisesRegex(ValueError,'below_threshold'):validate_edge(e)
    def test_cross_source_concrete_unresolved_single_owner(self):
        r=self.run_gate(edges=[edge(96,100)]);self.assertEqual(len(r['private']['proposal']['selected_records']),11);self.assertEqual(r['public']['cross_split_hard_edges'],0)

if __name__=='__main__':unittest.main()
