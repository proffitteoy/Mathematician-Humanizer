import copy,unittest
from project_wikitext import project
from source_risk_gate import source_risks,gated_metadata

class SourceRiskTests(unittest.TestCase):
    def test_fences_whole_record_quarantine(self):
        for fence in ('```python','~~~','````','   ~~~~~','\t```'):
            t='前文。\n'+fence+'\n不能当叙述的代码。\n后文。';meta,risks=gated_metadata(t,{})
            self.assertTrue(risks);self.assertFalse(project(t,'discussion',meta)['segments'])
    def test_unclosed_fence_no_spurious_prose(self):
        t='前文。\n```\n保持代码。';meta,risks=gated_metadata(t,{})
        self.assertFalse(project(t,'discussion',meta)['segments'])
    def test_retained_candidate_projection_identical(self):
        for t in ('正常[[目标|叙述]]。\n之后。','单个`字符。','双重``字符。','波浪~字符。','正常内容。\n<ref>来源</ref>'):
            m={'source_role':'unknown'};meta,risks=gated_metadata(t,m)
            self.assertFalse(risks);self.assertEqual(project(t,'discussion',m),project(t,'discussion',meta))
    def test_no_metadata_mutation(self):
        m={'rights_unresolved':False};old=copy.deepcopy(m);meta,risks=gated_metadata('```\n代码。',m)
        self.assertEqual(m,old);self.assertTrue(meta['rights_unresolved'])
    def test_oversized_tag_quarantined_before_projection(self):
        t='<'+('a'*5000)+'>\n文。\n文。\n</'+('a'*5000)+'>';meta,risks=gated_metadata(t,{})
        p=project(t,'discussion',meta);self.assertFalse(p['segments']);self.assertEqual(len(p['barriers']),1)
        self.assertLess(len(str(p)),2000)
    def test_oversized_tag_hyphen_colon_boundaries(self):
        for suffix in ('-custom',':custom'):
            tag='a'*1000+suffix;t='<'+tag+'>\n'+('文字。\n'*100)+'</'+tag+'>';meta,risks=gated_metadata(t,{})
            self.assertTrue(risks);p=project(t,'discussion',meta);self.assertEqual(len(p['barriers']),1);self.assertLess(len(str(p)),2000)
    def test_CR_and_entity_fence_boundaries(self):
        for t in ('前文。\r```python\r代码。\r```','&#96;&#96;&#96;python\n代码。','前文。&#10;```python&#10;代码。','前文。\r\n~~~\r\n代码。','前文。\u2028```python\u2028代码。'):
            meta,risks=gated_metadata(t,{})
            self.assertTrue(risks,t);self.assertFalse(project(t,'discussion',meta)['segments'])
    def test_detection_view_does_not_transform_retained_source(self):
        t='正常&amp;内容&#32;叙述。';meta,risks=gated_metadata(t,{})
        self.assertFalse(risks);self.assertEqual(project(t,'discussion'),project(t,'discussion',meta))
    def test_preexisting_rights_quarantine_retained(self):
        m,r=gated_metadata('普通。',{'rights_unresolved':True});self.assertTrue(m['rights_unresolved'])

if __name__=='__main__':unittest.main()
