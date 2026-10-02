#!/usr/bin/env python3
"""One bounded, no-retry acquisition of a supplied immutable Markdown manifest.
Private noncommercial research; NEVER execute downloaded source. Output includes
private document receipts; do not publish the private directory or payloads.
"""
import concurrent.futures, collections, datetime, hashlib, json, pathlib, resource, signal, threading, time, urllib.request, urllib.error
ROOT=pathlib.Path(__file__).resolve().parents[1]
PREV=ROOT.parent/'research_longform_acquisition'
PRIVATE=ROOT/'private'
CAP=20*1024**2
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
signal.alarm(590)
START=time.monotonic()
STAMP=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
sha256=lambda b:hashlib.sha256(b).hexdigest()

def save(path,obj):
 path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs): return None

proposal_path=PREV/'deliverables/next_batch_proposal.json'
proposal_bytes=proposal_path.read_bytes(); proposal=json.loads(proposal_bytes)
rows=proposal['files']
assert len(rows)==221 and sum(x['declared_bytes'] for x in rows)==2790922
assert collections.Counter(x['source_id'] for x in rows)=={'yihui':49,'yufree':172}
assert len({(x['source_id'],x['source_path']) for x in rows})==221
sample=json.load(open(PREV/'deliverables/candidate_manifest.json'))
prior={(x['source_id'],x['source_path']) for x in sample['documents']}
sources=sample['sources']
trees={s:{x['path']:x for x in json.load(open(PREV/'metadata'/f'{s}_tree.json'))['tree']} for s in ['yihui','yufree']}
for row in rows:
 s=row['source_id']; p=row['source_path']; assert s in ['yihui','yufree']
 assert p.startswith('content/cn/') and p.endswith('.md') and '/kids/' not in p and '..' not in pathlib.PurePosixPath(p).parts
 assert (s,p) not in prior and row['declared_bytes']>=6000
 assert '2015-01-01'<=row['path_date_claim']<'2022-01-01'
 assert trees[s][p]['size']==row['declared_bytes'] and trees[s][p]['sha']==row['git_blob_sha1']
 assert row['raw_url']==f"https://raw.githubusercontent.com/{sources[s]['repository']}/{sources[s]['commit']}/{p}"
 assert row['text_license']=='CC-BY-NC-SA-4.0'
assert not (PRIVATE/'acquisition_state.json').exists(), 'Existing run: do not silently repeat requests'
base=json.load(open(PREV/'deliverables/acquisition_receipt.json'))['conservative_accounted_primary_payload_bytes']
reserve=133637 # separate reproduction cache; no receipt establishes copy vs extra HTTP
assert base+reserve+sum(x['declared_bytes']+1 for x in rows)<CAP
states=[dict(row, ordinal=i+1, status='pending', actual_response_body_bytes=0, attempts=0) for i,row in enumerate(rows)]
lock=threading.Lock()
state={'schema':'private-pinned-batch-receipts/1.0','started_utc':STAMP(),'proposal_sha256':sha256(proposal_bytes),'prior_accounted_bytes':base,'prior_reproduction_uncertainty_reserve':reserve,'requests_max_in_flight':4,'automatic_retries':0,'redirects_followed':0,'candidates':states}
save(PRIVATE/'proposal_frozen.json',proposal)
save(PRIVATE/'acquisition_state.json',state)

def run(i):
 row=states[i]
 if time.monotonic()-START>540:
  row['status']='not_attempted_deadline'; return row
 with lock:
  row.update(status='request_started',attempts=1,request_started_utc=STAMP())
  save(PRIVATE/'acquisition_state.json',state)
 body=bytearray();resp=None
 try:
  req=urllib.request.Request(row['raw_url'],headers={'User-Agent':'bounded-noncommercial-source-audit/1.0','Accept-Encoding':'identity'})
  opener=urllib.request.build_opener(NoRedirect)
  resp=opener.open(req,timeout=20)
  row['http_status']=resp.status
  while len(body)<row['declared_bytes']+1:
   chunk=resp.read(min(16384,row['declared_bytes']+1-len(body)))
   if not chunk:break
   body.extend(chunk)
  b=bytes(body); row['actual_response_body_bytes']=len(b)
  row['sha256']=sha256(b); row['observed_git_blob_sha1']=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
  assert resp.status==200,'Unexpected HTTP status'
  assert len(b)==row['declared_bytes'],'Size mismatch'
  assert row['observed_git_blob_sha1']==row['git_blob_sha1'],'Git blob mismatch'
  b.decode('utf-8')
  path=PRIVATE/'payloads'/row['source_id']/row['source_path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b)
  row['status']='verified';row['private_relative_path']=str(path.relative_to(PRIVATE))
 except urllib.error.HTTPError as e:
  row['http_status']=e.code
  try: body.extend(e.read(min(row['declared_bytes']+1,65536)))
  except Exception as sub:row['error_body_read_error']=type(sub).__name__
  row['status']='http_failure';row['error']=str(e)
 except Exception as e:
  row['status']='request_or_identity_failure';row['error']=type(e).__name__+': '+str(e)
 finally:
  if resp:resp.close()
  row['actual_response_body_bytes']=len(body)
  row['finished_utc']=STAMP()
  with lock:save(PRIVATE/'acquisition_state.json',state)
 return row

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for index,row in enumerate(pool.map(run,range(len(states))),1):
  if index%25==0 or row['status']!='verified':print(index,row['status'],flush=True)
state.update(finished_utc=STAMP(),elapsed_seconds=round(time.monotonic()-START,3),max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
save(PRIVATE/'acquisition_state.json',state)
success=[x for x in states if x['status']=='verified']
transfer=sum(x['actual_response_body_bytes'] for x in states)
receipt={'schema':'bounded-pinned-batch-acquisition/1.0','original_candidate_denominator':221,'proposal_declared_source_bytes':2790922,'verified_documents':len(success),'verified_source_bytes':sum(x['declared_bytes'] for x in success),'attempted_requests':sum(x['attempts'] for x in states),'failure_or_unattempted_counts':dict(collections.Counter(x['status'] for x in states if x['status']!='verified')),'body_bytes_received_including_failures':transfer,'prior_accounted_payload_bytes':base,'prior_reproduction_cache_uncertainty_reserve_bytes':reserve,'cumulative_conservative_accounted_bytes':base+reserve+transfer,'cap_bytes':CAP,'automatic_retries':0,'replacements':0,'redirects_followed':0,'max_parallel_requests_in_one_process':4,'memory_limit_bytes':512*1024**2,'max_rss_kib':state['max_rss_kib'],'wall_clock_limit_seconds':590,'elapsed_seconds':state['elapsed_seconds'],'proposal_sha256':sha256(proposal_bytes),'by_source':{s:{'candidates':sum(x['source_id']==s for x in states),'verified':sum(x['source_id']==s for x in success),'verified_bytes':sum(x['declared_bytes'] for x in success if x['source_id']==s)} for s in ['yihui','yufree']},'payload_accounting_note':'Logical HTTP response body bytes, not TLS/on-wire bytes. Prior reproduction reserve is conservatively additive because its cache creation lacks a transfer receipt. Read lengths never exceed declared size plus one. No new metadata, images, archives, executable files, or supplemental source bodies fetched.','raw_published':False}
assert receipt['cumulative_conservative_accounted_bytes']<CAP
save(ROOT/'deliverables/acquisition_receipt.json',receipt)
print(json.dumps(receipt,indent=2))
