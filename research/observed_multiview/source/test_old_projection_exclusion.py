import hashlib,json,pathlib,sys,tempfile,unittest,zipfile
from unittest.mock import patch
from old_projection_exclusion import enumerate_old,view_key,rawsha,wiki_member,prepare
from registry import canonical
sys.path.insert(0,'/workspace/shared/style-compiler/research/audits')
import wikiconv_annual_census as reader

class Guard:
    def __init__(self):self.calls=0
    def check(self,*args):self.calls+=1

class EnumerationTests(unittest.TestCase):
    def fixtures(self,path):
        blog=path/'blog.md';blog.write_text('合成博客。',encoding='utf-8')
        xml=path/'article.xml';xml.write_text('<OAI><article><title>合成标题</title><p>合成段落。</p></article></OAI>',encoding='utf-8');raw=xml.read_bytes();lo=raw.index(b'<article>');hi=raw.index(b'</article>')+len(b'</article>')
        def rec(i,text,**extra):return {'id':i,'speaker':None,'conversation_id':'conv','timestamp':1,'text':text,'meta':{'is_section_header':False,**extra}}
        historical=rec('a','合成现有文本。',original=rec('b','合成原始文本。'))
        encoded=canonical(historical)+b'\n'
        oldzip=path/'old.zip'
        with zipfile.ZipFile(oldzip,'w') as z:
            z.writestr('conversations.json',json.dumps({'conv':{'meta':{'page_id':'7'}}}))
            z.writestr('utterances.jsonl',encoded)
        expected=[]
        for i,v in enumerate(reader.views(historical),1):expected.append({'rownum':1,'seq':i,'byte_offset':0,'role':v['role'],'id':v['id'],'conversation':'conv','chars':len(v['text']),'text_sha256':rawsha(v['text'])})
        ep=path/'expected.json';ep.write_text(json.dumps(expected))
        allow={'blogs':[{'path':str(blog),'sha256':hashlib.sha256(blog.read_bytes()).hexdigest(),'bytes':blog.stat().st_size,'original_path':'fixture.md'}],
        'pmc':[{'path':str(xml),'sha256':hashlib.sha256(raw).hexdigest(),'article_range':[lo,hi],'article_sha256':hashlib.sha256(raw[lo:hi]).hexdigest(),'pmcid':'PMCfixture'}],
        'wikiconv2002':{'path':str(oldzip),'sha256':hashlib.sha256(oldzip.read_bytes()).hexdigest(),'bytes':oldzip.stat().st_size},
        'wikiconv2017':{'expected_view_file':str(ep),'expected_view_file_sha256':hashlib.sha256(ep.read_bytes()).hexdigest(),'allowed_top_rows':[1],'path':'synthetic-only','sha256':'a'*64,'bytes':1,'expanded_bytes':len(encoded),'conversation_to_page':{'conv':'7'}}}
        class FakeArchive:
            def __init__(self,*args):self.verified={}
            def chunks(self,name):
                yield encoded
                self.verified[name]=len(encoded)
            def close(self):pass
        return allow,FakeArchive
    def test_all_declared_source_views_exact_roles(self):
        with tempfile.TemporaryDirectory() as d:
            allow,archive=self.fixtures(pathlib.Path(d));guard=Guard()
            with patch.object(reader,'Archive',archive):out=list(enumerate_old(allow,guard))
            self.assertEqual(len(out),9);self.assertEqual([v[3] for v in out],['raw_markdown','raw_OAI_XML','article_itertext_unclassified','JATS_title_text_not_training_prose','JATS_p_text_not_training_prose','top_level','original','top_level','original'])
            self.assertTrue(guard.calls);self.assertEqual(out[-1][2],wiki_member('7'))
    def test_raw_hash_changed_rejects(self):
        with tempfile.TemporaryDirectory() as d:
            allow,archive=self.fixtures(pathlib.Path(d));allow['blogs'][0]['sha256']='b'*64
            with patch.object(reader,'Archive',archive),self.assertRaisesRegex(RuntimeError,'old_blog_changed'):list(enumerate_old(allow,Guard()))
    def test_old_view_metadata_mismatch_rejects(self):
        with tempfile.TemporaryDirectory() as d:
            allow,archive=self.fixtures(pathlib.Path(d));ep=pathlib.Path(allow['wikiconv2017']['expected_view_file']);rows=json.loads(ep.read_text());rows[-1]['text_sha256']='b'*64;ep.write_text(json.dumps(rows));allow['wikiconv2017']['expected_view_file_sha256']=hashlib.sha256(ep.read_bytes()).hexdigest()
            with patch.object(reader,'Archive',archive),self.assertRaisesRegex(RuntimeError,'old_view_identity_changed'):list(enumerate_old(allow,Guard()))
    def test_binding_key_role_member_scope(self):
        base=['WikiConv2017',wiki_member('7'),'original','a'*64,'b'*64,{'row':1}]
        a=view_key(*base)
        for pos,value in ((0,'WikiConv2002'),(1,wiki_member('8')),(2,'top_level'),(3,'c'*64),(4,'d'*64),(5,{'row':2})):
            b=base.copy();b[pos]=value;self.assertNotEqual(a,view_key(*b))
    def test_binding_key_canonical_locator_order(self):
        args=['source',wiki_member('7'),'role','a'*64,'b'*64]
        self.assertEqual(view_key(*args,{'a':1,'b':2}),view_key(*args,{'b':2,'a':1}))
    def test_no_implicit_old_projection_start(self):
        self.assertNotEqual(prepare.__name__,'execute')
        from old_projection_exclusion import execute
        with self.assertRaisesRegex(RuntimeError,'GO_required'):execute('a'*64,False)

if __name__=='__main__':unittest.main()
