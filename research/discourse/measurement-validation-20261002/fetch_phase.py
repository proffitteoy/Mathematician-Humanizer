#!/usr/bin/env python3
"""Private, pinned, bounded GCDT retrieval. Never releases the source files."""
import argparse, hashlib, json, pathlib, urllib.request, time
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parent
CACHE=pathlib.Path('/tmp/gcdt-validation-private')
MANIFEST=ROOT/'research_discourse_validation/minimal_gcdt_manifest.json'
MAX_BYTES=10*1024*1024

def main():
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['dev','test']); a=p.parse_args()
 if a.phase=='test':
  f=json.loads((HERE/'freeze.json').read_text())
  for path,sha in f['sha256'].items():
   assert hashlib.sha256((HERE/path).read_bytes()).hexdigest()==sha, 'Frozen file changed'
 m=json.loads(MANIFEST.read_text()); meta=json.loads((ROOT/'research_discourse_validation/GCDT_metadata.json').read_text())
 blobs={x['path']:x.get('sha') for x in meta['files']}
 logpath=HERE/'download_log.json'; log=json.loads(logpath.read_text()) if logpath.exists() else []
 for d in m['documents']:
  if d['split']!=a.phase: continue
  paths=[d['files'][k]['path'] for k in ['xml','tokenized','rs3']]+d['double_rst_paths']+d['alternate_segmentation_paths']
  for path in paths:
   dest=CACHE/path;url=f"https://raw.githubusercontent.com/logan-siyao-peng/GCDT/{m['commit']}/{path}"
   if dest.exists(): data=dest.read_bytes()
   else:
    with urllib.request.urlopen(url, timeout=25) as r:data=r.read(1024*1024+1)
    assert len(data)<=1024*1024,'Single-file bound exceeded'
    assert sum(x.stat().st_size for x in CACHE.rglob('*') if x.is_file())+len(data)<=MAX_BYTES,'Download cap exceeded'
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
   git=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
   expected=blobs.get(path)
   if expected:assert git==expected,(path,'Git blob mismatch')
   if not any(x['path']==path for x in log):log.append({'path':path,'url':url,'bytes':len(data),'git_blob_sha':git,'verified_expected_blob':bool(expected),'sha256':hashlib.sha256(data).hexdigest(),'download_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
   logpath.write_text(json.dumps(log,indent=2)+'\n')
 print(json.dumps({'phase':a.phase,'downloaded_bytes_all_phases':sum(x['bytes'] for x in log),'files_all_phases':len(log)}))
if __name__=='__main__':main()
