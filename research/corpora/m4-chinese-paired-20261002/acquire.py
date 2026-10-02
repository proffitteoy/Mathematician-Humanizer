"""Original bounded binary retrieval code; Python standard library only."""
import json,hashlib,pathlib,urllib.request,socket,time,resource,sys
D=pathlib.Path(__file__).resolve().parents[1]
P=json.loads((D/'public/predeclared_protocol.json').read_text())
resource.setrlimit(resource.RLIMIT_AS,(P['limits']['max_address_space_bytes'],)*2)
resource.setrlimit(resource.RLIMIT_CPU,(60,60))
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**kw): raise RuntimeError('Redirect not authorized')
opener=urllib.request.build_opener(NoRedirect)
log={'protocol_sha256':hashlib.sha256((D/'public/predeclared_protocol.json').read_bytes()).hexdigest(),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'actual_payload_bytes':0,'attempts':[],'files':[]}
def save(): (D/'private/acquisition_log.json').write_text(json.dumps(log,indent=2))
for f in P['files']:
 url='https://raw.githubusercontent.com/mbzuai-nlp/M4/'+P['revision']+'/data/'+f['name']
 target=D/'raw'/f['name']
 if target.exists(): raise RuntimeError('Refusing existing raw path; inspect existing log, do not repeat transfer')
 for attempt in (1,2):
  if log['actual_payload_bytes']+f['bytes']>P['raw_transfer_cap_bytes']: raise RuntimeError('Insufficient budget for full-file attempt')
  entry={'url':url,'attempt':attempt,'payload_bytes':0};log['attempts'].append(entry);save()
  try:
   req=urllib.request.Request(url,headers={'Accept-Encoding':'identity','User-Agent':'bounded-private-scientific-schema-audit/1'})
   with opener.open(req,timeout=40) as response, target.open('wb') as out:
    if response.headers.get('Content-Encoding','identity')!='identity': raise RuntimeError('Unexpected content encoding')
    while True:
     chunk=response.read(min(65536,P['raw_transfer_cap_bytes']-log['actual_payload_bytes']+1))
     if not chunk: break
     entry['payload_bytes']+=len(chunk);log['actual_payload_bytes']+=len(chunk)
     if log['actual_payload_bytes']>P['raw_transfer_cap_bytes'] or entry['payload_bytes']>f['bytes']: raise RuntimeError('Budget or advertised size exceeded')
     out.write(chunk);save()
   b=target.read_bytes(); sha=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
   if len(b)!=f['bytes'] or sha!=f['git_blob_sha1']: raise RuntimeError('Length/blob verification failed')
   entry['status']='complete';log['files'].append(dict(f,url=url,sha256=hashlib.sha256(b).hexdigest(),verified_git_blob=sha));save();print(f['name'],len(b),sha,flush=True);break
  except Exception as e:
   timeout=isinstance(e,(TimeoutError,socket.timeout)) or isinstance(e,urllib.error.URLError) and isinstance(e.reason,(TimeoutError,socket.timeout))
   entry.update(status='timeout' if timeout else 'failed',error=str(e));save()
   if timeout and attempt==1: continue
   raise
log['completed_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());save()
print('ACTUAL PAYLOAD',log['actual_payload_bytes'])
