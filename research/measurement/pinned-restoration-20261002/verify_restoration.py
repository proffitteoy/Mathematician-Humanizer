from pathlib import Path
import hashlib,json,sys,collections,importlib.metadata as md,subprocess,datetime
R=Path(__file__).resolve().parents[1];B=R.parent;C=B/'m4_chinese_paired_20261002';E=B/'chinese-extraction-recovery-20261002';P=json.loads((E/'public/input_pins.json').read_text())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def blob(p):
 h=hashlib.sha1();h.update(b'blob '+str(p.stat().st_size).encode()+b'\0')
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
plan=read(R/'public/source_plan.json');sources=[]
for f in plan['files']:
 p=R/'repo'/f['path'];assert p.stat().st_size==f['size'] and blob(p)==f['sha'];sources.append({'path':f['path'],'bytes':p.stat().st_size,'git_blob_sha1':f['sha'],'sha256':sha(p)})
for name,x in P['models'].items():
 p=R/'models/zh-hans'/name;assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256']
assert sha(R/'models/resources.json')==P['resources_json_sha256']
raw=[]
for f in read(C/'public/predeclared_protocol.json')['files']:
 p=C/'raw'/f['name'];assert p.stat().st_size==f['bytes'] and blob(p)==f['git_blob_sha1'];raw.append(dict(f,sha256=sha(p)))
metadata={}
for name,key in [('cohort_identity_views.jsonl','cohort_identity_views_sha256'),('components_and_splits.json','components_and_splits_sha256'),('component_edges.jsonl','component_edges_sha256')]:
 h=sha(C/'private'/name);assert h==P[key];metadata[name]={'sha256':h,'matches_original':True}
cohort=[json.loads(x) for x in (C/'private/cohort_identity_views.jsonl').read_text().splitlines()];counts=dict(collections.Counter(r['split'] for r in cohort));assert counts=={'train':1816,'dev':591,'test':593}
assert all(r['fit_eligible_arms']==(['human','chatgpt'] if r['split'] in ('train','dev') else []) for r in cohort)
assert sha(E/'public/extract.py')=='617c3b1ebc88f623e7de9930aad873d00a48a06ee41e4e7c5e9eabd6ffd4aec1'
proto=hashlib.sha256(json.dumps(read(E/'public/extraction_protocol.json'),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest();assert proto=='6e2c5562dfd51b3735486475376662acf09d1fe218a95e5005fb4eeb6ac719a9'
tests=read(E/'public/model_free_receipt.json');assert tests['success'] and tests['tests_run']==164 and tests['failures']==0 and tests['errors']==0
smoke=read(R/'public/parser_smoke_receipt.json');assert smoke['profile_matches_historical']
pre=read(E/'public/predeclaration_receipt.json');assert pre['pilot_plan_sha256']=='2de48ce4ab8e947588ef7b5d0f9c00ac65c4cec6b34dad594e57cdc2b71979ef'
assert read(C/'public/verification_receipt.json')['passed']
assert read(C/'public/freeze_aggregate.json')==read(C/'published_receipts/freeze_aggregate.json')
assert md.version('stanza')=='1.10.1' and md.version('torch')=='2.3.1+cpu' and md.version('numpy')=='1.26.4'
import torch
assert torch.version.cuda is None and not torch.cuda.is_available()
packages={};new_packages=set()
for p in ('stanza_runtime_receipt.json','schema_runtime_receipt.json'):new_packages.update(read(R/'public'/p)['pins'])
new_installed=set()
for d in md.distributions():
 record=d.read_text('RECORD');packages[d.metadata['Name']]={'version':d.version,'RECORD_text_normalized_sha256':hashlib.sha256(record.encode()).hexdigest() if record else None}
 if d.metadata['Name'].lower() in {n.lower() for n in new_packages}:
  new_installed.update(Path(d.locate_file(f)) for f in d.files or [] if Path(d.locate_file(f)).is_file())
check=subprocess.run([sys.executable,'-c',"import stanza,torch,numpy,jsonschema;assert torch.version.cuda is None"],capture_output=True,text=True,check=True)
new_disk=sum(p.stat().st_size for root in (R,C,Path('/tmp/zh-corpus-audit')) for p in root.rglob('*') if p.is_file() and not p.is_symlink())+sum(p.stat().st_size for p in new_installed)
tracked=sum(read(R/'public'/n)['download_bytes'] for n in ('model_download_receipt.json','stanza_runtime_receipt.json','schema_runtime_receipt.json'))+read(C/'private/acquisition_log.json')['actual_payload_bytes']+(R/'models/resources.json').stat().st_size+sum(x['bytes'] for x in sources)+sum(x['size'] for x in read(C/'public/source_plan.json')['files'])
# Reserve 20MiB for small read-only connector responses, repeated source inspection and metadata HTTP responses beyond the byte-ledger counters.
conservative_download=tracked+20*1024**2
assert conservative_download<700*1024**2 and new_disk<2*1024**3
receipt={'status':'READY_FOR_ORIGINAL_4814_TRAIN_DEV_EXTRACTION','completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'paths':{'restoration':str(R),'instrument_repo':str(R/'repo'),'models':str(R/'models'),'python':sys.executable,'cohort':str(C),'exact_wrapper':str(E/'public/extract.py')},'source_revision':plan['revision'],'source_files_checked':len(sources),'source_inventory_note':'Functional pinned Git-blob superset, including all instrument/test dependencies. Lost original48-file manifest inventory is unavailable; identical original inventory is NOT claimed.','source_files':sources,'models':P['models'],'resources_json_sha256':P['resources_json_sha256'],'raw_files':raw,'private_cohort_metadata':metadata,'cohort_counts':counts,'eligible_train_dev_pairs':2407,'eligible_train_dev_arms':4814,'all_frozen_aggregate_fields_match_published':True,'exposure_prefixes':read(C/'public/restored_exposure_receipt.json'),'wrapper_sha256':sha(E/'public/extract.py'),'protocol_sha256':proto,'predeclaration':pre,'model_free_tests':tests,'parser_smoke':smoke,'runtime_packages':packages,'entire_historical_environment_byte_identity':False,'new_download_tracked_bytes':tracked,'new_download_conservative_upper_bound_bytes':conservative_download,'new_disk_bytes':new_disk,'budget':{'download_bytes':700*1024**2,'new_disk_bytes':2*1024**3,'wall_minutes':30},'operations':{'cohort_metadata_only_rebuild':True,'original_scripts_unmodified':True,'full_extraction_started':False,'natural_feature_extraction_started':False,'model_training_started':False,'raw_or_per_sample_uploads':0,'github_writes':0},'boundary':'TEST/davinci bytes were read only by original deterministic cohort metadata rebuild and integrity verifier. No TEST/davinci analysis, parser features, model fitting or tuning; no text was printed or sent to a model.','historical_cache_recovered':0}
(R/'public/RESTORATION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:receipt[k] for k in ('status','source_files_checked','eligible_train_dev_arms','protocol_sha256','new_download_tracked_bytes','new_download_conservative_upper_bound_bytes','new_disk_bytes')},indent=2))
