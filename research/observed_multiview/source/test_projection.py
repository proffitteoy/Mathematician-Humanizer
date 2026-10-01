import copy,hashlib,unittest
from project_wikitext import project,exclusion_project,canonical,sha
from projection_contract import validate_projection


def reseal(p):
    p['projection_sha256']=hashlib.sha256(canonical({k:v for k,v in p.items() if k!='projection_sha256'})).hexdigest()
    return p


class ProjectionTests(unittest.TestCase):
    def checked(self,text,frame='discussion',metadata=None):
        p=project(text,frame,metadata);validate_projection(text,p);return p
    def test_identity_and_mixed_newlines(self):
        text='第一行叙述。\r\n第二行叙述。\n\n第三行叙述。\r第四行叙述。'
        p=self.checked(text);self.assertEqual(p['segments'][0]['text'],text)
    def test_literal_links_and_emphasis(self):
        t="我们参观[[北京|首都]]。 阅读[https://example.test 说明]以及'''文字'''和''样式''。"
        p=self.checked(t);self.assertEqual(p['segments'][0]['text'],'我们参观首都。 阅读说明以及文字和样式。')
    def test_entity_one_to_many(self):
        t='文字&amp;内容&NotEqualTilde;说明。'
        p=self.checked(t);self.assertEqual(p['segments'][0]['text'],'文字&内容≂̸说明。')
        maps=p['segments'][0]['source_map'];self.assertTrue(any(a[:2]==b[:2] and b[3]==1 for a,b in zip(maps,maps[1:])))
    def test_numeric_entities(self):
        self.assertEqual(self.checked('文本&#20013;&#x6587;。')['segments'][0]['text'],'文本中文。')
    def test_unknown_entities_fail_closed(self):
        for t in ('文本&unknown;。','文本&#0;。','文本&#xD800;。','文本&amp缺少;。'):
            self.assertFalse(self.checked(t)['segments'])
    def test_nested_templates_barrier(self):
        t='甲。\n{{模板|{{内部|文本}}}}\n乙。'
        p=self.checked(t);self.assertEqual([s['text'] for s in p['segments']],['甲。\n','乙。'])
    def test_inline_template_reject_whole_line(self):
        p=self.checked('不保留{{模板}}剩余词语。');self.assertFalse(p['segments'])
    def test_unclosed_template_no_later_leak(self):
        p=self.checked('保留。\n{{开始\n不保留。\n仍不保留。');self.assertEqual(p['segments'][0]['text'],'保留。\n');self.assertEqual(len(p['segments']),1)
    def test_multiline_comment_barrier(self):
        p=self.checked('前段。\n<!--开始\n继续-->\n后段。');self.assertEqual(len(p['segments']),2)
    def test_nested_html_no_inner_leak(self):
        p=self.checked('<div><div>引用。</div>仍然引用。</div>\n叙述。');self.assertEqual(p['segments'][0]['text'],'叙述。')
    def test_multiline_quote_and_code_barriers(self):
        for construct in ('<blockquote>引文。\n另一行。</blockquote>','<pre>代码。\n代码。</pre>','“引语。\n后半段。”'):
            p=self.checked('叙述。\n'+construct+'\n后文。');self.assertEqual(len(p['segments']),2)
    def test_list_heading_indentation_category_file(self):
        for line in ('* 列表内容。','= 标题 =',' 层级内容。','[[Category:范围]]','[[File:图像.jpg|图像文字]]','[[用户:名字|名字]]','[[en:Example]]','电话：12345','邮箱：a@example.test'):
            p=self.checked('甲。\n'+line+'\n乙。');self.assertEqual(len(p['segments']),2,line)
    def test_link_with_template_and_unknown_markers(self):
        for t in ('[[目标|{{模板}}]]','[[未闭合','[https://example.test]','甲}}乙。','甲<unknown>乙。'):
            self.assertFalse(self.checked(t)['segments'],t)
    def test_pure_markup_emits_nothing(self):
        self.assertFalse(self.checked('{{模板}}\n<!--注释-->\n[[分类:项目]]')['segments'])
    def test_source_hash_change_refuses_cache(self):
        p=self.checked('第一段。')
        with self.assertRaisesRegex(ValueError,'source_or_profile'):validate_projection('第二段。',p)
    def test_source_map_tampering_and_empty_range_rejected(self):
        t='文字。';p=self.checked(t)
        for row in ([0,0,'identity',0],[0,1,'identity',1],[0,1,'invent',0]):
            q=copy.deepcopy(p);q['segments'][0]['source_map'][0]=row;reseal(q)
            with self.assertRaises(ValueError):validate_projection(t,q)
    def test_arbitrary_character_deletion_rejected(self):
        t='完整文字。';p=self.checked(t);s=p['segments'][0];s['text']=s['text'][1:];s['source_map']=s['source_map'][1:];reseal(p)
        with self.assertRaisesRegex(ValueError,'unapproved_deletion'):validate_projection(t,p)
    def test_barrier_bridge_rejected(self):
        t='叙述。\n*列表。\n后文。';p=self.checked(t);p['segments'][0]['source_spans'][0][1]=len(t);reseal(p)
        with self.assertRaisesRegex(ValueError,'barrier_bridging'):validate_projection(t,p)
    def test_record_role_quarantine(self):
        for frame,metadata in [('news_prose',{'template_names':['Headline item/header']}),('news_prose',{'template_names':['VOA']}),('guide_prose',{'rights_unresolved':True}),('discussion',{'template_names':['Translated']})]:
            self.assertFalse(self.checked('没有可准入叙述。',frame,metadata)['segments'])
    def test_no_truth_promotion(self):
        p=self.checked('正文。','news_prose',{'original':True,'author':'某人'})
        self.assertEqual(p['flags']['human_origin'],'unknown');self.assertEqual(p['flags']['authorship'],'unknown')
    def test_projector_deterministic(self):
        t='甲[[目标|内容]]。\n{{模板}}\n乙。'
        self.assertEqual(project(t,'guide_prose'),project(t,'guide_prose'))
    def test_no_network_or_external_expansion(self):
        p=self.checked('文字{{#invoke:remote}}。\n[https://external.invalid 标签]正文。')
        self.assertEqual(p['segments'][0]['text'],'标签正文。')
    def test_decoded_role_markers_cannot_bypass_barriers(self):
        for t in ('普通&#8220;未决引用&#8221;继续。','联系user&#64;example.com。','&#42; 列表。','&#60;script&#62;未知。'):
            self.assertFalse(self.checked(t)['segments'],t)
    def test_entity_multiline_scope_quarantines_record(self):
        for left,right in (('&#8220;','&#8221;'),('&ldquo;','&rdquo;'),('&#60;blockquote&#62;','&#60;/blockquote&#62;')):
            t='甲。\n'+left+'引用开始。\n这一行仍在引用中。\n引用结束。'+right+'\n乙。\n'
            p=self.checked(t);self.assertFalse(p['segments']);self.assertTrue(p['flags']['record_quarantine_reasons'])
    def test_nested_unclosed_mixed_quote_scopes_quarantine(self):
        for t in ('“外层开始\n“内层。”\n仍在外层。\n外层结束。”','"未闭合引文。\n仍然引用。\n继续引用。','“原始开头\n后续引用。&#8221;','&#8220;开始\n后续引用。”'):
            p=self.checked(t);self.assertFalse(p['segments']);self.assertTrue(p['flags']['record_quarantine_reasons'])
    def test_raw_translation_template_without_metadata_quarantines_record(self):
        p=self.checked('此前正文。\n{{translated|来源}}\n此后正文。','news_prose')
        self.assertFalse(p['segments']);self.assertIn('translation_or_reprint_rights_unresolved',p['flags']['record_quarantine_reasons'])
    def test_empty_input(self):self.assertEqual(self.checked('')['segments'],[])
    def test_no_zero_emission_pure_style_segment(self):self.assertEqual(self.checked("''''\n")['segments'],[])
    def test_exclusion_same_transformation_bounded_full_view(self):
        t='正文[[目标|标签]]。'
        self.assertEqual(project(t,'discussion'),exclusion_project(t))
        large='字'*20001+'。';p=exclusion_project(large);validate_projection(large,p)
        self.assertEqual(p['segments'][0]['text'],large)
        with self.assertRaisesRegex(ValueError,'source_codepoint_cap'):exclusion_project('字'*200001)
    def test_exclusion_never_windows_large_unclosed_construct(self):
        t='{{模板\n'+'未决内容。\n'*5000
        self.assertFalse(exclusion_project(t)['segments'])
    def test_size_cap(self):
        with self.assertRaisesRegex(ValueError,'source_codepoint_cap'):project('字'*20001,'discussion')

if __name__=='__main__':unittest.main()
