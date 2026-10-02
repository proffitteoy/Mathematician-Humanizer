#!/usr/bin/env python3
"""Run unchanged extraction with child-process backups under one resource watchdog."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path

def write(p,x):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,sort_keys=True)+'\n');os.replace(t,p)
def count_commits(path):
 if not path.exists():return 0
 names=set()
 for line in path.read_bytes().splitlines(keepends=True):
  if not line.endswith(b'\n'):break
  e=json.loads(line)
  if e.get('event')=='cache_committed':names.add(e['cache_file'])
 return len(names)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--python',required=True);ap.add_argument('--interval',type=int,default=500);a=ap.parse_args()
 root=Path(a.root).resolve();pub=root/'public';private=root/'private';backup_root=private/'secondary_cache';backup_root.mkdir(parents=True,exist_ok=True)
 start=time.monotonic();log=(private/'full_rerun.log').open('ab')
 child=subprocess.Popen([a.python,str(pub/'extract.py'),'full'],stdout=log,stderr=subprocess.STDOUT)
 packing=None;packing_log=None;pending=None;last_archived=0;last_verified=0;backup_failure=None;generation_count=0
 write(private/'rerun_supervisor_state.json',{'extractor_pid':child.pid,'status':'running','last_tool_store_verified_count':0})
 while True:
  count=count_commits(private/'execution_ledger.jsonl')
  if packing is not None and packing.poll() is not None:
   packing_log.close();receipt_path=pending/'backup_attempt_receipt.json'
   if packing.returncode or not receipt_path.exists():backup_failure={'reason':'archive_process_failed','generation':pending.name,'exit_code':packing.returncode}
   else:
    receipt=json.loads(receipt_path.read_bytes())
    if not receipt['success']:backup_failure=receipt
    else:
     last_archived=receipt['committed_cache_count'];receipt['generation']=pending.name
     write(private/'secondary_backup_ready.json',receipt)
     print(json.dumps({'event':'secondary_archive_ready','generation':pending.name,'count':last_archived,'compressed_bytes':receipt['compressed_bytes'],'archive_sha256':receipt['archive_sha256']}),flush=True)
   packing=None
   if backup_failure:
    write(private/'secondary_backup_failure.json',backup_failure);print(json.dumps({'event':'secondary_archive_failed','detail':backup_failure}),flush=True);pending=None
  if pending is not None and packing is None:
   ack=pending/'tool_store_verified.json'
   if ack.exists():
    data=json.loads(ack.read_bytes());receipt=json.loads((pending/'backup_attempt_receipt.json').read_bytes())
    assert data['verified'] and data['archive_sha256']==receipt['archive_sha256'] and data['last_backed_up_count']==receipt['committed_cache_count'],'invalid_tool_store_ack'
    last_verified=data['last_backed_up_count'];write(private/'last_secondary_backup_verified.json',data);pending=None
    print(json.dumps({'event':'secondary_tool_store_verified','count':last_verified,'archive_sha256':data['archive_sha256']}),flush=True)
  done=child.poll() is not None
  need=(count-last_archived>=a.interval) or (done and child.returncode==0 and count>last_archived)
  if need and packing is None and pending is None and backup_failure is None:
   generation_count+=1;pending=backup_root/f'g{generation_count:03d}_c{count:06d}';pending.mkdir()
   packing_log=(pending/'pack.log').open('ab')
   packing=subprocess.Popen([sys.executable,str(pub/'secondary_cache.py'),'pack','--root',str(root),'--destination',str(pending)],stdout=packing_log,stderr=subprocess.STDOUT)
  if done and (backup_failure or child.returncode!=0 or (packing is None and pending is None and last_verified==count)):
   break
  time.sleep(2)
 log.close()
 receipt={'extractor_exit_code':child.returncode,'committed_cache_count':count,'last_tool_store_verified_count':last_verified,'backup_failure':backup_failure,'elapsed_seconds':time.monotonic()-start,'secondary_store_guaranteed_durable':False,'done':child.returncode==0 and backup_failure is None and count==last_verified}
 write(pub/'rerun_supervisor_receipt.json',receipt);print(json.dumps(receipt),flush=True)
 raise SystemExit(0 if receipt['done'] else 2)
if __name__=='__main__':main()
