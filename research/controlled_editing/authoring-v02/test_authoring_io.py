import hashlib,json,tempfile,unittest
from pathlib import Path
from authoring_io import *
class IOTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'style-controlled-authoring-v02';(self.root/'public').mkdir(parents=True);(self.root/'private').mkdir()
  jobs=[{'job_id':f'fake-{pa}-{i}','authoring_pass':pa,'prompt_sha256':sha(canonical({'instruction':'synthetic-only','content_plan':{}})),'prompt':{'instruction':'synthetic-only','content_plan':{}},'partition':'SECRET_TEST','family_id':'SECRET_FAMILY'} for pa in (0,1) for i in range(192)]
  put_once(self.root/'private/authoring-jobs.json',canonical(jobs));put_once(self.root/'public/authoring.contract.json',b'{"schema":"synthetic-io-test"}')
  export_passes(self.root);self.rows=read_json(self.root/'private/author-pass-0/input.json')
  files=[{'path':str(p.relative_to(self.root)),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in self.root.rglob('*') if p.is_file()]
  put_once(self.root/'public/FILE_HASHES.json',canonical({'files':files}));self.go={'actor':'root','action':'CONTROLLED_AUTHORING_384_GO','contract_sha256':sha((self.root/'public/authoring.contract.json').read_bytes()),'manifest_sha256':sha((self.root/'public/FILE_HASHES.json').read_bytes())}
  self.prov={'author_context_id':'fixture-context','provider':'OpenAI','actual_model_identifier':None,'actual_model_revision':None,'sampling_seed':None,'temperature':None,'available_requested_configuration':{},'started_utc':'fixture','finished_utc':'fixture'}
 def tearDown(self):self.tmp.cleanup()
 def start(self):return start_pass(self.root,0,self.go,'fixture-context')
 def test_sanitized_inputs(self):
  b=(self.root/'private/author-pass-0/input.json').read_bytes();self.assertNotIn(b'SECRET',b);self.assertNotIn(b'partition',b);self.assertNotIn(b'family_id',b);self.assertEqual(len(self.rows),192)
 def test_GO_required(self):
  with self.assertRaisesRegex(ValueError,'GO'):start_pass(self.root,0,{},'fixture-context')
 def test_all_started_before_exposure_and_no_repeat(self):
  self.start();r=read_json(self.root/'private/author-pass-0/STARTED.json');self.assertEqual(len(r['attempt_slots']),192)
  with self.assertRaises(FileExistsError):self.start()
 def test_changed_binding_rejects(self):
  (self.root/'private/authoring-jobs.json').write_text('[]')
  with self.assertRaisesRegex(ValueError,'binding_changed'):self.start()
 def test_fixed_single_terminal_attempt(self):
  self.start();task=self.rows[0]['task_id'];raw=canonical({'text':'甲。'*70,'failure_reason':None});r=record_result(self.root,0,task,raw,self.prov);self.assertEqual(r['status'],'draft_received_pending_blind_review')
  with self.assertRaises(FileExistsError):record_result(self.root,0,task,raw,self.prov)
 def test_unknown_task_not_substituted(self):
  self.start()
  with self.assertRaisesRegex(ValueError,'not_in_this_pass'):record_result(self.root,0,'wrong',b'{}',self.prov)
 def test_wrong_context_rejected(self):
  self.start();p=dict(self.prov,author_context_id='other')
  with self.assertRaisesRegex(ValueError,'provenance'):record_result(self.root,0,self.rows[0]['task_id'],b'{}',p)
 def test_malformed_and_oversize_consumed_as_failures(self):
  self.start()
  for task,raw in [(self.rows[0]['task_id'],b'{bad'),(self.rows[1]['task_id'],b'x'*(RAW_CAP+1))]:self.assertEqual(record_result(self.root,0,task,raw,self.prov)['status'],'failed')
 def test_short_draft_not_admitted(self):
  self.start();r=record_result(self.root,0,self.rows[0]['task_id'],canonical({'text':'甲。','failure_reason':None}),self.prov);self.assertEqual(r['failure_reason'],'text_length_out_of_support')
 def test_no_worker_can_receive_other_pass(self):
  a=read_json(self.root/'private/author-pass-0/ALLOWLIST.json');self.assertFalse(a['other_pass_read_authorized']);self.assertTrue(all('author-pass-1' not in p for p in a['read_allowlist']))
 def test_large_provenance_rejected_before_slot(self):
  self.start();p=dict(self.prov,available_requested_configuration={'x':'x'*4096})
  with self.assertRaisesRegex(ValueError,'size_limit'):record_result(self.root,0,self.rows[0]['task_id'],b'{}',p)
 def test_cumulative_start_reservation_cap(self):
  import authoring_io
  old=authoring_io.CAP;authoring_io.CAP=10000
  try:
   with self.assertRaisesRegex(ValueError,'cap'):self.start()
  finally:authoring_io.CAP=old
if __name__=='__main__':unittest.main()
