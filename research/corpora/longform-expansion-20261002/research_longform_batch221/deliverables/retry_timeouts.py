#!/usr/bin/env python3
"""One explicitly authorized recorded retry of the SAME four first-pass zero-body timeouts.
First-pass receipt/state is immutable. Retry must finish inside original 590s window.
"""
import concurrent.futures,copy,datetime,hashlib,json,pathlib,resource,signal,time,urllib.request,urllib.error
R=pathlib.Path(__file__).resolve().parents[1];P=R/'private';D=R/'deliverables';resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def utc():return datetime.datetime.now(datetime.timezone.utc)
first=json.load(open(P/'acquisition_state.json'));receipt=json.load(open(D/'acquisition_receipt.json'));start=datetime.datetime.fromisoformat(first['started_utc']);remaining=590-(utc()-start).total_seconds();assert remaining>30,'Original cap elapsed or insufficient time'
signal.alarm(int(remaining));failures=[r for r in first['candidates'] if r['status']!='verified'];assert len(failures)==4
assert all(r['source_id']=='yufree' and r['actual_response_body_bytes']==0 and r['error']=='URLError: <urlopen error timed out>' for r in failures)
assert not (P/'retry_receipt.json').exists(),'Do not automatically retry retry'
assert receipt['cumulative_conservative_accounted_bytes']+sum(r['declared_bytes']+1 for r in failures)<20*1024**2
retry={'authorization':'Parent explicitly authorized one logged retry of the same four zero-body timeout identities, preserving first pass and original 590-second total wall limit.','first_pass_receipt_sha256':hashlib.sha256((D/'acquisition_receipt.json').read_bytes()).hexdigest(),'first_pass_state_sha256':hashlib.sha256((P/'acquisition_state.json').read_bytes()).hexdigest(),'original_candidate_denominator':221,'started_utc':utc().isoformat(),'first_pass_verified':217,'first_pass_zero_body_timeouts':4,'attempts':[]}
for r in failures:retry['attempts'].append({'source_id':r['source_id'],'source_path':r['source_path'],'raw_url':r['raw_url'],'git_blob_sha1':r['git_blob_sha1'],'declared_bytes':r['declared_bytes'],'attempt_number':2,'status':'scheduled','actual_response_body_bytes':0})
write(P/'retry_receipt.json',retry)
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**k):return None

def fetch(row):
 row['started_utc']=utc().isoformat();b=bytearray();response=None
 try:
  assert (utc()-start).total_seconds()<565,'No time left under original cap'
  req=urllib.request.Request(row['raw_url'],headers={'User-Agent':'bounded-noncommercial-source-audit/1.0','Accept-Encoding':'identity'})
  response=urllib.request.build_opener(NoRedirect).open(req,timeout=20);row['http_status']=response.status
  while len(b)<row['declared_bytes']+1:
   chunk=response.read(min(16384,row['declared_bytes']+1-len(b)))
   if not chunk:break
   b.extend(chunk)
  raw=bytes(b);row['sha256']=hashlib.sha256(raw).hexdigest();row['observed_git_blob_sha1']=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
  assert response.status==200 and len(raw)==row['declared_bytes'] and row['observed_git_blob_sha1']==row['git_blob_sha1'];raw.decode('utf-8')
  dest=P/'payloads'/row['source_id']/row['source_path'];assert not dest.exists();dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
  row['private_relative_path']=str(dest.relative_to(P));row['status']='verified'
 except Exception as e:
  row['status']='retry_failure';row['error']=type(e).__name__+': '+str(e)
  if isinstance(e,urllib.error.HTTPError):
   try:b.extend(e.read(min(row['declared_bytes']+1,65536)))
   except Exception:pass
 finally:
  if response:response.close()
  row['actual_response_body_bytes']=len(b);row['finished_utc']=utc().isoformat()
 return row
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for row in pool.map(fetch,retry['attempts']):print(row['source_path'],row['status'],flush=True)
retry.update(finished_utc=utc().isoformat(),total_elapsed_from_first_acquisition_start_seconds=(utc()-start).total_seconds(),max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
write(P/'retry_receipt.json',retry)
final=copy.deepcopy(first);lookup={(x['source_id'],x['source_path']):x for x in retry['attempts']}
for r in final['candidates']:
 k=(r['source_id'],r['source_path'])
 if k in lookup:
  r['first_pass_status']=r['status'];r['first_pass_error']=r['error'];r['attempts']=2
  rr=lookup[k]
  for field in ['status','actual_response_body_bytes','sha256','observed_git_blob_sha1','private_relative_path','http_status','finished_utc']:
   if field in rr:r[field]=rr[field]
  if rr['status']=='verified':r.pop('error',None)
final['retry_receipt_path']='retry_receipt.json';final['finalized_utc']=utc().isoformat();write(P/'final_identity_manifest.json',final)
verified=[r for r in final['candidates'] if r['status']=='verified'];transfer=sum(r['actual_response_body_bytes'] for r in retry['attempts'])
final_receipt=copy.deepcopy(receipt);final_receipt.update(first_pass_verified_documents=217,first_pass_attempted_requests=221,first_pass_zero_body_timeouts=4,explicitly_authorized_retry_requests=4,successful_retry_documents=sum(r['status']=='verified' for r in retry['attempts']),verified_documents=len(verified),verified_source_bytes=sum(r['declared_bytes'] for r in verified),attempted_requests=225,failure_or_unattempted_counts=dict(__import__('collections').Counter(r['status'] for r in final['candidates'] if r['status']!='verified')),body_bytes_received_including_failures=receipt['body_bytes_received_including_failures']+transfer,cumulative_conservative_accounted_bytes=receipt['cumulative_conservative_accounted_bytes']+transfer,total_elapsed_from_first_acquisition_start_seconds=retry['total_elapsed_from_first_acquisition_start_seconds'],first_pass_receipt_sha256=retry['first_pass_receipt_sha256'],by_source={s:{'candidates':sum(r['source_id']==s for r in final['candidates']),'verified':sum(r['source_id']==s for r in verified),'verified_bytes':sum(r['declared_bytes'] for r in verified if r['source_id']==s)} for s in ['yihui','yufree']})
write(D/'final_acquisition_receipt.json',final_receipt)
print(json.dumps({'final_verified':len(verified),'retry_bytes':transfer,'original_window_elapsed':retry['total_elapsed_from_first_acquisition_start_seconds'],'cumulative_bytes':final_receipt['cumulative_conservative_accounted_bytes']}))
