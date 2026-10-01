"""Original no-authority guard test; no corpus, manifest or model is opened."""
import unittest
from research.observed_sequence.sealed_extract import extract_sealed_test
class TestSealedExtractionGuard(unittest.TestCase):
 def test_no_go_rejected_before_any_path_access(self):
  with self.assertRaisesRegex(ValueError,'one_time_root_test_go_required'):
   extract_sealed_test(repo='/does/not/exist',data='/does/not/exist',manifest='/does/not/exist',expected_manifest_sha256='0'*64,model_directory='/does/not/exist',expected_parser_profile_sha256='0'*64,expected_schema_sha256='0'*64,private_out='/does/not/exist',budget=None,control_hook=None)
if __name__=='__main__':unittest.main()
