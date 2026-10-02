"""Original, deterministic M4 Chinese preparation. No ML fit or remote writes.
Private outputs contain identities and per-record measurements: never publish them.
"""
import collections,hashlib,json,math,pathlib,re,resource,time,unicodedata,sys
D=pathlib.Path(__file__).resolve().parents[1];PUB=D/'public';PRIV=D/'private'
P=json.loads((PUB/'predeclared_protocol.json').read_text()); START=time.monotonic();CPU=time.process_time()
resource.setrlimit(resource.RLIMIT_AS,(P['limits']['max_address_space_bytes'],)*2)
resource.setrlimit(resource.RLIMIT_CPU,(780,780))
# One process and no BLAS/parallel dependencies. Fail closed before freeze.
def write(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2))
def digest(x): return hashlib.sha256(x.encode('utf-8')).hexdigest()
def familykey(r):return json.dumps([r['source'],type(r['source_ID']).__name__,r['source_ID']],ensure_ascii=False,separators=(',',':'))
def pairkey(r):return digest(json.dumps([familykey(r),r['prompt'],r['human_text']],ensure_ascii=False,separators=(',',':')))
def norm(s): return ''.join(unicodedata.normalize('NFKC',s).casefold().split())
def line_spans(t):
 start=0; out=[]
 for m in re.finditer(r'\r\n|\r|\n',t):out.append((start,m.start()));start=m.end()
 out.append((start,len(t)));return out
def block_spans(t):
 out=[];start=None;end=None
 for a,b in line_spans(t):
  if t[a:b].strip():
   if start is None:start=a
   end=b
  elif start is not None:out.append((start,end));start=None
 if start is not None:out.append((start,end))
 return out
def sentence_spans(t):
 out=[];start=0;i=0
 while i<len(t):
  c=t[i];ending=c in '。！？!?' or c=='.' and not(i>0 and i+1<len(t) and t[i-1].isdigit() and t[i+1].isdigit())
  if ending:
   end=i+1
   while end<len(t) and t[end] in '。！？!?':end+=1
   if any(ch.isalnum() for ch in t[start:end]):out.append((start,end))
   start=end;i=end
  else:i+=1
 if any(ch.isalnum() for ch in t[start:]):out.append((start,len(t)))
 return out
def support(t):
 if t is None:return {'status':'null','lexical':False,'sentence':False,'ordered_prose':False,'multiline':False,'paragraph':False,'chars':None,'sentences':None,'nonempty_lines':None,'blocks':None}
 if not isinstance(t,str):return {'status':'non_string','lexical':False,'sentence':False,'ordered_prose':False,'multiline':False,'paragraph':False,'chars':None,'sentences':None,'nonempty_lines':None,'blocks':None}
 lines=line_spans(t);blocks=block_spans(t);sentences=sentence_spans(t);nonempty=sum(bool(t[a:b].strip()) for a,b in lines)
 return {'status':'empty' if not t else 'whitespace_only' if not t.strip() else 'present','lexical':bool(t.strip()),'sentence':bool(sentences),'ordered_prose':len(sentences)>=2,'multiline':nonempty>=2,'paragraph':len(blocks)>=2,'chars':len(t),'sentences':len(sentences),'nonempty_lines':nonempty,'blocks':len(blocks),'CR':t.count('\r'),'LF':t.count('\n'),'CRLF':t.count('\r\n'),'literal_backslash_n':t.count('\\n'),'sentence_spans':sentences,'block_spans':blocks}
