"""Synthetic-only regression tests. No natural source files are opened."""
import copy
import json
import random
import unittest

import markdown_projection as p


class ProjectionTests(unittest.TestCase):
    def parse(self, text):
        value = p.project_bytes(text.encode())
        self.assertTrue(p.validate_projection(text.encode(), value))
        self.assertFalse(value['model_admitted'])
        self.assertFalse(value['split_eligible'])
        self.assertEqual(value['human_origin'], 'unknown')
        return value

    def texts(self, text):
        return [s['text'] for s in self.parse(text)['segments']]

    def role(self, text, role):
        self.assertIn(role,self.parse(text)['counts']['role_codepoints'])

    def blocked(self, text, issue):
        v=self.parse(text)
        self.assertIn(issue,v['issues'])
        self.assertEqual(v['segments'],[])

    def test_plain_chinese(self): self.assertEqual(self.texts('正文。'),['正文。'])
    def test_empty(self): self.assertEqual(self.texts(''),[])
    def test_blank(self): self.assertEqual(self.texts(' \n\t\r\n'),[])
    def test_yaml(self): self.assertEqual(self.texts('---\ntitle: unsafe\n---\n正文。'),['正文。'])
    def test_yaml_object_not_evaluated(self): self.assertEqual(self.texts('---\na: !!python/object/apply:os.system [bad]\n---\n正文'),['正文'])
    def test_toml(self): self.role('+++\na="x"\n+++\n正文','frontmatter')
    def test_yaml_dot_end(self): self.role('---\na: x\n...\n正文','frontmatter')
    def test_unclosed_frontmatter(self): self.blocked('---\na: x\n正文','unresolved_frontmatter')
    def test_bom(self): self.assertEqual(self.texts('\ufeff正文'),['正文'])
    def test_atx_heading(self): self.assertEqual(self.texts('# 标题\n\n正文'),['正文'])
    def test_setext_heading(self): self.assertEqual(self.texts('标题\n=====\n\n正文'),['正文'])
    def test_thematic_break(self): self.role('正文\n\n***\n\n末尾','thematic_break')
    def test_fenced_code(self): self.assertEqual(self.texts('```python\n正文不是正文\n```\n\n正文'),['正文'])
    def test_tilde_fence(self): self.role('~~~\nx\n~~~\n','fenced_code')
    def test_long_fence(self): self.assertEqual(self.texts('````\n```\n````\n\n正文'),['正文'])
    def test_unclosed_fence(self): self.blocked('正文\n\n```\nx','unclosed_fenced_code')
    def test_indented_code(self): self.assertEqual(self.texts('    hidden\n\n正文'),['正文'])
    def test_tab_code(self): self.role('\thidden\n','indented_code')
    def test_blockquote_lazy(self): self.assertEqual(self.texts('> 引用\n仍是引用\n\n正文'),['正文'])
    def test_nested_quote(self): self.assertEqual(self.texts('> > quote\n\n正文'),['正文'])
    def test_inline_quote(self): self.assertEqual(self.texts('前“引文”后'),['前','后'])
    def test_ascii_quote(self): self.assertEqual(self.texts('前"引文"后'),['前','后'])
    def test_unclosed_quote(self): self.blocked('前“引文','unresolved_inline_quote')
    def test_bullet_list(self): self.assertEqual(self.texts('- 第一。\n- 第二。'),['第一。','第二。'])
    def test_ordered_list(self): self.assertEqual(self.texts('1. 第一。\n2. 第二。'),['第一。','第二。'])
    def test_nested_list(self): self.assertEqual(self.texts('- 第一。\n  - 第二。'),['第一。','第二。'])
    def test_task_list(self): self.role('- [x] 完成。','task_list_marker')
    def test_list_continuation(self): self.assertEqual(self.texts('- 第一。\n  第二。'),['第一。','第二。'])
    def test_emphasis_gap(self): self.assertEqual(self.texts('前**中**后'),['前','中','后'])
    def test_unclosed_emphasis(self): self.blocked('前*未闭合','unresolved_emphasis_or_literal_marker')
    def test_inline_code(self): self.assertEqual(self.texts('前`code`后'),['前','后'])
    def test_multiline_code(self): self.assertEqual(self.texts('前`a\nb`后'),['前','后'])
    def test_unclosed_inline_code(self): self.blocked('前`code','unresolved_backtick')
    def test_link(self): self.assertEqual(self.texts('前[标签](https://example.test)后'),['前','后'])
    def test_nested_link_text(self): self.assertEqual(self.texts('前[**标签**](https://example.test)后'),['前','后'])
    def test_reference(self): self.assertEqual(self.texts('前[标签][r]后\n\n[r]: https://example.test\n'),['前','后'])
    def test_reference_duplicate(self): self.blocked('[r]: a\n[r]: b\n\n正文','duplicate_link_reference')
    def test_unresolved_reference(self): self.blocked('前[missing]后','unresolved_inline_syntax')
    def test_image(self): self.assertEqual(self.texts('前![alt](image.png "title")后'),[])
    def test_image_only(self): self.assertEqual(self.texts('![alt](image.png)'),[])
    def test_caption(self): self.assertEqual(self.texts('图1：内容说明。\n\n正文'),['正文'])
    def test_caption_chinese_ordinal(self):self.assertEqual(self.texts('图一：说明\n\n正文'),['正文'])
    def test_caption_roman(self):self.assertEqual(self.texts('Figure IV: caption\n\n正文'),['正文'])
    def test_caption_explicit(self):self.assertEqual(self.texts('图片说明：照片中的人物\n\n正文'),['正文'])
    def test_caption_bare_label(self):self.assertEqual(self.texts('图：说明内容\n\n表: 说明内容\n\n正文'),['正文'])
    def test_caption_after_image(self):self.assertEqual(self.texts('![alt](a.png)\n\n*照片说明*\n\n正文'),['正文'])
    def test_caption_same_paragraph(self):self.assertEqual(self.texts('![alt](a.png)\n照片说明\n\n正文'),[])
    def test_unmarked_adjacent_caption(self):self.assertEqual(self.texts('![alt](a.png)\n\n说明内容\n\n正文'),['正文'])
    def test_unmatched_closing_quote(self):self.blocked('前”后','unresolved_closing_quote')
    def test_standalone_bold_heading(self):self.assertEqual(self.texts('**标题**\n\n正文'),['正文'])
    def test_nested_quote(self):self.blocked('前“外层“内层”后半段”尾','unresolved_quote_nesting')
    def test_entity_quote(self):self.blocked('前&ldquo;引文&rdquo;后','unresolved_encoded_role_delimiter')
    def test_numeric_quote(self):self.blocked('前&#34;引文&#34;后','unresolved_encoded_role_delimiter')
    def test_escaped_quote(self):self.blocked(r'前\"引文\"后','unresolved_escaped_quote_scope')
    def test_encoded_cross_paragraph_quote(self):self.blocked('前&ldquo;引文\n\n后段&rdquo;后','unresolved_encoded_role_delimiter')
    def test_encoded_html(self):self.blocked('&lt;blockquote&gt;\n\n引文\n\n&lt;/blockquote&gt;','unresolved_encoded_role_delimiter')
    def test_encoded_fence(self):self.blocked('&#96;&#96;&#96;\n\ncode\n\n&#96;&#96;&#96;','unresolved_encoded_role_delimiter')
    def test_encoded_math(self):self.blocked('&#36;&#36;\n\nmath\n\n&#36;&#36;','unresolved_encoded_role_delimiter')
    def test_escaped_cross_paragraph_quote(self):self.blocked('前\\"引文\n\n后段\\"后','unresolved_escaped_quote_scope')
    def test_leading_blank_frontmatter(self):self.assertEqual(self.texts('\n+++\ntitle = A\nauthor = B\n+++\n\n正文'),['正文'])
    def test_table(self): self.assertEqual(self.texts('| a | b |\n|---|---|\n| x | y |\n\n正文'),['正文'])
    def test_footnote(self): self.assertEqual(self.texts('前[^a]后\n\n[^a]: 引文\n    续文\n\n正文'),['前','后','正文'])
    def test_footnote_lazy(self): self.assertEqual(self.texts('[^a]: 引文\n仍属引文\n\n正文'),['正文'])
    def test_inline_dollar_math(self): self.assertEqual(self.texts('前$x+y$后'),['前','后'])
    def test_inline_backslash_math(self): self.assertEqual(self.texts(r'前\(x+y\)后'),['前','后'])
    def test_display_math(self): self.assertEqual(self.texts('$$\nx+y\n$$\n\n正文'),['正文'])
    def test_display_bracket_math(self): self.assertEqual(self.texts('\\[\nx+y\n\\]\n\n正文'),['正文'])
    def test_unclosed_math(self): self.blocked('前$x','unresolved_inline_math')
    def test_unclosed_display_math(self): self.blocked('$$\nx+y','unresolved_display_math')
    def test_html_scope(self): self.assertEqual(self.texts('<div>\n\n不是正文\n\n</div>\n\n正文'),['正文'])
    def test_inline_html_whole_line(self): self.assertEqual(self.texts('前<span>不是正文</span>后\n\n正文'),['正文'])
    def test_html_comment(self): self.assertEqual(self.texts('<!-- include external -->\n\n正文'),['正文'])
    def test_html_script_not_executed(self): self.assertEqual(self.texts('<script>fetch("https://invalid.test")</script>\n\n正文'),['正文'])
    def test_html_attribute_angle(self): self.assertEqual(self.texts('<div data-x=">">text</div>\n\n正文'),['正文'])
    def test_unclosed_html(self): self.blocked('<div>\n\nhidden','unresolved_html_scope')
    def test_mismatched_html(self): self.blocked('<div><span>x</div>','unresolved_html_nesting')
    def test_template(self): self.blocked('正文\n\n{% if x %}\nhidden\n{% endif %}','unresolved_template_scope')
    def test_inline_template(self): self.blocked('前 {{ value }} 后','unresolved_template_scope')
    def test_template_in_code(self): self.assertEqual(self.texts('前`{{ x }}`后'),['前','后'])
    def test_template_in_fence(self): self.assertEqual(self.texts('```\n{% x %}\n```\n\n正文'),['正文'])
    def test_entity_barrier(self): self.assertEqual(self.texts('前&amp;后'),['前','后'])
    def test_unknown_entity(self): self.blocked('前&NotAnEntity;后','unresolved_entity')
    def test_escape_barrier(self): self.assertEqual(self.texts(r'前\*后'),['前','后'])
    def test_autolink(self): self.assertEqual(self.texts('前<https://example.test>后'),['前','后'])
    def test_bare_url(self): self.assertEqual(self.texts('前 https://example.test 后'),['前 ',' 后'])
    def test_crlf_unicode(self): self.assertEqual(self.texts('甲😀\r\n乙e\u0301\r丙'),['甲😀','乙e\u0301','丙'])
    def test_softbreak_is_gap(self): self.assertEqual(self.texts('甲\n乙'),['甲','乙'])
    def test_hardbreak_is_gap(self): self.assertEqual(self.texts('甲  \n乙'),['甲','乙'])
    def test_no_cross_gap_join(self):
        v=self.parse('甲`hidden`乙')
        self.assertFalse(v['joining_across_gaps_permitted'])
        self.assertTrue(all(s['text']!='甲乙' for s in v['segments']))
    def test_exact_duplicate_text_offsets(self):
        v=self.parse('同文\n\n同文')
        self.assertEqual([s['source_char_span'] for s in v['segments']],[[0,2],[4,6]])
    def test_invalid_utf8(self):
        with self.assertRaises(p.ProjectionError): p.project_bytes(b'\xff')
    def test_nul(self):
        with self.assertRaises(p.ProjectionError): p.project_bytes(b'a\0b')
    def test_byte_cap(self):
        with self.assertRaises(p.ProjectionError): p.project_bytes(b'x'*(p.MAX_BYTES+1))
    def test_inline_cap(self):
        with self.assertRaises(p.ProjectionError): p.project_bytes(b'x'*(p.MAX_INLINE_CHARS+1))
    def test_map_tamper(self):
        v=self.parse('正文'); v['segments'][0]['source_map'][0][0]=1
        with self.assertRaises(p.ProjectionError): p.validate_projection('正文'.encode(),v)
    def test_hash_tamper(self):
        v=self.parse('正文'); v['human_origin']='verified'
        with self.assertRaises(p.ProjectionError): p.validate_projection('正文'.encode(),v)
    def test_gap_tamper_rehash(self):
        v=self.parse('前`code`后');v['gaps']=[]
        v['projection_sha256']=p.sha(json.dumps({k:x for k,x in v.items() if k!='projection_sha256'},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
        with self.assertRaises(p.ProjectionError):p.validate_projection('前`code`后'.encode(),v)
    def test_factual_schema_tampering_rehashed(self):
        mutators=[lambda v:v.update(raw_bytes=0),lambda v:v.update(raw_codepoints=0),
            lambda v:v.update(structural_status='quarantined'),lambda v:v.update(dependencies={}),
            lambda v:v.update(linguistic_parser_run=True),lambda v:v.update(extra='unbound'),
            lambda v:v.pop('flags'),lambda v:v['counts'].update(projected_codepoints=0),
            lambda v:v['counts']['role_codepoints'].update(body_prose_candidate=0),
            lambda v:v['segments'][0].update(segment_id='forged'),
            lambda v:v['segments'][0].update(raw_spans=[[0,1]]),
            lambda v:v['segments'][0].update(internally_contiguous=False),
            lambda v:v['segments'][0]['source_map'][0].__setitem__(0,False)]
        for mutate in mutators:
            v=self.parse('正文');mutate(v)
            v['projection_sha256']=p.sha(json.dumps({k:x for k,x in v.items() if k!='projection_sha256'},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
            with self.assertRaises(p.ProjectionError):p.validate_projection('正文'.encode(),v)
    def test_distinct_frame(self):
        v=self.parse('正文')
        self.assertEqual(v['source_frame'],'historical_blog_markdown')
        self.assertNotIn('wiki',v['profile'])
    def test_determinism(self): self.assertEqual(self.parse('前*中*后'),self.parse('前*中*后'))
    def test_synthetic_fuzz(self):
        rng=random.Random(61001)
        alphabet='abc中文😀\r\n\t *_`[]<>$\\|{}#;:!~^&"'
        for _ in range(200):
            s=''.join(rng.choice(alphabet) for _ in range(rng.randrange(0,100)))
            self.parse(s)


if __name__ == '__main__': unittest.main(verbosity=2)
