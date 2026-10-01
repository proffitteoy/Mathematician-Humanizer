"""Explicit private train/dev execution wrapper. Verification mode never fits.

No natural fit is authorized by a flag alone: the caller must have current root
GO for this exact implementation and receipts. No test loader/evaluator exists.
"""
from __future__ import annotations
import argparse,dataclasses,hashlib,io,json,pathlib,resource,socket,time
from .contracts import check_known_split_isolation,require
from .fit import FitStopped,decode_record,fit_train_dev

CACHE_RECEIPT_SHA256='b36572cbff861fb84675e50f8dd8dcc4344825205c88ce122fc66accd401a786'
PLAN_SHA256='e72d8ba86171e3ebe06440bd6a5921096b01fabbfa6bff73a3552af57321e750'
EXTRACTION_PLAN_SHA256='32d081061bd905dbcfa1f0d26a9d15aed3d44d1514585e5ef1df80ae292c14cc'
EOF_AMENDMENT_SHA256='93dfa10d803428afebb5a5732eb41ae0d2fd8b31f306059e844728ec66e860b7'

def sha(b):return hashlib.sha256(b).hexdigest()
def data_bytes(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def write_new(path,blob):
 with path.open('xb') as f:f.write(blob)
 require(path.read_bytes()==blob,'output_readback')
 return sha(blob)
def disable_network(*a,**k):raise PermissionError('observed_fit_network_disabled')

class FileControl:
 """A bounded-latency cooperative run/pause/stop flag, never OS PID control."""
 def __init__(self,path,status_path,*,interval=.1):
  self.path=pathlib.Path(path);self.status_path=pathlib.Path(status_path);self.interval=interval;self.last_check=0.0;self.last_status=0.0;self.start=time.monotonic();self.calls=0;self.state=None
  if not self.path.exists():write_new(self.path,data_bytes({'state':'run'}))
 def _status(self,state):
  now=time.monotonic()
  if state!=self.state or now-self.last_status>=5:
   b=data_bytes({'status':state,'elapsed_seconds':round(now-self.start,3),'control_hook_calls':self.calls,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'test_access':False})
   temp=self.status_path.with_suffix('.tmp');temp.write_bytes(b);temp.replace(self.status_path);self.last_status=now;self.state=state
 def __call__(self):
  self.calls+=1;now=time.monotonic()
  if now-self.last_check<self.interval:return
  while True:
   try:
    value=json.loads(self.path.read_text());require(set(value)=={'state'} and value['state'] in {'run','pause','stop'},'control_state')
   except (OSError,ValueError,TypeError):raise FitStopped('external_control_missing_or_invalid') from None
   state=value['state'];self._status(state);self.last_check=time.monotonic()
   if state=='stop':raise FitStopped('external_stop_requested')
   if state=='run':return
   time.sleep(.1)


def read_admitted_records(cache,receipt,repo):
 """Exact receipt/code/data checks only. No transform or prior is fitted here."""
 require(receipt['status']=='pass' and receipt['stage']=='train-dev' and receipt['selected_records']==160 and receipt['test_records_extracted']==0 and receipt['model_fit'] is False,'cache_admission')
 require(all(sha((repo/p).read_bytes())==h for p,h in receipt['module_hashes'].items()),'extraction_code_changed')
 train=[];development=[];names=set()
 for item in receipt['record_receipts']:
  name=item['file'];require(pathlib.Path(name).name==name and name not in names,'cache_file_name');names.add(name)
  raw=(cache/'records'/name).read_bytes();require(sha(raw)==item['sha256'],'cache_record_hash')
  payload=json.loads(raw);record=decode_record(payload['record'])
  require(record.provenance.partition==item['partition'] and record.provenance.partition in {'train','development'},'test_partition_sealed')
  require(record.parser_profile_sha256==receipt['parser_profile_sha256'] and record.measurement_schema_sha256==receipt['measurement_schema_sha256'],'profile_join')
  (train if record.provenance.partition=='train' else development).append(record)
 require(len(train)==128 and len(development)==32,'fixed_partition_sizes')
 check_known_split_isolation(train+development)
 return tuple(train),tuple(development)


def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for x in ['repo','cache','plan','out']:ap.add_argument('--'+x,type=pathlib.Path,required=True)
 mode=ap.add_mutually_exclusive_group(required=True);mode.add_argument('--verify-only',action='store_true');mode.add_argument('--root-fit-go',action='store_true')
 a=ap.parse_args();repo=a.repo.resolve();cache=a.cache.resolve();out=a.out.resolve();require(repo!=out and repo not in out.parents,'private_output_inside_repo');out.mkdir(parents=True,exist_ok=True)
 socket.socket.connect=disable_network;socket.socket.connect_ex=disable_network;socket.getaddrinfo=disable_network
 pb=a.plan.read_bytes();require(sha(pb)==PLAN_SHA256,'plan_hash')
 rb=(cache/'train-dev-receipt.private.json').read_bytes();require(sha(rb)==CACHE_RECEIPT_SHA256,'cache_receipt_hash');receipt=json.loads(rb);plan=json.loads(pb)
 require(receipt['plan_sha256']==EXTRACTION_PLAN_SHA256 and plan['extraction_plan_sha256']==EXTRACTION_PLAN_SHA256 and plan['prefit_eof_amendment_sha256']==EOF_AMENDMENT_SHA256 and receipt['manifest_sha256']==plan['selected_manifest_sha256'],'approved_amendment_plan_cache_join')
 implementation={p.name:sha(p.read_bytes()) for p in sorted((repo/'research/observed_sequence').glob('*.py'))}
 train,development=read_admitted_records(cache,receipt,repo)
 control=FileControl(out/'control.json',out/'live-status.json');control()
 admission={'status':'verified_no_fit' if a.verify_only else 'explicit_root_go_execution','root_fit_go':a.root_fit_go,'implementation_hashes':implementation,'cache_receipt_sha256':sha(rb),'plan_sha256':sha(pb),'extraction_plan_sha256':EXTRACTION_PLAN_SHA256,'prefit_eof_amendment_sha256':EOF_AMENDMENT_SHA256,'manifest_sha256':receipt['manifest_sha256'],'parser_profile_sha256':receipt['parser_profile_sha256'],'measurement_schema_sha256':receipt['measurement_schema_sha256'],'records':{'train':len(train),'development':len(development)},'units':{'train':sum(len(r.units) for r in train),'development':sum(len(r.units) for r in development)},'natural_transforms_fitted':False,'natural_models_fitted':False,'test_records_loaded':0,'source_comparison_flags_promoted':False,'control_file':str(out/'control.json'),'control_states':['run','pause','stop'],'normal_control_poll_seconds':.1,'model_updates_cap':4800,'fit_wall_seconds_cap':3600,'cpu_threads':2,'peak_rss_mib_cap':3072,'new_download_bytes':0}
 name='admission.verify.json' if a.verify_only else 'admission.execute.json';h=write_new(out/name,data_bytes(admission));print(json.dumps({'admission':admission['status'],'admission_sha256':h,'control_file':admission['control_file'],'test_records_loaded':0,'fit_started':False}),flush=True)
 if a.verify_only:return
 try:
  result=fit_train_dev(train,development,root_approved=True,control_hook=control)
  require(implementation=={p.name:sha(p.read_bytes()) for p in sorted((repo/'research/observed_sequence').glob('*.py'))},'implementation_changed_during_fit')
  weights=out/'weights';weights.mkdir(exist_ok=True);artifacts={}
  import torch
  for fitted in result.fits:
   buffer=io.BytesIO();torch.save(fitted.best_state,buffer);blob=buffer.getvalue();require(len(blob)<10000000,'weight_file_budget')
   name=f'{fitted.arm}-{fitted.seed}.pt';artifacts[name]=write_new(weights/name,blob)
  artifacts['transform.private.json']=write_new(out/'transform.private.json',data_bytes(dataclasses.asdict(result.transform)))
  artifacts['prior.private.json']=write_new(out/'prior.private.json',data_bytes(result.prior.tolist()))
  write_new(out/'model-selection-freeze.private.json',data_bytes({'selected_checkpoints':[{'arm':f.arm,'seed':f.seed,'best_epoch':f.best_epoch} for f in result.fits],'frozen_artifact_hashes':artifacts,'plan_sha256':sha(pb),'selection_used_all_target_ce':True,'endpoint_flags_used_for_selection':False,'test_evaluated':False}))
  from .diagnostics import post_selection_diagnostics
  diagnostics=post_selection_diagnostics(result,train,development,control_hook=control)
  write_new(out/'endpoint-diagnostics.aggregate.json',data_bytes(diagnostics))
  report=dict(result.public_report,plan_sha256=sha(pb),cache_receipt_sha256=sha(rb),implementation_hashes=implementation,private_weight_hashes=artifacts)
  require(sum(p.stat().st_size for p in out.rglob('*') if p.is_file())+len(data_bytes(report))<250000000,'fit_output_budget')
  h=write_new(out/'train-dev-fit.aggregate.json',data_bytes(report));control._status('completed')
  print(json.dumps({'status':report['status'],'public_report_sha256':h,'fits':len(result.fits),'optimizer_updates':report['resources']['optimizer_updates'],'test_evaluated':False,'wall_seconds':report['resources']['wall_seconds']}),flush=True)
 except BaseException as error:
  control._status('stopped');write_new(out/'stopped.private.json',data_bytes({'status':'stopped','error_class':type(error).__name__,'reason':str(error) if isinstance(error,FitStopped) else 'execution_error_details_not_public','test_evaluated':False,'completed_results_not_claimed':True}));raise
if __name__=='__main__':main()
