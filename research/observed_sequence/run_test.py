"""Explicit one-shot sealed TEST extraction/inference, never training.

Requires current root TEST GO for the exact pre-unseal evaluation plan and code.
No test source, outcome or endpoint is read without that explicit invocation.
"""
from __future__ import annotations
import argparse,dataclasses,hashlib,json,pathlib,resource,socket,time
import torch
from .contracts import require,check_known_split_isolation
from .fit import decode_record
from .prepare import TrainTransform
from .run_fit import FileControl,disable_network
from .sealed_extract import extract_sealed_test
from .evaluation import predict_frozen_test,summarize_predictions
from .diagnostics import endpoint_flags

EVALUATION_PLAN_SHA256='427e39afabbdd21793459a7eb2e1368d480dc1af9a46ed73c7104a3d7dde8cb8'
FIT_REPORT_SHA256='a659b33493de4227dfed7aa92cd44837cd3d10f1a7fc1bfe716bdbc00192398b'
FIT_FREEZE_SHA256='0633ef57ef1228d93ac989c366a39b239315531f64a5c2ed645572a6ec709c21'
MANIFEST_SHA256='ddbe04ae3a3a1d289fbb53e35872b2eb9df27407d92f6002066c992c1580b0b8'
EXTRACTION_RECEIPT_SHA256='b36572cbff861fb84675e50f8dd8dcc4344825205c88ce122fc66accd401a786'

