"""One-shot local authoring ledger, sanitized pass exports, and byte accounting.

No generator calls, network access, source corpus discovery, or model fitting.
Coordinator start_pass must precede exposing a pass's input to its author.
"""
import hashlib,json,os,tempfile,time
from pathlib import Path
CAP=33554432
RAW_CAP=16384

def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def read_json(p):
 def pairs(xs):
  d={}
  for k,v in xs:
   if k in d:raise ValueError('duplicate_json_key')
   d[k]=v
  return d
 def bad(x):raise ValueError('nonfinite_json')
 return json.loads(Path(p).read_bytes(),object_pairs_hook=pairs,parse_constant=bad)
def used_bytes(roots):return sum(p.stat().st_size for root in roots for p in Path(root).rglob('*') if p.is_file())
def put_once(p,data):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
def roots_for(root):return [Path(root).with_name('style-controlled-authoring-v01'),Path(root)]

def export_passes(root):
 """Metadata/prompt preparation only; no generated prose."""
 root=Path(root);jobs=read_json(root/'private/authoring-jobs.json');out=[]
 for pa in (0,1):
  rows=[{'task_id':'J'+sha(('controlled-task-id/v2\0'+j['job_id']).encode())[:24],'prompt_sha256':j['prompt_sha256'],'prompt':j['prompt']} for j in jobs if j['authoring_pass']==pa]
  assert len(rows)==192
  p=root/f'private/author-pass-{pa}/input.json';data=canonical(rows)+b'\n'
  if p.exists():assert p.read_bytes()==data
  else:put_once(p,data)
  allow={'schema':'sanitized-author-input/v2','pass':pa,'input_path':str(p),'input_sha256':sha(data),'read_allowlist':[str(p),str(root/f'private/author-pass-{pa}/ALLOWLIST.json'),str(root/f'private/author-pass-{pa}/STARTED.json'),str(root/'public/authoring_io.py')],'write_root':str(root/f'private/author-pass-{pa}/attempts'),'no_partition_or_family_ids':True,'other_pass_read_authorized':False,'all_natural_or_owner_text_read_authorized':False,'per_task_prose_attempts':1,'job_count':192,'file_system_sandbox_claim':False}
  ap=root/f'private/author-pass-{pa}/ALLOWLIST.json';ad=canonical(allow)+b'\n'
  if ap.exists():assert ap.read_bytes()==ad
  else:put_once(ap,ad)
  out.append(allow)
 return out

def start_pass(root,pa,authorization,author_context_id):
 """Coordinator-only start, before disclosing any prompt. Refuses repeat starts."""
 root=Path(root)
 if pa not in (0,1) or not isinstance(author_context_id,str) or not author_context_id:raise ValueError('pass_context_required')
 contract=root/'public/authoring.contract.json';manifest=root/'public/FILE_HASHES.json'
 if authorization.get('action')!='CONTROLLED_AUTHORING_384_GO' or authorization.get('actor')!='root' or authorization.get('contract_sha256')!=sha(contract.read_bytes()) or authorization.get('manifest_sha256')!=sha(manifest.read_bytes()):raise ValueError('exact_root_GO_required')
 for binding in read_json(manifest)['files']:
  p=root/binding['path']
  if sha(p.read_bytes())!=binding['sha256'] or p.stat().st_size!=binding['bytes']:raise ValueError('frozen_binding_changed')
 rows=read_json(root/f'private/author-pass-{pa}/input.json');allow=read_json(root/f'private/author-pass-{pa}/ALLOWLIST.json')
 if sha((root/f'private/author-pass-{pa}/input.json').read_bytes())!=allow['input_sha256']:raise ValueError('input_hash_changed')
 # Reserve both complete raw envelopes and up to 16 KiB of receipt per task.
 # Both passes reserve their own outstanding slots; no uncharged concurrent run.
 outstanding=0
 for op in (0,1):
  d=root/f'private/author-pass-{op}'
  if (d/'STARTED.json').exists():outstanding+=192-len(list((d/'attempts').glob('*/receipt.json')))
 reserve=(outstanding+192)*32768
 if used_bytes(roots_for(root))+reserve>CAP:raise ValueError('controlled_artifact_cap_before_start')
 marker={'schema':'controlled-pass-start/v2','pass':pa,'author_context_id':author_context_id,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'authorization_sha256':sha(canonical(authorization)),'input_sha256':allow['input_sha256'],'attempt_slots':[{k:r[k] for k in ('task_id','prompt_sha256')} for r in rows],'generation_attempts_reserved':192,'replacement_authorized':False}
 put_once(root/f'private/author-pass-{pa}/STARTED.json',canonical(marker)+b'\n')
 return {'pass':pa,'started_slots':192,'input_sha256':allow['input_sha256'],'author_context_id':author_context_id}

