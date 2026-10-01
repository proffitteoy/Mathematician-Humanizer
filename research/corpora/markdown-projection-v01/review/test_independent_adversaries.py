"""Synthetic-only independent role and integrity regressions.

The reviewed implementation is loaded by source bytes; no acquired prose is used.
Set MARKDOWN_PROJECTOR_SOURCE to review a distinct frozen revision.
"""
import copy
import json
import os
import pathlib
import sys
import types
import unittest

SOURCE = pathlib.Path(os.environ.get('MARKDOWN_PROJECTOR_SOURCE', '/workspace/shared/style-markdown-projection-v01/public/markdown_projection.py'))
p = types.ModuleType('markdown_projection')
p.__file__ = str(SOURCE)
sys.modules[p.__name__] = p
exec(compile(SOURCE.read_bytes(), str(SOURCE), 'exec'), p.__dict__)

class IndependentRoleCases(unittest.TestCase):
    def projected(self, text):
        v = p.project_bytes(text.encode())
        p.validate_projection(text.encode(), v)
        # Each output stays entirely within a single contiguous original slice.
        for segment in v['segments']:
            a,b = segment['source_char_span']
            self.assertEqual(segment['text'], text[a:b])
            self.assertEqual(segment['source_map'], [[i,i+1,'identity',0] for i in range(a,b)])
        return v

    def excluded(self, text, forbidden):
        v = self.projected(text)
        self.assertFalse(any(forbidden in s['text'] for s in v['segments']), v['segments'])

    def test_nested_same_quote(self):
        self.excluded('前“外层“内层”后半段”尾', '后半段')

    def test_nested_multiline_quote(self):
        self.excluded('前“外层\n“内层”\n剩余引文”后', '剩余引文')

    def test_named_quote_entities(self):
        for op,cl in [('&ldquo;','&rdquo;'),('&laquo;','&raquo;'),('&lsquo;','&rsquo;')]:
            with self.subTest(op=op): self.excluded('前'+op+'引文'+cl+'后','引文')

    def test_numeric_quote_entities(self):
        for op in ['&#34;','&#x22;','&#X22;']:
            with self.subTest(op=op): self.excluded('前'+op+'引文'+op+'后','引文')

    def test_escaped_ascii_quotes(self):
        self.excluded(r'前\"引文\"后','引文')

    def test_entity_quotes_across_blocks(self):
        self.excluded('&ldquo;\n\n第一引文段。\n\n第二引文段。\n\n&rdquo;', '引文段')

    def test_escaped_quotes_across_blocks(self):
        self.excluded('\\"\n\n引文段落\n\n\\"', '引文段落')

    def test_encoded_html_scope(self):
        self.excluded('&lt;blockquote&gt;\n\n引文。\n\n&lt;/blockquote&gt;', '引文')

    def test_encoded_fence_scope(self):
        self.excluded('&#96;&#96;&#96;\n\n代码文本\n\n&#96;&#96;&#96;', '代码文本')

    def test_encoded_math_scope(self):
        self.excluded('&#36;&#36;\n\n公式文本\n\n&#36;&#36;', '公式文本')

    def test_nested_emphasis_entity_quote(self):
        self.excluded('*&#34;引文&#34;*', '引文')

    def test_image_italic_caption(self):
        self.excluded('![照片](photo.png)\n\n*照片说明文字*\n\n正文', '照片说明文字')

    def test_image_inline_caption(self):
        self.excluded('![照片](photo.png) 照片说明文字\n\n正文', '照片说明文字')

    def test_image_adjacent_plain_caption(self):
        self.excluded('![照片](photo.png)\n\n照片说明文字\n\n正文', '照片说明文字')

    def test_unmatched_typographic_closer(self):
        v=self.projected('前”引文碎片')
        self.assertEqual(v['segments'], [])

    def test_explicit_caption_variants(self):
        for prefix in ['图：','图片说明：','图一：','Figure IV: ']:
            with self.subTest(prefix=prefix): self.excluded(prefix+'说明内容\n\n正文','说明内容')

    def test_standalone_bold_heading(self):
        self.excluded('**单独标题**\n\n正文', '单独标题')

    def test_displaced_toml_frontmatter(self):
        self.excluded('\n+++\ntitle = metadata\nauthor = metadata\n+++\n\n正文','metadata')

    def test_comment_math_code_scopes(self):
        for text in ['<!--\n\n隐藏\n\n-->\n\n正文', '<math>\n\n隐藏\n\n</math>\n\n正文', '- ```\n  隐藏\n  ```\n\n正文']:
            with self.subTest(text=text): self.excluded(text,'隐藏')

    def test_literal_gaps_no_join(self):
        v=self.projected('甲`code`乙&amp;丙')
        self.assertEqual([x['text'] for x in v['segments']], ['甲','乙','丙'])

    def test_unicode_crlf_map(self):
        v=self.projected('甲😀\r\n乙e\u0301\r丙')
        self.assertEqual([x['text'] for x in v['segments']], ['甲😀','乙e\u0301','丙'])

class IndependentValidatorCases(unittest.TestCase):
    def check_forged(self, field, value):
        raw='正文'.encode();v=p.project_bytes(raw);v[field]=value
        v['projection_sha256']=p.sha(json.dumps({k:x for k,x in v.items() if k!='projection_sha256'},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
        with self.assertRaises((p.ProjectionError,ValueError,KeyError,TypeError)):
            p.validate_projection(raw,v)

    def test_raw_byte_count(self): self.check_forged('raw_bytes',999)
    def test_raw_character_count(self): self.check_forged('raw_codepoints',999)
    def test_aggregate_counts(self): self.check_forged('counts',{'segments':999,'projected_codepoints':999,'role_codepoints':{}})
    def test_quarantined_status_with_segments(self): self.check_forged('structural_status','quarantined')
    def test_false_parser_claim(self): self.check_forged('linguistic_parser_run',True)
    def test_dependency_binding(self): self.check_forged('dependencies',{})
    def test_unknown_assistance(self): self.check_forged('assistance_status','unassisted_human')
    def test_unknown_role_claim(self): self.check_forged('source_role','verified_human_original')

if __name__ == '__main__': unittest.main(verbosity=2)
