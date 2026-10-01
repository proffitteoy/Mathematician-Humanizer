"""Independent readback of the authorized fixed96 calibration, never new candidates.
Read-only for the frozen source run. Character-only replay, no NLP/model imports.
"""
import collections, gzip, hashlib, html, json, pathlib, sys, importlib.machinery
P=pathlib.Path('/workspace/shared/style-scale10-source-v01/public');V=P.parent/'private'
O=pathlib.Path('/workspace/shared/style-scale10-calibration-results-review-v01')
EXPECTED='ea88b0398cf3d60178056b4f5ab44b7da9ec8196c7a87a2fa2c07ba20d29d1c2'
def h(p):
 d=hashlib.sha256()
 with pathlib.Path(p).open('rb')as f:
  for chunk in iter(lambda:f.read(1048576),b''):d.update(chunk)
 return d.hexdigest()
def j(p):return json.loads(pathlib.Path(p).read_text())
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def lines(p):return [json.loads(x) for x in pathlib.Path(p).read_text().splitlines() if x]
def binding(p):return {'path':str(p),'bytes':p.stat().st_size,'sha256':h(p)}
cp=V/'calibration.contract.proposal.v02.json';assert h(cp)==EXPECTED;c=j(cp)
sealpath=V/'calibration.outputs.sealed.private.json';assert h(sealpath)=='26f40568753bece5e26197fc696c371d728efbea3ed4ce111ab0c296bb371b51';seal=j(sealpath)
assert seal['contract_sha256']==EXPECTED and len(seal['files'])==96
for b in seal['files']:
 assert pathlib.Path(b['path']).stat().st_size==b['bytes'] and h(b['path'])==b['sha256']
rp=V/'calibration.receipt.private.json';r=j(rp)
assert r['status']=='source_projection_complete_pending_independent_review_and_lineage'
assert r['contract_sha256']==EXPECTED and r['source_admission_complete'] is False and r['model_or_POS_or_target_calls']==0 and r['human_gold'] is False
assert 'current_record_at_failure' not in r and 'failure_code' not in r
allbindings=c['source_bindings']+c['code_bindings']+c['indirect_bindings']+c['prior_budget_bindings']+[c['registry'],c['freeze'],c['metadata_database'],c['runtime']['executable']]
for b in allbindings:
 p=pathlib.Path(b['path']);assert p.stat().st_size==b['bytes'] and h(p)==b['sha256'],str(p)
f=j(c['freeze']['path']);expected={x['record_key']:x for x in f['records']};assert len(expected)==96
marker=j(V/'calibration.ONE_TIME_STARTED.json');go=j(V/'calibration.root_GO.private.json')
assert marker['contract_sha256']==EXPECTED and marker['review_sha256']==r['review_sha256'] and marker['root_GO_sha256']==h(V/'calibration.root_GO.private.json')
assert go['action']=='CALIBRATION_GO' and go['actor']=='root' and go['contract_sha256']==EXPECTED and go['review_sha256']==r['review_sha256'] and go['no_other_stages']is True
es=lines(V/'exposure.private.jsonl');es=[x for x in es if x.get('stage')=='calibration']
assert len(es)==96 and {x['record_key']for x in es}==set(expected)
for x in es:
 q=expected[x['record_key']];assert x['contract_sha256']==EXPECTED and x['source_sha256']==q['source_sha256'] and x['member_key']==q['member_key'] and x['known_component_id']==q['component_id'] and x['exclude_entire_final_component']is True and x['body_opened_yet']is False
rs=lines(V/'calibration.source-read.private.jsonl');progress=lines(V/'calibration.progress.private.jsonl')
byevent=collections.defaultdict(list)
for x in rs:byevent[x['event']].append(x)
for event in ['selected_source_view_pre_read','selected_source_view_attempt','selected_source_view_read','source_projection_attempt']:
 rows=byevent[event];assert len(rows)==96 and {x['record_key']for x in rows}==set(expected)
 for x in rows:
  q=expected[x['record_key']];assert x['member_key']==q['member_key'] and x['source_sha256']==q['source_sha256'] and x['source_frame']==q['source_frame']
  if event=='selected_source_view_read':assert x['observed_source_sha256']==q['source_sha256'] and x['source_codepoints']==q['source_codepoints']
assert len(byevent['source_stream_open_intent'])==3
assert len(progress)==96 and {x['record_key']for x in progress}==set(expected)
for key in expected:
 indexes={event:next(i for i,x in enumerate(rs) if x['event']==event and x.get('record_key')==key) for event in ['selected_source_view_pre_read','selected_source_view_attempt','selected_source_view_read','source_projection_attempt']}
 assert indexes['selected_source_view_pre_read']<indexes['selected_source_view_attempt']<indexes['selected_source_view_read']<indexes['source_projection_attempt']
