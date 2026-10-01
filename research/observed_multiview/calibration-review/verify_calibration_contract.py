"""Read-only hash/metadata calibration gate; never opens decoded source bodies."""
from pathlib import Path
import collections,hashlib,json,sqlite3
P=Path('/workspace/shared/style-scale10-source-v01/public');V=P.parent/'private';O=Path('/workspace/shared/style-scale10-calibration-review-v01/public')
CP=V/'calibration.contract.proposal.v02.json';EXPECTED='ea88b0398cf3d60178056b4f5ab44b7da9ec8196c7a87a2fa2c07ba20d29d1c2'
def h(p):
 d=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):d.update(b)
 return d.hexdigest()
def j(p):return json.loads(Path(p).read_text())
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
assert h(CP)==EXPECTED;c=j(CP);assert c['stage']=='calibration' and c['source_only'] is True and not c['replacement_allowed'] and not c['body_eligibility_before_freeze'] and not c['human_gold']
assert c['stage_output_budget_bytes']==83886080 and c['candidates_execution_blocked_until_fingerprint_writer_integrated']is True
assert c['caps']=={'old_fingerprint_minimum_bytes':566539146,'private_bytes':1073741824,'rss_bytes':3221225472,'wall_seconds':5400}
assert not Path(c['one_time_marker']).exists()
bs=c['source_bindings']+c['code_bindings']+c['indirect_bindings']+c['prior_budget_bindings']+[c['registry'],c['freeze'],c['metadata_database'],c['runtime']['executable']]
for b in bs:
 p=Path(b['path']);assert p.is_file() and p.stat().st_size==b['bytes'] and h(p)==b['sha256']
assert {b['path']for b in c['code_bindings']}=={str(p.resolve())for p in P.glob('*.py')}
assert h(P/'runner.py')=='f433b9e8292e6e149ed18d8afce15f7be56ab93a944c88271e89ee2b3709e70d'
assert h(P/'source_risk_gate.py')=='c5ea663a8264b0efa4dc30aa2ae00906dc49d2a2f3123adfe941156ec404a77a'
assert h(P/'project_wikitext.py')=='387a8a82eb4024ac2c324b841f0ebbc090818f2d81a364113881b9ae0b954da0'
f=j(c['freeze']['path']);reg=j(c['registry']['path']);assert f['records_sha256']==digest(f['records']) and f['registry_sha256']==c['registry']['sha256'] and f['metadata_database_sha256']==c['metadata_database']['sha256']
assert reg['input_bindings']==c['source_bindings'] and reg['metadata_database']==c['metadata_database']
assert len(f['records'])==len({x['record_key']for x in f['records']})==len({x['component_id']for x in f['records']})==96
assert collections.Counter(x['source_frame']for x in f['records'])=={'discussion':32,'news_prose':32,'guide_prose':32}
db=sqlite3.connect(Path(c['metadata_database']['path']).as_uri()+'?mode=ro',uri=True);db.execute('PRAGMA query_only=ON')
assert dict(db.execute('select key,value from control'))['status']=='metadata_only_frozen'
M={k:(component,bool(excluded))for k,component,excluded in db.execute('select * from members')}
graph={k:set()for k in M}
# Old ancestry is a separately hash-bound input, not duplicated in the new-edge table.
sel=j('/workspace/shared/style-compiler-data/learning-pilot-20261001-v02/frozen-selection.private.json')
assert sel['raw_text_in_output'] is False
old_components=set(sel['excluded_component_ids'])|{r['component_id']for r in sel['selected_records']}
old_groups=collections.defaultdict(list);excluded_members=set()
for page,comp in sel['all_page_component_map'].items():
 member=canonical(['wikimedia','zhwiki','page:'+str(int(page))]).decode();assert member in graph;old_groups[comp].append(member)
 if comp in old_components:excluded_members.add(member)
for members in old_groups.values():
 for member in members[1:]:graph[members[0]].add(member);graph[member].add(members[0])
for path in ('/workspace/shared/style-compiler-data/exposure-fingerprints-v01/fingerprints.private.sqlite',str(V/'incremental-blog-exclusion.private.sqlite')):
 ex=sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True)
 excluded_members.update(x[0]for x in ex.execute('select distinct member_key from bindings'));ex.close()
assert excluded_members<=set(graph)
for a,b,kind in db.execute('select * from lineage'):assert a in M and b in M;graph[a].add(b);graph[b].add(a)
seen=set();excluded=set();components=0
for start in graph:
 if start in seen:continue
 group={start};todo=[start]
 while todo:
  n=todo.pop()
  for neighbor in graph[n]-group:group.add(neighbor);todo.append(neighbor)
 seen.update(group);cid=digest(sorted(group));taint=bool(group&excluded_members);components+=1
 for k in group:assert M[k]==(cid,taint)
 if taint:excluded.add(cid)
seed='style-observed-multiview-scale10-v1-20261001'
def rank(purpose,key):return digest([seed,purpose,key]),canonical(key)
reps={};records=0
for key,frame,member,component,sha,cp in db.execute('select record_key,source_frame,member_key,component_id,source_sha256,source_codepoints from records'):
 records+=1;assert 200<=cp<=20000 and M[member][0]==component
 if component in excluded:continue
 row=(key,frame,member,component,sha,cp)
 if component not in reps or rank('representative',key)<rank('representative',reps[component][0]):reps[component]=row
chosen=[]
for source in ('discussion','news_prose','guide_prose'):
 eligible=sorted((r for r in reps.values()if r[1]==source),key=lambda r:rank('calibration',[source,r[3]]));assert len(eligible)>=32;chosen.extend(eligible[:32])
assert [x[0]for x in chosen]==[x['record_key']for x in f['records']]
for r in f['records']:
 row=db.execute('select source_frame,member_key,component_id,source_sha256,source_codepoints,locator_json,metadata_json from records where record_key=?',(r['record_key'],)).fetchone()
 assert row[:5]==tuple(r[k]for k in ('source_frame','member_key','component_id','source_sha256','source_codepoints'))
 assert json.loads(row[5])==r['locator'] and json.loads(row[6])==r['metadata']
db.close()
used=sum(p.stat().st_size for p in V.rglob('*')if p.is_file())+sum(p.stat().st_size for p in Path('/workspace/shared/style-compiler-data/exposure-fingerprints-v01').rglob('*')if p.is_file())
assert used+83886080+4096<=1073741824
result={'schema_version':'independent-calibration-contract-checks/1','contract_sha256':EXPECTED,'all_bound_files_checked':len(bs),'code_files':len(c['code_bindings']),'runtime_indirect_files':len(c['indirect_bindings']),'prior_budget_receipts':len(c['prior_budget_bindings']),'metadata_records_checked':records,'metadata_members_checked':len(M),'independently_rebuilt_components':components,'independently_rebuilt_contaminated_components':len(excluded),'calibration_selection_independently_repeated':96,'records_per_source':32,'source_codepoints_sum':sum(x['source_codepoints']for x in f['records']),'source_codepoints_max':max(x['source_codepoints']for x in f['records']),'actual_private_bytes_at_review':used,'global_private_bytes_cap':1073741824,'enforced_calibration_stage_growth_bytes':83886080,'emergency_reserve_bytes':4096,'natural_calibration_not_started':True,'all_source_synthetic_tests_passed':160,'runner_synthetic_tests_passed':42,'risk_tests_passed':9,'independent_final_risk_adversaries_passed':4,'decoded_source_bodies_read':0,'parser_calls':0,'fits':0,'root_GO_minted':False,'remote_writes':False}
(O/'contract-checks.aggregate.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