def sha(b):return hashlib.sha256(b).hexdigest()
def encoded(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
class TestRunStopped(RuntimeError):pass

class TestBudget:
 def __init__(self,out):self.out=out;self.start=time.monotonic();self.stage='extraction';self.cap=5400
 def evaluation(self):self.start=time.monotonic();self.stage='evaluation';self.cap=1800
 def check(self):
  if time.monotonic()-self.start>self.cap:raise TestRunStopped(self.stage+'_wall_cap')
  if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>3*1024**2:raise TestRunStopped('test_rss_cap')
  if sum(p.stat().st_size for p in self.out.rglob('*') if p.is_file())>250000000:raise TestRunStopped('test_disk_cap')
 def write(self,path,obj):
  self.check();b=encoded(obj)
  # Keep2KiB for a minimal failure receipt even when the normal output cap trips.
  if sum(p.stat().st_size for p in self.out.rglob('*') if p.is_file())+len(b)>249998000:raise TestRunStopped('test_disk_cap')
  with path.open('xb') as f:f.write(b)
  require(sha(path.read_bytes())==sha(b),'test_output_readback');return sha(b)

class TestControl(FileControl):
 __test__=False
 def __init__(self,path,status_path,budget):self.budget=budget;self.test_unsealed=False;super().__init__(path,status_path)
 def _status(self,state):
  now=time.monotonic()
  if state!=self.state or now-self.last_status>=5:
   b=encoded({'status':state,'stage':self.budget.stage,'stage_elapsed_seconds':round(now-self.budget.start,3),'control_hook_calls':self.calls,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'test_access':self.test_unsealed,'new_fit':False})
   temp=self.status_path.with_suffix('.tmp');temp.write_bytes(b);temp.replace(self.status_path);self.last_status=now;self.state=state
 def __call__(self):
  self.calls+=1;now=time.monotonic()
  if now-self.last_check<self.interval:return
  while True:
   self.budget.check()
   try:
    x=json.loads(self.path.read_text());require(set(x)=={'state'} and x['state'] in {'run','pause','stop'},'test_control_state')
   except (OSError,ValueError,TypeError):raise TestRunStopped('test_control_missing_or_invalid') from None
   state=x['state'];self._status(state);self.last_check=time.monotonic()
   if state=='stop':raise TestRunStopped('test_external_stop')
   if state=='run':return
   time.sleep(.1)


def verified_json(path,expected):
 b=path.read_bytes();require(sha(b)==expected,'frozen_artifact_hash');return json.loads(b)

def verify_extraction_dependencies(receipt,repo,archive_helpers):
 """Implementation identities supplement, not replace, profile/schema hashes."""
 require(bool(receipt['module_hashes']) and bool(archive_helpers),'missing_extraction_dependency_hashes')
 result={**receipt['module_hashes'],**archive_helpers}
 for name,h in result.items():
  path=pathlib.Path(name)
  require(not path.is_absolute() and '..' not in path.parts,'dependency_relative_path')
  require(sha((repo/path).read_bytes())==h,'extraction_dependency_hash_mismatch')
 return result


def load_frozen_artifacts(fit_dir,repo):
 """Only already-fitted artifacts; never estimates parameters or accesses test."""
 report=verified_json(fit_dir/'train-dev-fit.aggregate.json',FIT_REPORT_SHA256)
 freeze=verified_json(fit_dir/'model-selection-freeze.private.json',FIT_FREEZE_SHA256)
 require(report['private_weight_hashes']==freeze['frozen_artifact_hashes'] and len(freeze['selected_checkpoints'])==15,'frozen_checkpoint_set')
 for name,h in report['implementation_hashes'].items():require(sha((repo/'research/observed_sequence'/name).read_bytes())==h,'fitted_implementation_changed')
 for name,h in freeze['frozen_artifact_hashes'].items():
  path=(fit_dir/'weights'/name) if name.endswith('.pt') else fit_dir/name
  require(sha(path.read_bytes())==h,'frozen_weight_or_transform_changed')
 tr=json.loads((fit_dir/'transform.private.json').read_text());require(set(tr)=={f.name for f in dataclasses.fields(TrainTransform)},'frozen_transform_fields')
 transform=TrainTransform(**{k:tuple(v) if isinstance(v,list) else v for k,v in tr.items()})
 prior=torch.tensor(json.loads((fit_dir/'prior.private.json').read_text()),dtype=torch.float64)
 states={(x['arm'],x['seed']):torch.load(fit_dir/'weights'/f"{x['arm']}-{x['seed']}.pt",map_location='cpu',weights_only=True) for x in freeze['selected_checkpoints']}
 return transform,prior,states


def configure_cpu_two():
 """Set both pools before loading models or invoking any parser/inference."""
 torch.set_num_threads(2)
 if torch.get_num_interop_threads()!=2:
  try:torch.set_num_interop_threads(2)
  except RuntimeError:raise RuntimeError('fresh_test_process_with_cpu2_required') from None
 require(torch.get_num_threads()==2 and torch.get_num_interop_threads()==2,'cpu_two_configuration')


def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ['repo','data','manifest','fit-dir','training-cache','evaluation-plan','models','out']:ap.add_argument('--'+name,type=pathlib.Path,required=True)
 ap.add_argument('--root-test-go',action='store_true',required=True);a=ap.parse_args();require(a.root_test_go is True,'one_time_root_TEST_GO_required')
 configure_cpu_two()
 repo=a.repo.resolve();out=a.out.resolve();require(repo!=out and repo not in out.parents,'private_test_output_inside_repo');out.mkdir(parents=True,exist_ok=True)
 require(not (out/'unseal.started.private.json').exists(),'one_shot_test_already_started_no_blind_restart')
 socket.socket.connect=disable_network;socket.socket.connect_ex=disable_network;socket.getaddrinfo=disable_network
 plan=verified_json(a.evaluation_plan,EVALUATION_PLAN_SHA256);require(plan['frozen_selection_manifest_sha256']==MANIFEST_SHA256 and plan['frozen_model_selection_sha256']==FIT_FREEZE_SHA256 and plan['frozen_training_aggregate_sha256']==FIT_REPORT_SHA256,'evaluation_plan_join')
 transform,prior,states=load_frozen_artifacts(a.fit_dir,repo)
 receipt=verified_json(a.training_cache/'train-dev-receipt.private.json',EXTRACTION_RECEIPT_SHA256)
 dependencies=verify_extraction_dependencies(receipt,repo,plan['extraction_dependency_binding']['archive_helpers'])
 budget=TestBudget(out);control=TestControl(out/'control.json',out/'live-status.json',budget);control()
 code={p.name:sha(p.read_bytes()) for p in sorted((repo/'research/observed_sequence').glob('*.py'))}
 admission={'status':'explicit_one_time_root_TEST_GO','evaluation_plan_sha256':EVALUATION_PLAN_SHA256,'model_selection_sha256':FIT_FREEZE_SHA256,'training_report_sha256':FIT_REPORT_SHA256,'manifest_sha256':MANIFEST_SHA256,'code_hashes':code,'cpu_configuration':{'intra_op_threads':torch.get_num_threads(),'inter_op_threads':torch.get_num_interop_threads()},'extraction_dependency_hashes':dependencies,'test_model_or_transform_fit':False,'test_targets_accessed_before_marker':False}
 h=budget.write(out/'unseal.started.private.json',admission);control.test_unsealed=True
 print(json.dumps({'status':'authorized_test_opening','admission_sha256':h,'new_fit':False,'control_file':str(out/'control.json')}),flush=True)
 try:
  records,metadata,extraction=extract_sealed_test(repo=repo,data=a.data,manifest=a.manifest,expected_manifest_sha256=MANIFEST_SHA256,model_directory=a.models,expected_parser_profile_sha256=receipt['parser_profile_sha256'],expected_schema_sha256=receipt['measurement_schema_sha256'],private_out=out,budget=budget,control_hook=control,root_test_go=True)
  train_dev=[]
  for item in receipt['record_receipts']:
   raw=(a.training_cache/'records'/item['file']).read_bytes();require(sha(raw)==item['sha256'],'training_source_reference_changed');train_dev.append(decode_record(json.loads(raw)['record']))
  check_known_split_isolation(tuple(train_dev)+records)
  extract_h=budget.write(out/'test-extraction-receipt.private.json',extraction)
  budget.evaluation();control()
  predictions=predict_frozen_test(records,transform=transform,prior=prior,checkpoints=states,root_approved=True,control_hook=control)
  pred_h=budget.write(out/'all-predictions.private.json',dataclasses.asdict(predictions))
  budget.write(out/'prediction-freeze.private.json',{'all_predictions_sha256':pred_h,'checkpoint_freeze_sha256':FIT_FREEZE_SHA256,'evaluation_plan_sha256':EVALUATION_PLAN_SHA256,'endpoint_flags_computed_before_prediction_freeze':False,'new_fit':False})
  require(predictions.status=='predictions_frozen','test_zero_scoreable_records')
  # Endpoint properties are obtained only after all20series are persisted.
  flags={t.target_id:endpoint_flags(records[r.ordinal],t.target_id[2]) for r in predictions.series[0].records for t in r.targets}
  summary=summarize_predictions(predictions,endpoint_flags=flags,speaker_keys={i:m['speaker_key'] for i,m in enumerate(metadata)},page_types={i:m['page_type'] for i,m in enumerate(metadata)},control_hook=control)
  budget.write(out/'paired-record-and-bootstrap.private.json',summary.private_details)
  require(code=={p.name:sha(p.read_bytes()) for p in sorted((repo/'research/observed_sequence').glob('*.py'))},'test_implementation_changed_during_execution')
  require(dependencies==verify_extraction_dependencies(receipt,repo,plan['extraction_dependency_binding']['archive_helpers']),'extraction_dependencies_changed_during_test')
  report=dict(summary.public_report,extraction_dependency_hashes=dependencies,evaluation_plan_sha256=EVALUATION_PLAN_SHA256,checkpoint_freeze_sha256=FIT_FREEZE_SHA256,training_report_sha256=FIT_REPORT_SHA256,test_extraction_receipt_sha256=extract_h,private_predictions_sha256=pred_h,implementation_hashes=code,new_fit=False,comparison_eligible_promoted=False,author_or_human_truth_admission=False)
  h=budget.write(out/'test-evaluation.aggregate.json',report);control._status('completed')
  print(json.dumps({'status':'test_evaluation_completed','public_report_sha256':h,'prediction_freeze_sha256':pred_h,'new_fit':False}),flush=True)
 except BaseException as error:
  control._status('stopped')
  failure=encoded({'status':'stopped','stage':budget.stage,'error_class':type(error).__name__,'reason':str(error) if isinstance(error,TestRunStopped) else 'validation_or_execution_error_no_automatic_retry','new_fit':False,'test_has_been_opened':True})
  # Failure logging does not re-enter an already-exceeded time/RSS check.
  if sum(p.stat().st_size for p in out.rglob('*') if p.is_file())+len(failure)<=250000000:
   with (out/'test-stopped.private.json').open('xb') as stream:stream.write(failure)
  raise
if __name__=='__main__':main()
