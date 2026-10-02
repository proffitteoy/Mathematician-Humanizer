from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlsplit
from pip._vendor.packaging.tags import sys_tags
from pip._vendor.packaging.utils import parse_wheel_filename
import hashlib,json,subprocess,sys,time
R=Path(__file__).resolve().parents[1];B=R.parent;W=R/'wheels';V=B/'natural-text-learning-pilot-20261002/runtime/venv/bin/python'
pins={'stanza':'1.10.1','tqdm':'4.67.1','emoji':'2.14.1','protobuf':'6.32.1','requests':'2.32.5','urllib3':'2.5.0','charset-normalizer':'3.4.3','idna':'3.10','certifi':'2025.8.3'}
tags={str(t):i for i,t in enumerate(sys_tags())};rec={'purpose':'Pinned Stanza compatibility runtime, existing Torch CPU / NumPy unchanged','pins':pins,'packages':[],'download_bytes':0,'status':'in_progress'}
def save(): (R/'public/stanza_runtime_receipt.json').write_text(json.dumps(rec,indent=2)+'\n')
for name,version in pins.items():
 data=urlopen(f'https://pypi.org/pypi/{name}/{version}/json',timeout=60).read();rec['download_bytes']+=len(data);info=json.loads(data);choices=[]
 for item in info['urls']:
  if item['packagetype']!='bdist_wheel' or item['yanked']:continue
  _,_,_,wt=parse_wheel_filename(item['filename']);matches=[tags[str(t)] for t in wt if str(t) in tags]
  if matches: choices.append((min(matches),item))
 item=min(choices,key=lambda x:x[0])[1];assert urlsplit(item['url']).hostname=='files.pythonhosted.org'
 p=W/item['filename'];blob=p.read_bytes() if p.exists() else urlopen(item['url'],timeout=60).read();rec['download_bytes']+=len(blob)
 assert hashlib.sha256(blob).hexdigest()==item['digests']['sha256'] and len(blob)==item['size'];assert rec['download_bytes']<30*1024**2
 p.write_bytes(blob);rec['packages'].append({'name':name,'version':version,'url':item['url'],'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'file':p.name});save();print(name,version,'verified',flush=True)
res=subprocess.run([sys.executable,'-m','pip','--python',str(V),'install','--no-index','--no-deps','--no-cache-dir','--no-compile']+[str(W/x['file']) for x in rec['packages']],capture_output=True,text=True,check=True,timeout=120)
(R/'public/STANZA_INSTALL.log').write_text(res.stdout+res.stderr)
res=subprocess.run([str(V),'-c',"import stanza,torch,numpy,importlib.metadata as m,json,sys;assert stanza.__version__=='1.10.1' and torch.__version__=='2.3.1+cpu' and numpy.__version__=='1.26.4' and torch.version.cuda is None; print(json.dumps({'python':sys.version,'packages':{x.metadata['Name']:x.version for x in m.distributions()}}))"],capture_output=True,text=True,check=True,timeout=60)
rec['verified']=json.loads(res.stdout);rec['status']='verified';save();print(res.stdout)
