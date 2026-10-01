"""Source-free gate/binding tests; fixtures are synthetic temporary files."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import diagnostic_runner as r


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='v021-gate-synthetic-',dir='/tmp')
        self.path=Path(self.tmp.name)/'go.json'
        self.manifest={'contract':{'sha256':'c'*64}}
        self.go={'schema_version':'markdown-v021-diagnostic-root-go/1','actor':'root',
             'action':'EXECUTE_V021_THREE_EXPOSED_DIAGNOSTICS_ONCE','manifest_sha256':'m'*64,
             'contract_sha256':'c'*64,'projector_sha256':r.PROJECTOR_SHA,
             'no_new_candidate_reads':True,'no_other_stages':True}
    def tearDown(self):self.tmp.cleanup()
    def verify(self):
        raw=r.canonical(self.go);self.path.write_bytes(raw)
        return r.verify_go(self.manifest,'m'*64,self.path,r.digest(raw))
    def test_exact_go(self):self.assertEqual(self.verify(),self.go)
    def test_no_go(self):
        with self.assertRaises(FileNotFoundError):r.verify_go(self.manifest,'m'*64,self.path,'0'*64)
    def test_wrong_manifest(self):
        self.go['manifest_sha256']='other'
        with self.assertRaisesRegex(RuntimeError,'root_go_binding_mismatch'):self.verify()
    def test_wrong_profile(self):
        self.go['projector_sha256']='0'*64
        with self.assertRaisesRegex(RuntimeError,'root_go_binding_mismatch'):self.verify()
    def test_wrong_contract(self):
        self.go['contract_sha256']='0'*64
        with self.assertRaisesRegex(RuntimeError,'root_go_binding_mismatch'):self.verify()
    def test_extra_stage(self):
        self.go['no_other_stages']=False
        with self.assertRaisesRegex(RuntimeError,'root_go_binding_mismatch'):self.verify()
    def test_extra_go_field(self):
        self.go['new_candidates']=785
        with self.assertRaisesRegex(RuntimeError,'root_go_binding_mismatch'):self.verify()
    def test_nonboolean_authorization(self):
        self.go['no_other_stages']=1
        with self.assertRaisesRegex(RuntimeError,'root_go_binding_mismatch'):self.verify()
    def test_wrong_go_digest(self):
        self.path.write_bytes(r.canonical(self.go))
        with self.assertRaisesRegex(RuntimeError,'root_go_digest_mismatch'):r.verify_go(self.manifest,'m'*64,self.path,'0'*64)
    def test_budget_roots_include_audit(self):
        self.assertIn(r.AUDIT_ROOT,r.BUDGET_ROOTS)
        self.assertIn(r.PROJECTOR_ROOT,r.BUDGET_ROOTS)
        self.assertEqual(r.EXECUTION_SECONDS+r.READBACK_SECONDS,60)
        self.assertEqual(r.TERMINAL_RESERVE,65536)
    def test_prior_markers_distinct(self):
        self.assertIn('v02-1-diagnostic-v01',str(r.MARKER))
        self.assertNotEqual(r.MARKER,Path('/workspace/shared/style-markdown-projection-v01/private/diagnostic-smoke.ONE_TIME_STARTED.private.json'))
    def test_accounting_charges_all_roots(self):
        a=Path(self.tmp.name)/'a';b=Path(self.tmp.name)/'b';a.mkdir();b.mkdir()
        (a/'file').write_bytes(b'123');(b/'file').write_bytes(b'4567')
        with patch.object(r,'BUDGET_ROOTS',(a,b)):self.assertEqual(r.total_bytes(),7)

if __name__=='__main__':unittest.main(verbosity=2)