files={};file_audit={};required={'prompt','human_text','machine_text','model','source','source_ID'}
for f in P['files']:
 raw=(D/'raw'/f['name']).read_bytes()
 assert len(raw)==f['bytes'] and hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==f['git_blob_sha1']
 rows=[];offset=0;fields=collections.Counter()
 for k,line in enumerate(raw.splitlines(keepends=True),1):
  row=json.loads(line.decode('utf-8'));assert required<=row.keys(),('schema',f['name'],k)
  fields.update(row.keys());rows.append((row,offset,len(line),k));offset+=len(line)
 ids=[familykey(r) for r,*_ in rows]
 assert all(type(r['source_ID']) in (str,int) and r['source_ID']!='' for r,*_ in rows), 'Missing/invalid ID'
 duplicate_ids=len(ids)-len(set(ids))
 assert len({pairkey(r) for r,*_ in rows})==len(rows),'Ambiguous duplicate composite identity' 
 file_audit[f['name']]={'rows':len(rows),'distinct_ids':len(set(ids)),'duplicate_id_occurrences_beyond_first':duplicate_ids,'id_types':dict(collections.Counter(type(r['source_ID']).__name__ for r,*_ in rows)),'field_counts':dict(fields),'sources':dict(collections.Counter(r['source'] for r,*_ in rows)),'model_labels':dict(collections.Counter(r['model'] for r,*_ in rows)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'git_blob_sha1':f['git_blob_sha1'],'file_CR':raw.count(b'\r'),'file_LF':raw.count(b'\n'),'file_CRLF':raw.count(b'\r\n')}
 files[f['name']]={pairkey(r):(r,off,size,line) for r,off,size,line in rows}
left=files['qazh_chatgpt.jsonl'];right=files['qazh_davinci.jsonl'];ids=sorted(set(left)|set(right))
shared=set(left)&set(right);only_left=set(left)-set(right);only_right=set(right)-set(left)
checks={field:sum(left[x][0][field]==right[x][0][field] for x in shared) for field in ['prompt','human_text','source']}
write(PUB/'schema_initial.json',{'files':file_audit,'shared_composite_answer_ids':len(shared),'only_chatgpt_composites':len(only_left),'only_davinci_composites':len(only_right),'exact_equal_fields':checks})
assert not only_left and not only_right,'Unequal family ID sets: investigate before freeze'
assert all(x==len(shared) for x in checks.values()),'Unequal shared prompt/human/source: investigate before freeze'
assert set(file_audit['qazh_chatgpt.jsonl']['model_labels'])=={'chatgpt'}
assert set(file_audit['qazh_davinci.jsonl']['model_labels'])=={'davinci'}
old_manifest=json.loads(pathlib.Path('/tmp/zh-corpus-audit/combined_manifest.json').read_text())
exposed=set();old_checks=[]
for model in ['chatgpt','davinci']:
 entry=next(x for x in old_manifest['entries'] if x['name']=='m4_qazh_'+model+'.jsonl')
 old=pathlib.Path('/tmp/zh-corpus-audit/raw',entry['name']).read_bytes();new=(D/'raw'/('qazh_'+model+'.jsonl')).read_bytes()
 assert hashlib.sha256(old).hexdigest()==entry['sha256'] and new.startswith(old)
 old_ids={pairkey(json.loads(x)) for x in old.splitlines()};assert len(old_ids)==128
 exposed.update(old_ids);old_checks.append({'file':entry['name'],'rows':128,'hash_verified':True,'exact_full_file_prefix_verified':True})
idx={x:i for i,x in enumerate(ids)}; n=len(ids);parent=list(range(n));weight=[1]*n
edges=collections.Counter();distinct_cross_edges=set();edgepath=PRIV/'component_edges.jsonl';edgeout=edgepath.open('w')
def root(i):
 while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
 return i
def link(a,b,reason,detail=None):
 edges[reason]+=1
 if a==b:return
 distinct_cross_edges.add((min(a,b),max(a,b)))
 ra,rb=root(a),root(b)
 if ra!=rb:
  if weight[ra]<weight[rb]:ra,rb=rb,ra
  parent[rb]=ra;weight[ra]+=weight[rb]
 edgeout.write(json.dumps({'a':ids[a],'b':ids[b],'reason':reason,'detail':detail},ensure_ascii=False)+'\n')
questions=[];answers=[];family_records=[];firstq={};firsta={};firstblock={};firstfamily={};norm_exact_groups=collections.defaultdict(list)
for identity in ids:
 i=idx[identity];a,ao,asz,aline=left[identity];b,bo,bsz,bline=right[identity]
 family=familykey(a)
 if family in firstfamily:link(i,firstfamily[family],'same_source_question_id')
 else:firstfamily[family]=i
 texts={'human':a['human_text'],'chatgpt':a['machine_text'],'davinci':b['machine_text']}
 q=norm(a['prompt']) if isinstance(a['prompt'],str) else ''
 if q:
  if q in firstq:link(i,firstq[q],'exact_question')
  else:firstq[q]=i
  questions.append((i,'question',q))
 rec={'pair_id':identity,'source_ID':a['source_ID'],'question_family_id':familykey(a),'source':a['source'],'author':None,'publication_date':None,'generation_date':None,'authorship_status':'original_benchmark_label_not_independently_verified','previously_audited':identity in exposed,'prompt_sha256':digest(a['prompt']) if isinstance(a['prompt'],str) else None,'human_stored_once_logically':True,'raw_rows':{'chatgpt':{'file':'qazh_chatgpt.jsonl','offset_bytes':ao,'length_bytes':asz,'line':aline},'davinci':{'file':'qazh_davinci.jsonl','offset_bytes':bo,'length_bytes':bsz,'line':bline}},'arms':{}}
 for arm,t in texts.items():
  s=support(t);rec['arms'][arm]=dict(s,original_text_sha256=digest(t) if isinstance(t,str) else None)
  if not isinstance(t,str) or not t.strip():continue
  z=norm(t);answers.append((i,arm,z));norm_exact_groups[z].append((i,arm))
  if z in firsta:link(i,firsta[z],'exact_answer')
  else:firsta[z]=i
  for st,en in block_spans(t):
   block=norm(t[st:en])
   if len(block)>=80:
    if block in firstblock:link(i,firstblock[block],'exact_blank_line_block')
    else:firstblock[block]=i
 family_records.append(rec)
print('SCHEMA',len(ids),'paired answer records; original exposed',len(exposed),'; beginning exact near-copy joins',flush=True)
# Prefix-filter join: for J>=4/5, each sorted set's prefix has n-ceil(4n/5)+1 grams.
# Any qualifying pair shares a prefix gram under the same total gram ordering.
# All earlier sets have size <= current; reject prior lengths <ceil(4n/5).
def join(docs,k,minchars,reason):
 unique=[];seen={}
 for fam,arm,t in docs:
  if len(t)<minchars:continue
  if t in seen:continue # exact answer/question edges already connect all repeated texts
  seen[t]=len(unique);unique.append((fam,arm,t))
 gramsets=[];freq=collections.Counter()
 for _,_,t in unique:
  grams={int.from_bytes(hashlib.blake2b(t[j:j+k].encode(),digest_size=8).digest(),'big') for j in range(len(t)-k+1)}
  gramsets.append(grams);freq.update(grams)
 order=sorted(range(len(unique)),key=lambda j:(len(gramsets[j]),digest(unique[j][2])))
 inverted=collections.defaultdict(list);candidates=verified=positives=0;maximum_bucket=0
 for j in order:
  x=gramsets[j];nx=len(x);prefix_len=nx-math.ceil(4*nx/5)+1
  prefix=sorted(x,key=lambda g:(freq[g],g))[:prefix_len];cand=set();minimum=math.ceil(4*nx/5)
  for g in prefix:
   for prior in inverted[g]:
    if len(gramsets[prior])>=minimum:cand.add(prior)
  candidates+=len(cand)
  for prior in cand:
   y=gramsets[prior];inter=len(x&y)
   if 5*inter<4*(len(x)+len(y)-inter):continue
   verified+=1; sx={unique[j][2][z:z+k] for z in range(len(unique[j][2])-k+1)};sy={unique[prior][2][z:z+k] for z in range(len(unique[prior][2])-k+1)}
   realinter=len(sx&sy)
   if 5*realinter>=4*(len(sx)+len(sy)-realinter):
    positives+=1;link(unique[j][0],unique[prior][0],reason,{'arm_a':unique[j][1],'arm_b':unique[prior][1],'jaccard':realinter/(len(sx)+len(sy)-realinter)})
  for g in prefix:inverted[g].append(j);maximum_bucket=max(maximum_bucket,len(inverted[g]))
  if time.process_time()-CPU>700:raise RuntimeError('Compute guard: do not freeze incomplete grouping')
 return {'documents_eligible':sum(len(t)>=minchars for _,_,t in docs),'distinct_texts_joined':len(unique),'gram_n':k,'threshold':0.8,'candidate_pairs_exactly_checked':candidates,'hash_positive_pairs_reverified_on_original_grams':verified,'near_pairs':positives,'max_prefix_bucket':maximum_bucket,'all_candidates_completed':True}
nearq=join(questions,3,12,'near_question');print('QUESTION JOIN',nearq,flush=True)
# Remove transient exact maps before the heavier answer join; their union effects and edges are retained.
firstq.clear();firsta.clear();firstblock.clear()
neara=join(answers,5,50,'near_answer');print('ANSWER JOIN',neara,flush=True)
edgeout.close();components=collections.defaultdict(list)
for i in range(n):components[root(i)].append(i)
comps=[]
for members in components.values():
 cid=digest('\n'.join(ids[i] for i in members));maxchar=max((family_records[i]['arms']['human']['chars'] or 0) for i in members);length_stratum='lt200' if maxchar<200 else '200_499' if maxchar<500 else 'ge500';source_profile='+'.join(sorted({family_records[i]['source'] for i in members}));stratum=source_profile+'|'+length_stratum
 comps.append({'component_id':cid,'members':[ids[i] for i in members],'stratum':stratum,'question_families':sorted({family_records[i]['question_family_id'] for i in members}),'source_profile':source_profile,'exposed':any(ids[i] in exposed for i in members),'order_hash':digest(P['split_seed']+'|'+cid)})
# Verify support before allocation. Keep all valid families; structural rows remain flagged.
arms=['human','chatgpt','davinci'];views=['lexical','sentence','ordered_prose','multiline','paragraph']
def aggregate(records):
 out={'paired_answer_records':len(records),'question_families':len({r['question_family_id'] for r in records}),'arms':{},'paired_support':{}}
 for arm in arms:
  vals=[r['arms'][arm] for r in records];chars=sorted(x['chars'] for x in vals if x['chars'] is not None)
  median=(chars[(len(chars)-1)//2]+chars[len(chars)//2])/2 if chars else None
  out['arms'][arm]={'count':len(vals),'status':dict(collections.Counter(x['status'] for x in vals)),'view_support':{v:sum(x[v] for x in vals) for v in views},'chars_min':min(chars) if chars else None,'chars_median':median,'chars_max':max(chars) if chars else None,'chars_ge500':sum(x>=500 for x in chars),'literal_backslash_n_texts':sum(bool(x.get('literal_backslash_n')) for x in vals),'with_CR':sum(bool(x.get('CR')) for x in vals),'with_LF':sum(bool(x.get('LF')) for x in vals),'with_CRLF':sum(bool(x.get('CRLF')) for x in vals)}
 for aa in [('human','chatgpt'),('human','davinci'),tuple(arms)]:out['paired_support']['+'.join(aa)]={v:sum(all(r['arms'][a][v] for a in aa) for r in records) for v in views}
 families=collections.defaultdict(list)
 for r in records:families[r['question_family_id']].append(r)
 out['equal_question_family_support']={}
 for aa in [('human',),('chatgpt',),('davinci',),('human','chatgpt'),('human','davinci'),tuple(arms)]:
  vv={}
  for v in views:
   fractions=[sum(all(r['arms'][a][v] for a in aa) for r in rr)/len(rr) for rr in families.values()]
   vv[v]={'question_families_any_answer_supported':sum(x>0 for x in fractions),'question_families_all_answers_supported':sum(x==1 for x in fractions),'equal_question_mean_fraction_of_supported_answers':sum(fractions)/len(fractions) if fractions else None}
  out['equal_question_family_support']['+'.join(aa)]=vv
 return out
full_support=aggregate(family_records);write(PUB/'support_before_split.json',full_support)
assert all(full_support['paired_support'][key]['lexical']>0 for key in ['human+chatgpt','human+davinci'])
alloc=[]
for stratum in sorted({c['stratum'] for c in comps}):
 cc=sorted([c for c in comps if c['stratum']==stratum],key=lambda c:c['order_hash']);target_test=int(len(cc)*.2+.5);target_dev=int(len(cc)*.2+.5);eligible=[c for c in cc if not c['exposed']];testids={c['component_id'] for c in eligible[:target_test]};remaining=[c for c in cc if c['component_id'] not in testids];devids={c['component_id'] for c in remaining[:target_dev]}
 for c in cc:c['split']='test' if c['component_id'] in testids else 'dev' if c['component_id'] in devids else 'train';c['test_panel']=None
 for j,c in enumerate(c for c in cc if c['split']=='test'):c['test_panel']='seen_generator' if j%2==0 else 'generator_transfer'
 alloc.append({'stratum':stratum,'total_components':len(cc),'test_target':target_test,'dev_target':target_dev,'train_target':len(cc)-target_test-target_dev,'test_eligible':len(eligible),'actual_component_counts':dict(collections.Counter(c['split'] for c in cc))})
byid={identity:c for c in comps for identity in c['members']}
for r in family_records:
 c=byid[r['pair_id']];r.update(component_id=c['component_id'],split=c['split'],test_panel=c['test_panel'],component_development_exposed=c['exposed']);assert not(c['exposed'] and c['split']=='test')
question_counts=collections.Counter(r['question_family_id'] for r in family_records)
for r in family_records:
 r['question_family_answer_count']=question_counts[r['question_family_id']]
 r['equal_question_family_answer_weight']=1/question_counts[r['question_family_id']]
 r['inference_cluster']=r['component_id']
 r['fit_eligible_arms']=['human','chatgpt'] if r['split'] in ('train','dev') else []
 r['davinci_role']='generator_held_out_from_fitting_and_tuning'
with (PRIV/'cohort_identity_views.jsonl').open('w') as out:
 for r in family_records:out.write(json.dumps(r,ensure_ascii=False)+'\n')
write(PRIV/'components_and_splits.json',comps)
# Prove no recorded cross-family graph edge spans a split; count once without raw examples.
assert all(byid[ids[a]]['component_id']==byid[ids[b]]['component_id'] for a,b in distinct_cross_edges)
by_split={sp:aggregate([r for r in family_records if r['split']==sp]) for sp in ['train','dev','test']}
by_panel={sp:aggregate([r for r in family_records if r['test_panel']==sp]) for sp in ['seen_generator','generator_transfer']}
exposed_comps=[c for c in comps if c['exposed']];size_distribution=dict(sorted(collections.Counter(len(c['members']) for c in comps).items()))
copy_groups=[g for g in norm_exact_groups.values() if len(g)>1]
counts={'files':file_audit,'alignment':{'shared_paired_answer_records':n,'distinct_question_families':len(firstfamily),'question_ids_with_multiple_human_answers':sum(v>1 for v in collections.Counter(r['question_family_id'] for r in family_records).values()),'id_sets_equal':True,'prompt_exact_equal':checks['prompt'],'human_exact_equal':checks['human_text'],'source_exact_equal':checks['source'],'logical_human_observations':n,'total_logical_answers':3*n,'original_human_stored_occurrences':2*n},'prior_audit':{'verified_files':old_checks,'unique_previously_audited_families':len(exposed),'exposed_components':len(exposed_comps),'paired_answer_records_in_exposed_components':sum(len(c['members']) for c in exposed_comps),'question_families_in_exposed_components':sum(len(c['question_families']) for c in exposed_comps),'additional_connected_question_families_blocked_from_test':sum(len(c['question_families']) for c in exposed_comps)-len(exposed),'test_exposed_components':0},'copy_graph':{'edges_by_reason':dict(edges),'distinct_cross_record_pairs_linked':len(distinct_cross_edges),'components':len(comps),'component_paired_record_size_distribution':size_distribution,'component_question_family_size_distribution':dict(sorted(collections.Counter(len(c['question_families']) for c in comps).items())),'largest_component_paired_records':max(len(c['members']) for c in comps),'largest_component_question_families':max(len(c['question_families']) for c in comps),'near_question':nearq,'near_answer':neara,'exact_answer_duplicate_groups':len(copy_groups),'exact_answer_duplicate_occurrences_beyond_first':sum(len(g)-1 for g in copy_groups),'cross_arm_exact_duplicate_groups':sum(len({a for _,a in g})>1 for g in copy_groups),'cross_family_exact_duplicate_groups':sum(len({i for i,_ in g})>1 for g in copy_groups),'cross_split_graph_edges':0},'full_support':full_support,'support_by_source':{source:aggregate([r for r in family_records if r['source']==source]) for source in sorted({r['source'] for r in family_records})},'allocation':alloc,'split_component_counts':dict(collections.Counter(c['split'] for c in comps)),'split_support':by_split,'test_panel_component_counts':dict(collections.Counter(c['test_panel'] for c in comps if c['test_panel'])),'test_panel_support':by_panel,'unsupported_panels':{'author_holdout':'No author identities','chronological_or_epoch_holdout':'No per-row dates or epochs','held_out_topic':'No verified topic labels; no topic generalization claim','held_out_domain':'Baike/Web source subdomains are observed and stratified; no source-disjoint/domain-transfer panel frozen' ,'held_out_domain_and_generator':'No domain-disjoint crossing panel; both observed source labels are broad Chinese QA'},'format_interpretation':{'web_human':'All 1500 released human strings are single-line; original writer paragraph/layout is unsupported/unknown. This alone does not prove deliberate stripping or that writers used one paragraph. Retain lexical/sentence views.','baike_paragraph_subset':'Conditional joint-support subset, subject to selection bias; does not represent the full cohort or universal writer structure.','ordered_prose':'A two-unit sentence-proxy inspection flag, not validated rhetorical/discourse annotation.'},'scope_notes':['Operational original-benchmark labels; wholly unaided human provenance not independently proved','Two early generator labels, one broad QA domain','No model fit, no detector accuracy, no synthetic rewrites','Paragraph/order support is a proxy and missingness is view-specific','Near-copy threshold is lexical; paraphrases and arbitrary partial substring copies can remain','Grouping and structural support audited across corpus before splitting; no test-outcome-based threshold/seed selection'],'weighting':{'unit':'source-aware question family','multiple_answer_weight':'1 / answer count within question family, once per human arm','view_specific_analysis':'Within-family means among available paired answers, followed by equal question weighting; missing answer/view denominators reported','uncertainty_cluster':'question/exact/near-copy connected component','no_sentence_or_repeated_human_pseudoreplication':True},'resources':{'wall_seconds':time.monotonic()-START,'cpu_seconds':time.process_time()-CPU,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'one_process':True}}
write(PUB/'aggregate_audit.json',counts)
private_paths=['cohort_identity_views.jsonl','components_and_splits.json','component_edges.jsonl'];freeze={'protocol_sha256':hashlib.sha256((PUB/'predeclared_protocol.json').read_bytes()).hexdigest(),'schema_amendment_sha256':hashlib.sha256((PUB/'SCHEMA_AMENDMENT_1.md').read_bytes()).hexdigest(),'admission_addendum_sha256':hashlib.sha256((PUB/'ADMISSION_ADDENDUM.md').read_bytes()).hexdigest(),'code_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'private_files':{p:hashlib.sha256((PRIV/p).read_bytes()).hexdigest() for p in private_paths},'source_file_sha256':{name:v['sha256'] for name,v in file_audit.items()},'seed':P['split_seed'],'frozen':True,'cpu_seconds':time.process_time()-CPU,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
write(PRIV/'freeze_manifest.json',freeze)
# Public integrity evidence hashes files as a whole, never individual identities/texts.
write(PUB/'freeze_aggregate.json',{'frozen':True,'protocol_sha256':freeze['protocol_sha256'],'schema_amendment_sha256':freeze['schema_amendment_sha256'],'admission_addendum_sha256':freeze['admission_addendum_sha256'],'code_sha256':freeze['code_sha256'],'private_manifest_bundle_sha256':digest(json.dumps(freeze['private_files'],sort_keys=True)),'seed':P['split_seed'],'component_split_counts':counts['split_component_counts'],'paired_answer_split_counts':{k:v['paired_answer_records'] for k,v in by_split.items()},'question_family_split_counts':{k:v['question_families'] for k,v in by_split.items()},'test_exposed_components':0,'cross_split_graph_edges':0})
derived=sum(p.stat().st_size for p in D.rglob('*') if p.is_file() and 'raw' not in p.relative_to(D).parts)
assert derived<=P['limits']['derived_disk_cap_bytes'],'Derived disk cap'
print(json.dumps({'frozen':True,'paired_answer_records':n,'question_families':len(firstfamily),'components':len(comps),'family_splits':{k:v['paired_answer_records'] for k,v in by_split.items()},'components_splits':counts['split_component_counts'],'resources':counts['resources'],'derived_bytes':derived},indent=2),flush=True)
