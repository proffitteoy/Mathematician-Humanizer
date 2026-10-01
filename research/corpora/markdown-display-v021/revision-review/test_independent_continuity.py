"""Independent source-free continuity, annotation and forged-proof cases."""
import copy
import json
import os
import pathlib
import sys
import types
import unittest

SOURCE=pathlib.Path(os.environ.get('CONTINUITY_PROJECTOR_SOURCE','/workspace/shared/style-markdown-projection-v02/public/continuity_projection.py'))
p=types.ModuleType('continuity_projection')
p.__file__=str(SOURCE);sys.modules[p.__name__]=p
exec(compile(SOURCE.read_bytes(),str(SOURCE),'exec'),p.__dict__)

TABLE='|a|b|\n|---|---|\n|x|y|\n'

class IndependentContinuity(unittest.TestCase):
    def project(self,text):
        result=p.project_bytes(text.encode());p.validate_projection(text.encode(),result)
        kinds=[]
        for r in result['regions']:kinds.extend([r['kind']]*(r['end']-r['start']))
        self.assertEqual(len(kinds),len(text))
        observed=[]
        for seg in result['segments']:
            indices=[i for a,b in seg['source_spans'] for i in range(a,b)]
            self.assertEqual(seg['text'],''.join(text[i] for i in indices))
            self.assertEqual(seg['source_map'],[[i,i+1,'identity',0] for i in indices])
            for left,right in zip(indices,indices[1:]):
                self.assertLess(left,right)
                if right>left+1:self.assertTrue(all(x=='syntax_only' for x in kinds[left+1:right]))
            observed.extend(indices)
        self.assertEqual(observed,[i for i,k in enumerate(kinds) if k=='content'])
        return result
    def texts(self,text):return [s['text'] for s in self.project(text)['segments']]
    def no_annotation(self,text):
        self.assertFalse(any('注释残留' in s for s in self.texts(text)))

    def test_sibling_item_cannot_close_table_scope(self):
        self.no_annotation('- Caption\n\n  |a|b|\n  |---|---|\n  |x|y|\n\n- # Sibling heading\n\n  注释残留\n\nRoot tail')
    def test_separate_list_cannot_close_table_scope(self):
        self.no_annotation('- Caption\n\n  |a|b|\n  |---|---|\n  |x|y|\n\ntext between\n\n- # Separate list\n\n  注释残留')
    def test_separate_quote_cannot_close_table_scope(self):
        self.no_annotation('> |a|b|\n> |---|---|\n> |x|y|\n\n> # Separate quote\n> quoted\n\n注释残留')
    def test_same_item_heading_can_end_scope(self):
        self.assertEqual(self.texts('- Caption\n\n  |a|b|\n  |---|---|\n  |x|y|\n\n  # Same item\n\n  正文'),['正文'])
    def test_same_root_heading_can_end_scope(self):
        self.assertEqual(self.texts(TABLE+'\n* note\n\n# Heading\n\n正文'),['正文'])
    def test_nested_thematic_break_cannot_close_root_scope(self):
        self.no_annotation(TABLE+'\n> ***\n\n注释残留')
    def test_annotated_second_table_is_barrier(self):
        self.no_annotation(TABLE+'\nFirst note\n\n'+TABLE+'\n注释残留')
    def test_caption_with_links_not_recovered(self):
        self.assertEqual(self.texts('Caption [label](url)\n\n'+TABLE),[])

    def test_visible_link_label(self):
        self.assertEqual(self.texts('前[甲](a)[乙](b)后'),['前甲乙后'])
    def test_empty_visible_link_label(self):
        self.assertEqual(self.texts('前[](https://example.test)后'),['前后'])
    def test_visible_spaces_preserved(self):
        self.assertEqual(self.texts('前[  甲  ](https://example.test)后'),['前  甲  后'])
    def test_destination_title_not_visible(self):
        self.assertEqual(self.texts('前[甲](https://example.test\n "invisible title")后'),['前甲后'])
    def test_visible_label_newline_is_barrier(self):
        self.assertEqual(self.texts('前[甲\r\n乙](https://example.test)后'),['前甲','乙后'])
    def test_label_inline_code_is_barrier(self):
        self.assertEqual(self.texts('前[甲`code`乙](url)后'),['前甲','乙后'])
    def test_label_quote_is_barrier(self):
        self.assertEqual(self.texts('前[甲“引文”乙](url)后'),['前甲','乙后'])
    def test_label_entity_is_barrier(self):
        self.assertEqual(self.texts('前[甲&amp;乙](url)后'),['前甲','乙后'])
    def test_label_escape_is_barrier(self):
        self.assertEqual(self.texts(r'前[甲\*乙](url)后'),['前甲','乙后'])
    def test_label_math_is_barrier(self):
        self.assertEqual(self.texts('前[甲$x$乙](url)后'),['前甲','乙后'])
    def test_label_footnote_is_barrier(self):
        self.assertEqual(self.texts('前[甲[^x]乙](url)后'),['前甲','乙后'])
    def test_label_encoded_quotes_quarantine(self):
        self.assertEqual(self.texts('前[&ldquo;引文&rdquo;](url)后'),[])
    def test_label_unbalanced_quote_quarantine(self):
        self.assertEqual(self.texts('前[“引文](url)后'),[])
    def test_image_in_label_not_recovered(self):
        self.assertEqual(self.texts('前[![alt](image)](url)后'),[])
    def test_autolink_does_not_gain_continuity(self):
        self.assertEqual(self.texts('前<https://example.test>后'),['前','后'])
    def test_emphasis_across_line_break(self):
        self.assertEqual(self.texts('甲**乙\n丙**丁'),['甲乙','丙丁'])
    def test_nested_emphasis_inside_link(self):
        self.assertEqual(self.texts('前[**甲*乙*丙**](url)后'),['前甲乙丙后'])
    def test_combining_astral_raw_map(self):
        self.assertEqual(self.texts('😀**e\u0301**[甲](url)后'),['😀e\u0301甲后'])
    def test_repeated_text_has_distinct_provenance(self):
        v=self.project('同[同](url)同\n\n同[同](url)同')
        self.assertEqual([s['text'] for s in v['segments']],['同同同','同同同'])
        self.assertLess(v['segments'][0]['source_cover'][1],v['segments'][1]['source_cover'][0])

