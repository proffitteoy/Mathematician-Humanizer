from pathlib import Path
from urllib.request import urlopen,Request
from urllib.parse import urlsplit
import json,hashlib,time
B=Path(__file__).resolve().parents[2];R=B/'chinese-linguistic-restoration-20261002';P=json.loads((B/'chinese-extraction-recovery-20261002/public/input_pins.json').read_text());start=time.monotonic()
ledger={'model_repo':'stanfordnlp/stanza-zh-hans','model_commit':P['model_repo_commit'],'download_bytes':0,'files':[],'status':'in_progress'}
def save(): (R/'public/model_download_receipt.json').write_text(json.dumps(ledger,indent=2)+'\n')
for name,expected in P['models'].items():
 target=R/'models/zh-hans'/name; target.parent.mkdir(parents=True,exist_ok=True)
 url=f'https://huggingface.co/stanfordnlp/stanza-zh-hans/resolve/{P["model_repo_commit"]}/models/{name}'
 if target.exists():
  assert target.stat().st_size==expected['bytes'] and hashlib.file_digest(target.open('rb'),'sha256').hexdigest()==expected['sha256'];continue
 print('Downloading pinned model',name,expected['bytes'],flush=True);save();h=hashlib.sha256();size=0
 with urlopen(Request(url,headers={'User-Agent':'pinned-scientific-restoration/1','Accept-Encoding':'identity'}),timeout=90) as response,target.with_suffix('.part').open('wb') as out:
  host=urlsplit(response.geturl()).hostname
  assert host=='huggingface.co' or host.endswith('.hf.co') or host.endswith('.huggingface.co'),host
  while True:
   data=response.read(1024*1024)
   if not data:break
   size+=len(data);ledger['download_bytes']+=len(data)
   assert size<=expected['bytes'] and ledger['download_bytes']<700*1024**2
   assert time.monotonic()-start<25*60
   h.update(data);out.write(data)
 assert size==expected['bytes'] and h.hexdigest()==expected['sha256'],name
 target.with_suffix('.part').rename(target)
 ledger['files'].append({'file':name,'url':url,'bytes':size,'sha256':h.hexdigest(),'verified':True});save()
 print('Verified pinned model',name,flush=True)
assert hashlib.sha256((R/'models/resources.json').read_bytes()).hexdigest()==P['resources_json_sha256']
ledger['resources_json_sha256']=P['resources_json_sha256'];ledger['status']='verified';ledger['wall_seconds']=time.monotonic()-start;save();print(json.dumps({'status':'verified','download_bytes':ledger['download_bytes'],'wall_seconds':ledger['wall_seconds']}),flush=True)
