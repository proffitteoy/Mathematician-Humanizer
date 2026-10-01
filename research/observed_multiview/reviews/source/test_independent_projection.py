"""Independent original synthetic role and mapping adversaries; no body I/O."""
import hashlib,json,pathlib,sys,unittest
ROOT=pathlib.Path('/workspace/shared/style-scale10-source-v01/public');sys.path.insert(0,str(ROOT))
from project_wikitext import project,canonical
from projection_contract import validate_projection

class IndependentProjectionTests(unittest.TestCase):
 def visible(self,s):
  p=project(s,'news_prose');validate_projection(s,p);return ''.join(x['text']for x in p['segments'])
 def test_plain_narrative_identity(self):
  s='原始叙述第一行。\r\n独立叙述第二行。\n';self.assertEqual(self.visible(s),s)
 def test_harmless_entity_kept_with_complete_source_map(self):self.assertEqual(self.visible('甲&amp;乙&NotEqualTilde;丙。\n'),'甲&乙≂̸丙。\n')
 def test_numeric_entity_quote(self):self.assertNotIn('未决引用',self.visible('甲&#8220;未决引用&#8221;乙。'))
 def test_numeric_entity_contact(self):self.assertNotIn('user@example.com',self.visible('联系 user&#64;example.com'))
 def test_raw_translation_marker_without_metadata(self):self.assertNotIn('翻译正文',self.visible('{{Translated from|en|A}}\n翻译正文。\n'))
 def test_numeric_multiline_quote_scope(self):self.assertNotIn('仍在引用中',self.visible('甲。\n&#8220;开始。\n仍在引用中。\n结尾。&#8221;\n乙。\n'))
 def test_named_multiline_quote_scope(self):self.assertNotIn('仍在引用中',self.visible('甲。\n&ldquo;开始。\n仍在引用中。\n结尾。&rdquo;\n乙。\n'))
 def test_mixed_entity_raw_quote_scope(self):self.assertNotIn('仍在引用中',self.visible('甲。\n&ldquo;开始。\n仍在引用中。\n结尾。”\n乙。\n'))
 def test_mixed_raw_entity_quote_scope(self):self.assertNotIn('仍在引用中',self.visible('甲。\n“开始。\n仍在引用中。\n结尾。&rdquo;\n乙。\n'))
 def test_nested_same_quote_fail_closed(self):self.assertNotIn('仍在外层',self.visible('甲。\n“外层开始。\n“内层。”\n仍在外层。\n外层结束。”\n乙。\n'))
 def test_unclosed_ascii_quote_fail_closed(self):self.assertNotIn('仍属未决引用',self.visible('甲。\n"未闭合引用。\n仍属未决引用。\n'))
 def test_unclosed_entity_quote_fail_closed(self):self.assertNotIn('仍属未决引用',self.visible('甲。\n&ldquo;未闭合引用。\n仍属未决引用。\n'))
 def test_markup_entity_not_executed(self):self.assertNotIn('危险代码',self.visible('&#60;script&#62;危险代码&#60;/script&#62;'))
 def test_template_barrier_never_bridged(self):
  p=project('甲。\n{{未知|内部}}\n乙。\n','guide_prose');validate_projection('甲。\n{{未知|内部}}\n乙。\n',p)
  self.assertEqual([s['text']for s in p['segments']],['甲。\n','乙。\n'])
 def test_bad_cache_hash_rejected(self):
  s='甲。';p=project(s,'news_prose');p['segments'][0]['text']='乙。'
  with self.assertRaises(ValueError):validate_projection(s,p)

if __name__=='__main__':unittest.main(verbosity=2)
