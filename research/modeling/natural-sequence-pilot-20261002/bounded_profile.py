#!/usr/bin/env python3
"""Stdlib Linux process-tree watchdog for the approved cost-only profile."""
import argparse,json,os,signal,subprocess,time
from pathlib import Path

def process_tree(pid,cpu_seen=None):
    # Some Linux runtimes omit /proc/PID/task/PID/children. Build the descendant
    # relation from stat PPIDs instead, without reading process command lines.
    snapshot={};page=os.sysconf('SC_PAGE_SIZE');ticks=os.sysconf('SC_CLK_TCK')
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():continue
        try:
            fields=(directory/'stat').read_text().rsplit(')',1)[1].split()
            resident=int((directory/'statm').read_text().split()[1])*page
            snapshot[int(directory.name)]=(int(fields[1]),resident,(int(fields[11])+int(fields[12]))/ticks,int(fields[19]))
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
    selected={pid};changed=True
    while changed:
        additions={p for p,(parent,*_) in snapshot.items() if parent in selected}-selected
        changed=bool(additions);selected|=additions
    rss=sum(snapshot[p][1] for p in selected if p in snapshot)
    if cpu_seen is None:cpu_seen={}
    for p in selected:
        if p in snapshot:
            _,_,cpu,started=snapshot[p];key=(p,started);cpu_seen[key]=max(cpu_seen.get(key,0),cpu)
    return rss,sum(cpu_seen.values())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--metrics',required=True);ap.add_argument('command',nargs=argparse.REMAINDER);a=ap.parse_args()
    command=a.command[1:] if a.command and a.command[0]=='--' else a.command
    if not command:raise ValueError('Command required')
    cores=sorted(os.sched_getaffinity(0))[:2]
    env={**os.environ,'OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','NUMEXPR_NUM_THREADS':'2','TOKENIZERS_PARALLELISM':'false'}
    p=subprocess.Popen(command,env=env,preexec_fn=lambda:os.sched_setaffinity(0,cores),start_new_session=True)
    start=time.monotonic();peak=0;peak_cpu=0.;reason=None;cpu_seen={}
    while p.poll() is None:
        rss,cpu=process_tree(p.pid,cpu_seen);peak=max(peak,rss);peak_cpu=max(peak_cpu,cpu)
        if rss>2*1024**3:reason='2GiB_process_tree_RSS'
        if cpu>1200:reason='20minute_aggregate_CPU'
        if time.monotonic()-start>1200:reason='20minute_wall'
        if reason:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        time.sleep(.05)
    result={'command':command,'affinity_cores':cores,'elapsed_seconds':time.monotonic()-start,'peak_process_tree_rss_bytes_sampled_50ms':peak,
        'cpu_seconds_sampled':peak_cpu,'exit_code':p.returncode,'stopped_reason':reason,'rss_limit_bytes':2*1024**3,'cpu_limit_seconds':1200,'wall_limit_seconds':1200}
    Path(a.metrics).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True);raise SystemExit(p.returncode)
if __name__=='__main__':main()
