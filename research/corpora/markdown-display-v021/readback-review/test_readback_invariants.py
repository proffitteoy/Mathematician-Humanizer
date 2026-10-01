"""Synthetic-only preflight for the independent readback checker."""
import copy
import pathlib
import sys
import types
import unittest
import readback_once as r

path=pathlib.Path('/workspace/shared/style-markdown-projection-v02-1/public/continuity_projection.py')
raw_code=path.read_bytes()
assert r.sha(raw_code)==r.PROJECTOR_SHA
p=types.ModuleType('synthetic_continuity');p.__file__=str(path);sys.modules[p.__name__]=p
exec(compile(raw_code,str(path),'exec'),p.__dict__)

class ReadbackCases(unittest.TestCase):
    def value(self,text):return p.project_bytes(text.encode())
    def rehash(self,value):value['projection_sha256']=r.sha(r.canonical({k:v for k,v in value.items() if k!='projection_sha256'}))
    def test_emphasis_and_link_proofs(self):
        text='前**重点**和[标签](url)后';r.independent_check(text.encode(),self.value(text))
    def test_hard_gap_and_unicode(self):
        text='😀**甲**`code`乙e\u0301\r\n丙';r.independent_check(text.encode(),self.value(text))
    def test_empty_source(self):r.independent_check(b'',self.value(''))
    def test_table_scope(self):
        text='|a|b|\n|---|---|\n|x|y|\n\n* note\n\n# Next\n\n正文'
        r.independent_check(text.encode(),self.value(text))
    def test_missing_partition_rejected(self):
        text='正文';v=self.value(text);v['regions']=[];self.rehash(v)
        with self.assertRaises(AssertionError):r.independent_check(text.encode(),v)
    def test_false_character_map_rejected(self):
        text='前**甲**后';v=self.value(text);v['segments'][0]['source_map'][0]=[1,2,'identity',0];self.rehash(v)
        with self.assertRaises(AssertionError):r.independent_check(text.encode(),v)
    def test_proof_gap_rejected(self):
        text='前**甲**后';v=self.value(text);v['syntax_proofs'][0]['source_spans']=[[0,1]];self.rehash(v)
        with self.assertRaises(AssertionError):r.independent_check(text.encode(),v)
    def test_false_boundary_rejected(self):
        text='甲`code`乙';v=self.value(text);v['content_boundaries']=[];self.rehash(v)
        with self.assertRaises(AssertionError):r.independent_check(text.encode(),v)
    def test_duplicate_json_rejected(self):
        with self.assertRaises(ValueError):r.decode('{"x":1,"x":2}')
    def test_nonfinite_json_rejected(self):
        with self.assertRaises(ValueError):r.decode('{"x":NaN}')

if __name__=='__main__':unittest.main(verbosity=2)