class ForgedProofCases(unittest.TestCase):
    def rehash(self,r):r['projection_sha256']=p.sha(p.canonical({k:v for k,v in r.items() if k!='projection_sha256'}))
    def forged(self,raw,mutate):
        r=p.project_bytes(raw.encode());mutate(r);self.rehash(r)
        with self.assertRaises((p.ProjectionError,ValueError,KeyError,IndexError,TypeError)):
            p.validate_projection(raw.encode(),r)
    def test_drop_content_boundary(self):
        self.forged('甲`code`乙',lambda r:r.update(content_boundaries=[]))
    def test_false_context_role(self):
        self.forged('前**甲**后',lambda r:r['segments'][0].update(context_role='verified_original'))
    def test_false_proof_kind(self):
        self.forged('前**甲**后',lambda r:r['syntax_proofs'][0].update(kind='visible_content'))
    def test_false_proof_span(self):
        self.forged('前**甲**后',lambda r:r['syntax_proofs'][0].update(source_spans=[[0,1]]))
    def test_false_elision_edge(self):
        self.forged('前**甲**后',lambda r:r['segments'][0]['continuity_edges'][0].update(source_gap=[0,1]))
    def test_false_old_certificate_compatibility(self):
        self.forged('正文',lambda r:r.update(old_exclusion_certificate_applies=True))

if __name__=='__main__':unittest.main(verbosity=2)
