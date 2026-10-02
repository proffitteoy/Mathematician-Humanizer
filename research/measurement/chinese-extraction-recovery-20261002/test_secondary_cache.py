#!/usr/bin/env python3
"""Synthetic files only; no model/corpus access."""
import base64,gzip,hashlib,io,json,lzma,pathlib,random,tarfile,tempfile,unittest
import secondary_cache as sc
from unittest.mock import patch
class BackupChecks(unittest.TestCase):
 def fixture(self,path,count=8):
  root=pathlib.Path(path);c=root/'private/cache';c.mkdir(parents=True)
  lines=[]
  for i in range(count):
   pair=hashlib.sha256(('synthetic-fixture-'+str(i)).encode()).hexdigest();arm='human' if i%2==0 else 'chatgpt';name=pair+'.'+arm+'.json.gz'
   r=random.Random(i)
   raw=sc.js({'synthetic_only':True,'values':[r.random() for _ in range(700)],'common':{'value':None,'missing_reason':'zero_denominator','status':'unavailable','denominator':0,'opportunities':0}})
   b=gzip.compress(raw,compresslevel=6,mtime=0);(c/name).write_bytes(b)
   lines.append(sc.js({'event':'measurement_started','pair_id':pair,'arm':arm,'split':'train'})+b'\n')
   lines.append(sc.js({'event':'cache_committed','pair_id':pair,'arm':arm,'split':'train','cache_file':name,'cache_sha256':sc.sha(b),'bytes':len(b)})+b'\n')
  (root/'private/execution_ledger.jsonl').write_bytes(b''.join(lines));return root
 def test_roundtrip_preserves_original_gzip_and_ledger(self):
  with tempfile.TemporaryDirectory() as td:
   root=self.fixture(pathlib.Path(td)/'source');dest=pathlib.Path(td)/'generation';r=sc.pack(root,dest);self.assertTrue(r['success'])
   restored=pathlib.Path(td)/'restored';v=sc.inspect_restore(r['archive_file'],restored);self.assertEqual(v['committed_cache_count'],8)
   for p in (root/'private/cache').iterdir():self.assertEqual(p.read_bytes(),(restored/'private/cache'/p.name).read_bytes())
   self.assertEqual((root/'private/execution_ledger.jsonl').read_bytes(),(restored/'private/execution_ledger.jsonl').read_bytes())
 def test_different_gzip_header_keeps_json_and_records_new_identity(self):
  with tempfile.TemporaryDirectory() as td:
   root=self.fixture(pathlib.Path(td)/'source');r=sc.pack(root,pathlib.Path(td)/'generation')
   def other_header(raw):
    b=gzip.compress(raw,compresslevel=6,mtime=0);return b[:9]+bytes([255 if b[9]!=255 else 3])+b[10:]
   restored=pathlib.Path(td)/'restored'
   with patch.object(sc,'encode_gzip',other_header):out=sc.inspect_restore(r['archive_file'],restored)
   self.assertEqual(out['gzip_container_hashes_regenerated'],8);self.assertTrue(out['exact_original_json_bytes_verified'])
   for p in (root/'private/cache').iterdir():
    a=p.read_bytes();b=(restored/'private/cache'/p.name).read_bytes();self.assertNotEqual(sc.sha(a),sc.sha(b));self.assertEqual(gzip.decompress(a),gzip.decompress(b))
   receipt=json.loads((restored/'private/secondary_restoration_receipt.json').read_bytes());self.assertEqual(receipt['changed_gzip_containers'],8)
   self.assertEqual((restored/'private/secondary_original_execution_ledger.jsonl').read_bytes(),(root/'private/execution_ledger.jsonl').read_bytes())
   for mapping in receipt['file_mapping'].values():self.assertTrue(mapping['gzip_identity_changed'])
 def test_partial_ledger_tail_excluded(self):
  with tempfile.TemporaryDirectory() as td:
   root=self.fixture(pathlib.Path(td)/'source');p=root/'private/execution_ledger.jsonl';b=p.read_bytes();p.write_bytes(b+b'{"event":"measurement_started"')
   prefix,events=sc.snapshot(p);self.assertEqual(prefix,b);self.assertEqual(len(events),8)
 def test_uncommitted_cache_not_counted(self):
  with tempfile.TemporaryDirectory() as td:
   root=self.fixture(pathlib.Path(td)/'source');(root/'private/cache'/('a'*64+'.human.json.gz')).write_bytes(gzip.compress(b'{"synthetic":true}'))
   r=sc.pack(root,pathlib.Path(td)/'generation');self.assertEqual(r['committed_cache_count'],8)
 def test_budget_failure_preserves_previous_generation_and_sources(self):
  with tempfile.TemporaryDirectory() as td:
   root=self.fixture(pathlib.Path(td)/'source');first=sc.pack(root,pathlib.Path(td)/'first');before=pathlib.Path(first['archive_file']).read_bytes()
   second=sc.pack(root,pathlib.Path(td)/'second',cap=128);self.assertFalse(second['success']);self.assertEqual(pathlib.Path(first['archive_file']).read_bytes(),before);self.assertEqual(len(list((root/'private/cache').iterdir())),8)
 def test_corrupt_cache_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=self.fixture(pathlib.Path(td)/'source');p=next((root/'private/cache').iterdir());p.write_bytes(p.read_bytes()+b'corruption')
   with self.assertRaisesRegex(AssertionError,'cache_sha_mismatch'):sc.pack(root,pathlib.Path(td)/'generation')
 def test_test_split_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=self.fixture(pathlib.Path(td)/'source');p=root/'private/execution_ledger.jsonl';p.write_bytes(p.read_bytes().replace(b'"train"',b'"test"'))
   with self.assertRaisesRegex(AssertionError,'out_of_scope'):sc.pack(root,pathlib.Path(td)/'generation')
 def test_readback_chunks_hash_match(self):
  with tempfile.TemporaryDirectory() as td:
   root=self.fixture(pathlib.Path(td)/'source',16);r=sc.pack(root,pathlib.Path(td)/'generation');index=json.loads(pathlib.Path(r['chunk_index_file']).read_bytes());chunks=pathlib.Path(td)/'readback_chunks'
   for i in range(len(index['chunks'])):sc.write_chunk(chunks,i,sc.read_chunk(r['chunk_index_file'],i))
   out=sc.finish_readback(chunks,r['chunk_index_file'],pathlib.Path(td)/'readback.tar.xz');self.assertTrue(out['tool_store_archive_readback_verified']);self.assertEqual(out['archive_sha256'],r['archive_sha256'])
 def test_corrupted_readback_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=self.fixture(pathlib.Path(td)/'source');r=sc.pack(root,pathlib.Path(td)/'generation');chunks=pathlib.Path(td)/'chunks'
   index=json.loads(pathlib.Path(r['chunk_index_file']).read_bytes())
   for i in range(len(index['chunks'])):sc.write_chunk(chunks,i,sc.read_chunk(r['chunk_index_file'],i))
   (chunks/'00000.bin').write_bytes(b'corrupt')
   with self.assertRaises(AssertionError):sc.finish_readback(chunks,r['chunk_index_file'],pathlib.Path(td)/'readback.tar.xz')
 def test_path_traversal_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   path=pathlib.Path(td)/'malicious.tar.xz'
   with tarfile.open(path,'w:xz') as tf:sc.add(tf,'../outside',b'bad')
   with self.assertRaisesRegex(AssertionError,'unsafe_archive_name'):sc.inspect_restore(path,pathlib.Path(td)/'dest')
if __name__=='__main__':unittest.main(verbosity=2)
