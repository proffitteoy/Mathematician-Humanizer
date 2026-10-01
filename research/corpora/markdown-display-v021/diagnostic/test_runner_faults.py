"""Fault tests use only freshly constructed synthetic files in temporary roots."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import diagnostic_runner as r


class SmokeFaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='markdown-smoke-synthetic-',dir='/tmp')
        self.root=Path(self.tmp.name);self.private=self.root/'private';self.private.mkdir()
        self.patches=[patch.object(r,'ROOT',self.root),patch.object(r,'PRIVATE',self.private),patch.object(r,'BUDGET_ROOTS',(self.root,)),patch.object(r,'CAP',131072)]
        for p in self.patches:p.start()
        self.raw=self.root/'synthetic.txt';self.raw.write_bytes(b'Synthetic prose.')
        self.source={'path':str(self.raw),'bytes':self.raw.stat().st_size,'sha256':r.digest(self.raw.read_bytes()),'synthetic':True}
        self.receipt={'read_attempted':0,'read_completed':0,'projection_completed':0}
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def read(self):return r.read_bound_source(self.source,0,self.receipt,time.monotonic(),'synthetic')
    def test_success_has_pre_and_post_events(self):
        self.assertEqual(self.read(),b'Synthetic prose.')
        self.assertEqual(self.receipt['read_attempted'],1);self.assertEqual(self.receipt['read_completed'],1)
        self.assertEqual(self.receipt['projection_completed'],0)
        self.assertTrue((self.private/'pre-read-00.private.json').exists())
        self.assertTrue(json.loads((self.private/'post-read-00.private.json').read_text())['source_verified'])
    def test_open_failure_not_completed_read(self):
        original=Path.open
        def fail(path,*a,**kw):
            if path==self.raw:raise PermissionError('synthetic open failure')
            return original(path,*a,**kw)
        with patch.object(Path,'open',fail),self.assertRaises(PermissionError):self.read()
        self.assertEqual((self.receipt['read_attempted'],self.receipt['read_completed']),(1,0))
        self.assertFalse((self.private/'post-read-00.private.json').exists())
    def test_postread_persistence_failure_counts_exposure(self):
        original=r.save
        def fail(path,*a,**kw):
            if path.name.startswith('post-read-'):raise OSError('synthetic postread persistence failure')
            return original(path,*a,**kw)
        with patch.object(r,'save',fail),self.assertRaises(OSError):self.read()
        self.assertEqual((self.receipt['read_attempted'],self.receipt['read_completed']),(1,1))
        self.assertEqual(self.receipt['projection_completed'],0)
    def test_hash_failure_is_completed_exposure(self):
        self.source['sha256']='0'*64
        with self.assertRaisesRegex(RuntimeError,'diagnostic_source_mismatch'):self.read()
        self.assertEqual(self.receipt['read_completed'],1)
        self.assertFalse(json.loads((self.private/'post-read-00.private.json').read_text())['source_verified'])
    def test_size_failure_prevents_open_attempt(self):
        self.source['bytes']+=1
        with self.assertRaisesRegex(RuntimeError,'source_size_mismatch'):self.read()
        self.assertEqual(self.receipt['read_attempted'],0)
        self.assertIn('current_source',self.receipt)
    def test_preledger_failure_prevents_open_attempt(self):
        with patch.object(r,'save',side_effect=OSError('synthetic preledger failure')),self.assertRaises(OSError):self.read()
        self.assertEqual(self.receipt['read_attempted'],0)
    def test_symlink_rejected(self):
        link=self.root/'alias';link.symlink_to(self.raw);self.source['path']=str(link)
        with self.assertRaisesRegex(RuntimeError,'source_path_alias'):self.read()
    def test_terminal_reserve_usable(self):
        (self.private/'fill').write_bytes(b'x'*70000)
        with self.assertRaisesRegex(RuntimeError,'derivative_byte_cap'):r.save(self.private/'ordinary',{'a':1})
        r.save(self.private/'terminal',{'status':'failed_no_retry'},terminal=True)
        self.assertTrue((self.private/'terminal').exists());self.assertLessEqual(r.total_bytes(),r.CAP)
    def test_terminal_still_capped(self):
        with self.assertRaisesRegex(RuntimeError,'derivative_byte_cap'):r.save_blob(self.private/'too-large',b'x'*r.CAP,terminal=True)
    def test_fsync_failure_is_not_success(self):
        with patch.object(r.os,'fsync',side_effect=OSError('synthetic fsync failure')),self.assertRaises(OSError):r.save_blob(self.private/'projection.gz',b'bytes')
        self.assertTrue((self.private/'projection.gz').exists())
        self.assertEqual(self.receipt['projection_completed'],0)
    def test_exclusive_marker_survives_second_write(self):
        path=self.private/'consumed';r.save(path,{'once':True})
        with self.assertRaises(FileExistsError):r.save(path,{'once':False})
        self.assertTrue(json.loads(path.read_text())['once'])
    def test_nonpython_dependency_hash_checked(self):
        license=self.root/'LICENSE';license.write_text('synthetic notice')
        with self.assertRaisesRegex(RuntimeError,'dependency_file_changed'):
            r.FrozenSourceLoader([{'path':str(license),'sha256':'0'*64,'bytes':license.stat().st_size}])


if __name__=='__main__':unittest.main(verbosity=2)
