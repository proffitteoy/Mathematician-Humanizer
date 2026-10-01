"""Source-free examples and adversaries; never opens a natural article."""
import copy
import random
import unittest
import continuity_projection as p

TABLE='| value* | other |\n|---|---|\n| 1 | 2 |\n'

class ContinuityTests(unittest.TestCase):
    def project(self,text):
        r=p.project_bytes(text.encode());self.assertTrue(p.validate_projection(text.encode(),r))
        self.assertFalse(r['semantic_equivalence_claimed']);self.assertFalse(r['model_admitted'])
        return r
    def texts(self,text):return [s['text'] for s in self.project(text)['segments']]
    def rehash(self,v):v['projection_sha256']=p.sha(p.canonical({k:x for k,x in v.items() if k!='projection_sha256'}))
    def test_plain_identity(self):self.assertEqual(self.texts('普通正文。'),['普通正文。'])
    def test_emphasis_continuity(self):self.assertEqual(self.texts('前**重点**后'),['前重点后'])
    def test_single_emphasis(self):self.assertEqual(self.texts('前*重点*后'),['前重点后'])
    def test_recursive_emphasis(self):self.assertEqual(self.texts('前**粗体*斜体*粗体**后'),['前粗体斜体粗体后'])
    def test_underscore_emphasis(self):self.assertEqual(self.texts('前 __重点__ 后'),['前 重点 后'])
    def test_link_visible_label(self):self.assertEqual(self.texts('前[标签](https://example.test)后'),['前标签后'])
    def test_link_title_invisible(self):self.assertEqual(self.texts('前[标签](https://example.test "hidden title")后'),['前标签后'])
    def test_recursive_label_emphasis(self):self.assertEqual(self.texts('前[**标签**和*内容*](https://example.test)后'),['前标签和内容后'])
    def test_emphasis_around_link(self):self.assertEqual(self.texts('前 *[标签](https://example.test)* 后'),['前 标签 后'])
    def test_commonmark_unresolved_flanking_stays_quarantined(self):self.assertEqual(self.texts('前*[标签](https://example.test)*后'),[])
    def test_reference_label(self):self.assertEqual(self.texts('前[标签][ref]后\n\n[ref]: https://example.test'),['前标签后'])
    def test_collapsed_reference(self):self.assertEqual(self.texts('前[标签][]后\n\n[标签]: https://example.test'),['前标签后'])
    def test_shortcut_reference(self):self.assertEqual(self.texts('前[标签]后\n\n[标签]: https://example.test'),['前标签后'])
    def test_standalone_link(self):self.assertEqual(self.texts('[标签](https://example.test)'),['标签'])
    def test_url_parentheses(self):self.assertEqual(self.texts('前[标签](https://example.test/a_(b))后'),['前标签后'])
    def test_inline_code_hard_boundary(self):self.assertEqual(self.texts('甲`code`乙'),['甲','乙'])
    def test_code_in_label(self):self.assertEqual(self.texts('前[字`code`字](https://example.test)后'),['前字','字后'])
    def test_quote_hard_boundary(self):self.assertEqual(self.texts('甲“quoted”乙'),['甲','乙'])
    def test_quote_in_link_label(self):self.assertEqual(self.texts('前[字“quote”字](https://example.test)后'),['前字','字后'])
    def test_unclosed_quote_in_link_label(self):self.assertEqual(self.texts('前[“open](https://example.test)后'),[])
    def test_entity_content_boundary(self):self.assertEqual(self.texts('前&amp;后'),['前','后'])
    def test_entity_inside_label(self):self.assertEqual(self.texts('前[甲&amp;乙](https://example.test)后'),['前甲','乙后'])
    def test_escape_content_boundary(self):self.assertEqual(self.texts(r'前\*后'),['前','后'])
    def test_math_content_boundary(self):self.assertEqual(self.texts('前$x$后'),['前','后'])
    def test_autolink_stays_boundary(self):self.assertEqual(self.texts('前<https://example.test>后'),['前','后'])
    def test_image_stays_barrier(self):self.assertEqual(self.texts('前![alt](image.png)后'),[])
    def test_image_inside_label(self):self.assertEqual(self.texts('前[![alt](image.png)](https://example.test)后'),[])
    def test_image_adjacent_link_caption(self):self.assertEqual(self.texts('![alt](image.png)\n\n[caption](https://example.test)\n\n正文'),['正文'])
    def test_standalone_bold_heading(self):self.assertEqual(self.texts('**heading**\n\n正文'),['正文'])
    def test_list_items_separate(self):self.assertEqual(self.texts('- 前**甲**后\n- 前[乙](https://example.test)后'),['前甲后','前乙后'])
    def test_softbreak_stays_boundary(self):self.assertEqual(self.texts('前**甲**\n乙'),['前甲','乙'])
    def test_label_softbreak_stays_boundary(self):self.assertEqual(self.texts('前[甲\n乙](https://example.test)后'),['前甲','乙后'])
    def test_crlf_astral_mapping(self):self.assertEqual(self.texts('😀**甲**\r\n乙e\u0301'),['😀甲','乙e\u0301'])
    def test_preserve_visible_punctuation(self):self.assertEqual(self.texts('A,**B**,[C](https://example.test)!'),['A,B,C!'])
    def test_multiple_proofs(self):
        r=self.project('前**甲**和[乙](https://example.test)后');s=r['segments'][0]
        self.assertGreaterEqual(len(s['continuity_edges']),4)
        self.assertEqual(len(s['source_map']),len(s['text']))
        self.assertTrue(all(e['kind']=='proved_syntax_only_elision' for e in s['continuity_edges']))
    def test_independent_commonmark_visible_leaf_equivalence(self):
        from markdown_it import MarkdownIt
        md=MarkdownIt('commonmark')
        examples=['前**重点**后','前*重点*后','前***重点***后','前[标签](https://example.test)后',
                  '前[**甲**和*乙*](https://example.test)后','前 *[标签](https://example.test)* 后',
                  'A,**B**,[C](https://example.test)!','前[甲](https://example.test "title")后']
        for s in examples:
            leaves=md.parseInline(s)[0].children
            expected=''.join(t.content for t in leaves if t.type=='text')
            self.assertEqual(self.texts(s),[expected])
    def test_emphasis_code_does_not_bridge(self):self.assertEqual(self.texts('前*甲`code`乙*后'),['前甲','乙后'])
    def test_encoded_quote_quarantine(self):self.assertEqual(self.texts('前&ldquo;x&rdquo;后'),[])
    def test_unresolved_reference_quarantine(self):self.assertEqual(self.texts('前[missing]后'),[])
    def test_unresolved_emphasis_quarantine(self):self.assertEqual(self.texts('前*missing'),[])
    def test_template_quarantine(self):self.assertEqual(self.texts('前{{ value }}后'),[])
    def test_table_star_annotation(self):self.assertEqual(self.texts(TABLE+'\n* note about marker'),[])
    def test_unmarked_caption_before_table(self):self.assertEqual(self.texts('Possible table caption\n\n'+TABLE),[])
    def test_list_caption_before_table(self):self.assertEqual(self.texts('- Possible caption\n- Continued caption\n\n'+TABLE),[])
    def test_table_plain_note(self):self.assertEqual(self.texts(TABLE+'\nNote: explanation'),[])
    def test_table_numbered_annotation(self):self.assertEqual(self.texts(TABLE+'\n1. explanation'),[])
    def test_table_lazy_list_continuation(self):self.assertEqual(self.texts(TABLE+'\n* note\nlazy continuation\n\n  continuation paragraph'),[])
    def test_table_separate_list(self):self.assertEqual(self.texts(TABLE+'\n* note\n\nparagraph\n\n- separate list'),[])
    def test_table_heading_boundary(self):self.assertEqual(self.texts(TABLE+'\n* note\n\n# Next\n\n正文'),['正文'])
    def test_table_thematic_boundary(self):self.assertEqual(self.texts(TABLE+'\nNote\n\n***\n\n正文'),['正文'])
    def test_consecutive_tables(self):self.assertEqual(self.texts(TABLE+'\nNote one\n\n'+TABLE+'\nNote two\n\n# Next\n\n正文'),['正文'])
    def test_table_quote_heading_no_reset(self):self.assertEqual(self.texts(TABLE+'\n> # Quoted heading\n> quoted\n\n* still annotation'),[])
    def test_table_list_heading_no_reset(self):self.assertEqual(self.texts(TABLE+'\n- # Nested heading\n\n* still annotation'),[])
    def test_quoted_table_scope_conservative(self):
        quoted='\n'.join('> '+x for x in TABLE.splitlines())
        self.assertEqual(self.texts(quoted+'\n\n* possible annotation'),[])
    def test_list_contained_table_scope(self):
        text='- container\n\n  |a|b|\n  |---|---|\n  |x|y|\n\n  * note\n\nOutside continuation'
        # The preceding container paragraph is also ambiguous as a caption.
        self.assertEqual(self.texts(text),[])
    def test_table_annotation_markup_no_escape(self):self.assertEqual(self.texts(TABLE+'\n* **note** [label](https://example.test)'),[])
    def test_hard_gap_tamper(self):
        raw='甲`x`乙';v=self.project(raw);s=v['segments'][0]
        s.update(text='甲乙',text_sha256=p.sha('甲乙'.encode()),source_spans=[[0,1],[4,5]],source_map=[[0,1,'identity',0],[4,5,'identity',0]],source_cover=[0,5]);v['segments']=v['segments'][:1];self.rehash(v)
        with self.assertRaises(p.ProjectionError):p.validate_projection(raw.encode(),v)
    def test_proof_tamper(self):
        raw='前**甲**后';v=self.project(raw);v['syntax_proofs'][0]['source_spans']=[[0,1]];self.rehash(v)
        with self.assertRaises(p.ProjectionError):p.validate_projection(raw.encode(),v)
    def test_boundary_tamper(self):
        raw='甲`x`乙';v=self.project(raw);v['content_boundaries']=[];self.rehash(v)
        with self.assertRaises(p.ProjectionError):p.validate_projection(raw.encode(),v)
    def test_schema_tamper(self):
        for key,value in [('counts',{}),('source_bytes',0),('profile','wrong'),('extra',True),('natural_validation_performed',True)]:
            v=self.project('正文');v[key]=value;self.rehash(v)
            with self.assertRaises(p.ProjectionError):p.validate_projection('正文'.encode(),v)
    def test_synthetic_fuzz(self):
        rng=random.Random(62002);alphabet='ab中文😀\r\n\t *_`[]<>$\\|{}#;:!~^&"'
        for _ in range(200):self.project(''.join(rng.choice(alphabet) for _ in range(rng.randrange(0,90))))

if __name__=='__main__':unittest.main(verbosity=2)