counts=dict(collections.Counter(x['source_frame']for x in expected.values()))
assert counts=={'discussion':32,'news_prose':32,'guide_prose':32}
for k in ['source_attempt_counts','actual_read_counts','projection_attempt_counts','completed_counts','counts']:assert r[k]==counts
# Compile checked source bytes, never load an unbound Python bytecode cache.
importlib.machinery.SourceFileLoader.get_code=lambda self,fullname:compile(self.get_data(self.path),self.path,'exec',dont_inherit=True)
sys.path.insert(0,str(P))
from project_wikitext import project
from source_risk_gate import gated_metadata
from preparse import qualify
from projection_contract import validate_projection
# This repeats the frozen implementation and separately checks every emitted char.
records=[];aggregate={frame:collections.Counter()for frame in counts};role_reasons={frame:collections.Counter()for frame in counts};checks=[]
files=sorted((V/'calibration.records').glob('*.private.json.gz'));assert len(files)==96
for file in files:
 x=json.loads(gzip.decompress(file.read_bytes()));q=x['metadata'];key=q['record_key'];assert expected[key]==q and file.name==digest(key)+'.private.json.gz'
 raw=x['raw_source_text'];assert len(raw)==q['source_codepoints'] and hashlib.sha256(raw.encode()).hexdigest()==q['source_sha256']==x['source_sha256']
 assert next(y for y in progress if y['record_key']==key)['output_sha256']==h(file)
 md,risks=gated_metadata(raw,q['metadata']);assert x['source_risks']==risks
 projection=x['projection'];assert project(raw,q['source_frame'],md)==projection
 assert qualify(projection,key,raw)==x['preparse'];validate_projection(raw,projection)
 charcount=0
 for seg in projection['segments']:
  lo,hi=seg['source_spans'][0];assert not any(b['start']<hi and b['end']>lo for b in projection['barriers'])
  for ch,(a,b,op,n) in zip(seg['text'],seg['source_map']):
   assert lo<=a<b<=hi
   assert (op=='identity' and b==a+1 and n==0 and raw[a:b]==ch) or (op=='entity' and html.unescape(raw[a:b])[n]==ch)
   charcount+=1
 frame=q['source_frame'];a=aggregate[frame];a['fixed_records']+=1;a['raw_codepoints']+=len(raw);a['projected_codepoints']+=charcount;a['segments']+=len(projection['segments']);a['zero_segment_records']+=not bool(projection['segments']);a['record_quarantines']+=bool(projection['flags']['record_quarantine_reasons']);a['risk_gate_records']+=bool(risks);a['preparse_eligible_records']+=x['preparse']['preparse_eligible']
 for b in projection['barriers']:role_reasons[frame].update(b['reasons'])
 checks.append({'output':file.name,'record_key':key,'source_frame':frame,'component_id':q['component_id'],'raw_codepoints':len(raw),'segments':len(projection['segments']),'preparse_eligible':x['preparse']['preparse_eligible'],'selected_segment':x['preparse']['selected_segment']['segment_index']if x['preparse']['selected_segment']else None,'record_quarantine_reasons':projection['flags']['record_quarantine_reasons'],'source_risks':risks,'output_sha256':h(file),'source_map_chars_verified':charcount,'manual_role_review':'pending'})
res=r['resources'];assert res['caps']==c['caps'];assert res['elapsed_seconds']+res['prior_stage_elapsed_seconds']<=5400 and res['peak_rss_bytes']<=3221225472 and res['private_bytes_including_old_fingerprints']<=1073741824
assert r['sandbox']=={'network_disabled':'kernel_seccomp','child_execution_disabled':True,'gpu_disabled':True,'max_numeric_threads':2}
actualbytes=sum(p.stat().st_size for p in V.rglob('*')if p.is_file())+sum(p.stat().st_size for p in pathlib.Path('/workspace/shared/style-compiler-data/exposure-fingerprints-v01').rglob('*')if p.is_file())
assert actualbytes<=1073741824
summary={'schema_version':'independent-fixed96-calibration-readback/1','contract_sha256':EXPECTED,'receipt_sha256':h(rp),'sealed_manifest_sha256':h(sealpath),'unbound_bytecode_cache_used':False,'all_bound_files_verified':len(allbindings),'output_files_verified':96,'exposed_records':96,'read_attempted_records':96,'actually_read_records':96,'projection_attempted_records':96,'completed_records':96,'replacement_records':0,'source_maps_character_checked':True,'frozen_projection_and_preparse_replay_equal':True,'by_source':{k:dict(v)for k,v in aggregate.items()},'barrier_reason_counts':{k:dict(v)for k,v in role_reasons.items()},'resources':res,'actual_private_bytes_at_review':actualbytes,'sandbox':r['sandbox'],'NLP_calls':0,'fit_calls':0,'manual_role_review':'pending','G2_approved':False}
(O/'private/record-checks.private.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
(O/'public/readback.aggregate.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
inputs=[cp,rp,sealpath,V/'calibration.ONE_TIME_STARTED.json',V/'calibration.root_GO.private.json',V/'exposure.private.jsonl',V/'calibration.source-read.private.jsonl',V/'calibration.progress.private.jsonl']+files
(O/'private/review-inputs.private.json').write_text(json.dumps([binding(p)for p in inputs],ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
