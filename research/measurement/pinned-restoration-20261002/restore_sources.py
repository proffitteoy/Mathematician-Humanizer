from pathlib import Path
from urllib.request import urlopen,Request
import hashlib,json,time
B=Path(__file__).resolve().parents[2]
for directory in ('chinese-linguistic-restoration-20261002','m4_chinese_paired_20261002'):
 root=B/directory;plan=json.loads((root/'public/source_plan.json').read_text());manifest=[]
 for f in plan['files']:
  p=(root/'repo'/f['path']) if directory.startswith('chinese-') else (root/'public'/Path(f['path']).name)
  if directory.startswith('m4_') and (root/'published_receipts'/Path(f['path']).name).exists():p=root/'published_receipts'/Path(f['path']).name
  url=f'https://raw.githubusercontent.com/{plan["repo"]}/{plan["revision"]}/{f["path"]}'
  data=p.read_bytes() if p.exists() else urlopen(Request(url,headers={'User-Agent':'pinned-scientific-restoration/1'}),timeout=60).read()
  sha=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  assert sha==f['sha'] and len(data)==f['size'],f['path']
  p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
  manifest.append({'path':f['path'],'url':url,'bytes':len(data),'git_blob_sha1':sha,'sha256':hashlib.sha256(data).hexdigest()})
  (root/'public/restored_sources.json').write_text(json.dumps({'revision':plan['revision'],'files':manifest},indent=2)+'\n')
 print(directory,len(manifest),'source files verified',flush=True)
