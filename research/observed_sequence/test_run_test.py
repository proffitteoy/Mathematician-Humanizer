"""Original synthetic one-shot wrapper/control checks; no natural files opened."""
import hashlib,json,pathlib,tempfile,unittest
from unittest.mock import patch
from research.observed_sequence.run_test import TestBudget,TestControl,TestRunStopped,verify_extraction_dependencies,configure_cpu_two
class TestEvaluationControl(unittest.TestCase):
 def test_true_test_access_status_only_after_unseal(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);b=TestBudget(p);c=TestControl(p/'control.json',p/'status.json',b);c();self.assertFalse(json.loads((p/'status.json').read_text())['test_access']);c.test_unsealed=True;c._status('authorized');self.assertTrue(json.loads((p/'status.json').read_text())['test_access'])
 def test_existing_stop_is_honored(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);(p/'control.json').write_text('{"state":"stop"}');b=TestBudget(p);c=TestControl(p/'control.json',p/'status.json',b)
   with self.assertRaisesRegex(TestRunStopped,'external_stop'):c()
 def test_stage_budget_resets_once_before_evaluation(self):
  with tempfile.TemporaryDirectory() as d:
   b=TestBudget(pathlib.Path(d));self.assertEqual(b.cap,5400);b.evaluation();self.assertEqual(b.cap,1800);self.assertEqual(b.stage,'evaluation')
class TestCpuConfiguration(unittest.TestCase):
 def test_both_thread_pools_requested_before_work(self):
  with patch('research.observed_sequence.run_test.torch.set_num_threads') as intra,patch('research.observed_sequence.run_test.torch.get_num_threads',return_value=2),patch('research.observed_sequence.run_test.torch.get_num_interop_threads',side_effect=[9,2]),patch('research.observed_sequence.run_test.torch.set_num_interop_threads') as inter:
   configure_cpu_two();intra.assert_called_once_with(2);inter.assert_called_once_with(2)
class TestDependencyBinding(unittest.TestCase):
 def test_original_dependency_tamper_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);(p/'ling.py').write_bytes(b'original');(p/'reader.py').write_bytes(b'archive')
   h=lambda b:hashlib.sha256(b).hexdigest();receipt={'module_hashes':{'ling.py':h(b'original')}};helpers={'reader.py':h(b'archive')}
   self.assertEqual(len(verify_extraction_dependencies(receipt,p,helpers)),2)
   (p/'ling.py').write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'dependency_hash_mismatch'):verify_extraction_dependencies(receipt,p,helpers)
 def test_archive_helper_tamper_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);(p/'ling.py').write_bytes(b'original');(p/'reader.py').write_bytes(b'archive')
   h=lambda b:hashlib.sha256(b).hexdigest();receipt={'module_hashes':{'ling.py':h(b'original')}};helpers={'reader.py':h(b'archive')}
   (p/'reader.py').write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'dependency_hash_mismatch'):verify_extraction_dependencies(receipt,p,helpers)
if __name__=='__main__':unittest.main()
