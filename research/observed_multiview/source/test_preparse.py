import unittest
from project_wikitext import project
from preparse import qualify,_han_fraction


def sentence(i):return '这是用于检验字符边界的中文叙述内容'+str(i)+'并不涉及模型目标和句法标注。'
def source(n=10,sep='\n'):return sep.join(sentence(i) for i in range(n))

class PreparseTests(unittest.TestCase):
    def test_eligible_fixed_character_rules(self):
        t=source();p=project(t,'discussion');q=qualify(p,'record1',t)
        self.assertTrue(q['preparse_eligible']);self.assertEqual(q['selected_segment']['full_segment_unit_count'],10);self.assertEqual(len(q['selected_segment']['closed_points']),6)
    def test_no_whitespace_anchors(self):
        t=source(sep='');q=qualify(project(t,'discussion'),'record',t);self.assertFalse(q['preparse_eligible'])
    def test_entity_whitespace_not_raw_anchor(self):
        t=source(sep='&#32;');q=qualify(project(t,'discussion'),'record',t);self.assertFalse(q['preparse_eligible']);self.assertIn('raw_whitespace_boundary_unconfirmed',q['segment_checks'][0]['candidate_point_rejections'].values())
    def test_barrier_no_join(self):
        t=source(5)+'\n{{模板}}\n'+source(5);q=qualify(project(t,'discussion'),'record',t)
        self.assertFalse(q['preparse_eligible']);self.assertEqual(len(q['segment_checks']),2)
    def test_source_size_floor(self):
        t='甲。\n'*10;q=qualify(project(t,'discussion'),'record',t);self.assertFalse(q['preparse_eligible']);self.assertIn('record_rejection',q)
    def test_count_cap_not_slice_to_admit(self):
        t=source(65);q=qualify(project(t,'discussion'),'record',t);self.assertFalse(q['preparse_eligible'])
    def test_full_unit_limit_before32_cut(self):
        t=source(33)+'\n'+'字'*513+'。';q=qualify(project(t,'discussion'),'record',t);self.assertFalse(q['preparse_eligible'])
    def test_fixed_segment_hash_choice(self):
        t=source(10)+'\n*列表\n'+source(12);p=project(t,'news_prose');a=qualify(p,'stable',t);b=qualify(p,'stable',t)
        self.assertEqual(a,b);self.assertTrue(a['preparse_eligible']);self.assertLessEqual(len(a['selected_segment']['unit_spans']),32)
    def test_han_numerator_domain_matches_denominator(self):
        self.assertEqual(_han_fraction('中文，。123'),.4);self.assertEqual(_han_fraction('⺀'),0.)
    def test_unicode_extended_han(self):self.assertEqual(_han_fraction('\U00020000字'),1.)
    def test_all_future_suffixes_preserve_character_prefix(self):
        from preparse import _seg
        t=source();q=qualify(project(t,'guide_prose'),'record',t);s=project(t,'guide_prose')['segments'][0]['text'];units=_seg.segment(s)[1]
        for p in q['selected_segment']['closed_points']:
            prefix=s[:p['projected_cutoff']];expected=[(u.start,u.end) for u in units[:p['target_unit_index']]]
            for suffix in ('','未来。','”未来。','\n任意改动。'):
                self.assertEqual([(u.start,u.end) for u in _seg.segment((prefix+suffix)[:len(prefix)])[1]],expected)

if __name__=='__main__':unittest.main()
