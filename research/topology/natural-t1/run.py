"""Bounded local T1 instrumentation pilot; no model fitting or origin labels."""
import os,sys,json,time,threading,hashlib,socket,resource,signal
from pathlib import Path
from collections import Counter
from unittest.mock import patch
ROOT=Path('/workspace/shared/style-compiler')
sys.path.insert(0,str(ROOT/'research/topology'))
HERE=Path(__file__).parent
PRIVATE=Path('/workspace/shared/style-compiler-data/topology-natural-20261001')
def sha(b):return hashlib.sha256(b).hexdigest()
protocol_bytes=(HERE/'preregister.public.json').read_bytes();protocol=json.loads(protocol_bytes)
manifest_bytes=(PRIVATE/'selection.private.json').read_bytes()
assert sha(manifest_bytes)==protocol['private_manifest_sha256']
manifest=json.loads(manifest_bytes)
assert sha((ROOT/'research/topology/encoder-profile.json').read_bytes())==protocol['encoder_profile_sha256']
assert len(manifest['selected'])==6
for item in manifest['selected']:assert sha(Path(item['raw_file']).read_bytes())==item['sha256']
started=time.monotonic();stop=threading.Event();network={'attempts':0};limit=protocol['budgets']
def monitor():
 while not stop.wait(.2):
  rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
  size=sum(p.stat().st_size for p in PRIVATE.iterdir() if p.is_file())
  reason='rss_cap' if rss>limit['rss_mib']*1024 else ('private_disk_cap' if size>limit['private_derivative_bytes'] else ('wall_cap' if time.monotonic()-started>limit['wall_seconds'] else None))
  if reason:
   (PRIVATE/'resource-stop.json').write_text(json.dumps({'reason':reason,'rss_kib':rss,'bytes':size}))
   os._exit(72)
def deny(*a,**k):
 network['attempts']+=1
 raise RuntimeError('network_forbidden')
threading.Thread(target=monitor,daemon=True).start()
rows=[]
try:
 with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(socket,'create_connection',deny):
  import numpy as np
  from encoder import LocalEncoder
  from phd import Config,estimate
  encoder=LocalEncoder('/workspace/shared/style-models/xlm-roberta-base')
  for i,item in enumerate(manifest['selected']):
   raw=Path(item['raw_file']).read_bytes();assert sha(raw)==item['sha256']
   text=raw.decode('utf-8')
   cloud,meta=encoder.encode(text)
   if i==0:
    repeated,meta2=encoder.encode(text)
    assert meta2['cloud']['npy_sha256']==meta['cloud']['npy_sha256']
   np.save(PRIVATE/f'cloud-{i}.npy',cloud,allow_pickle=False)
   result=estimate(cloud,Config(**protocol['phd_profile']))
   rows.append({'index':i,'source_path':item['path'],'extraction':meta,'phd':result})
   (PRIVATE/'results.private.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,allow_nan=False))
   print(json.dumps({'completed':len(rows),'retained_points':len(cloud),'status':result['status']}),flush=True)
 assert network['attempts']==0
 ok=[r['phd']['dimension'] for r in rows if r['phd']['status']=='ok']
 toks=[r['extraction']['tokenization'] for r in rows]
 report={'schema':'topology-natural-instrument-results/0.1','status':'complete','protocol_sha256':sha(protocol_bytes),'run_source_sha256':sha(Path(__file__).read_bytes()),'selected':6,'completed':len(rows),'extraction_failures':0,'phd_status':dict(Counter(r['phd']['status'] for r in rows)),'phd_abstention_reasons':dict(Counter(r['phd'].get('reason') for r in rows if r['phd']['status']!='ok')),'truncated_sources':sum(t['was_truncated'] for t in toks),'untruncated_token_count_range':[min(t['untruncated_tokens_including_specials'] for t in toks),max(t['untruncated_tokens_including_specials'] for t in toks)],'retained_point_count_range':[min(t['retained_tokens'] for t in toks),max(t['retained_tokens'] for t in toks)],'dimension_conditional_on_numerical_success':{'n':len(ok),'min':min(ok) if ok else None,'max':max(ok) if ok else None,'median':float(np.median(ok)) if ok else None},'first_case_exact_same_process_repeat':True,'network_attempts':network['attempts'],'wall_seconds':time.monotonic()-started,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'private_results_sha256':sha((PRIVATE/'results.private.json').read_bytes()),'scope':'Raw Markdown prefixes including metadata/code/quotes; no verified human origin, body-only style, cross-genre inference, classifier or model fit','monte_carlo_scope':'Rerun variation is conditional finite-cloud sampling variation, not population uncertainty','runtime':rows[0]['extraction']['runtime']}
 (HERE/'results.aggregate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print(json.dumps(report,ensure_ascii=False),flush=True)
finally:stop.set()