def record_result(root,pa,task_id,raw_envelope,provenance):
 """Pass worker writes a single immutable terminal output; no retry or polishing."""
 root=Path(root);d=root/f'private/author-pass-{pa}'
 if pa not in (0,1) or not isinstance(raw_envelope,bytes):raise ValueError('raw_bytes_and_pass_required')
 marker=read_json(d/'STARTED.json');allow=read_json(d/'ALLOWLIST.json');rows=read_json(d/'input.json')
 if sha((d/'input.json').read_bytes())!=marker['input_sha256'] or marker['input_sha256']!=allow['input_sha256']:raise ValueError('input_hash_changed')
 job=next((r for r in rows if r['task_id']==task_id),None)
 if job is None:raise ValueError('task_not_in_this_pass')
 required={'author_context_id','provider','actual_model_identifier','actual_model_revision','sampling_seed','temperature','available_requested_configuration','started_utc','finished_utc'}
 if len(canonical(provenance))>4096:raise ValueError('provenance_size_limit')
 if set(provenance)!=required or provenance['author_context_id']!=marker['author_context_id'] or provenance['provider']!='OpenAI':raise ValueError('actual_provenance_contract')
 if used_bytes(roots_for(root))+min(len(raw_envelope),RAW_CAP)+16384>CAP:raise ValueError('controlled_artifact_cap')
 out=d/'attempts'/task_id
 out.mkdir(parents=True,exist_ok=False) # any attempted finalization consumes slot
 receipt={'schema':'controlled-authoring-attempt/v2','task_id':task_id,'prompt_sha256':job['prompt_sha256'],'pass':pa,'provenance':provenance,'raw_envelope_sha256':sha(raw_envelope),'raw_envelope_bytes':len(raw_envelope),'status':'failed','failure_reason':None,'parsed_text_sha256':None,'model_admitted':False,'prose_attempts':1}
 if len(raw_envelope)>RAW_CAP:
  # Hash+count the whole returned blob; do not silently truncate into a draft.
  receipt['failure_reason']='raw_envelope_over_cap_not_retained';receipt['raw_envelope_retained']=False
 else:
  put_once(out/'raw.json',raw_envelope);receipt['raw_envelope_retained']=True
  try:
   obj=read_json(out/'raw.json')
   if not isinstance(obj,dict) or set(obj)!={'text','failure_reason'}:raise ValueError('output_schema')
   t=obj['text']
   if t is None:
    if not isinstance(obj['failure_reason'],str) or not obj['failure_reason']:raise ValueError('missing_failure_reason')
    receipt['failure_reason']='author_reported_failure'
   else:
    if not isinstance(t,str) or obj['failure_reason'] is not None:raise ValueError('output_schema')
    receipt['parsed_text_sha256']=sha(t.encode('utf-8'));receipt['raw_codepoints']=len(t)
    if not 120<=len(t)<=400:raise ValueError('text_length_out_of_support')
    receipt['status']='draft_received_pending_blind_review'
  except (ValueError,TypeError,UnicodeError) as e:receipt['failure_reason']=str(e)
 put_once(out/'receipt.json',canonical(receipt)+b'\n')
 return {'task_id':task_id,'status':receipt['status'],'failure_reason':receipt['failure_reason'],'parsed_text_sha256':receipt['parsed_text_sha256']}
