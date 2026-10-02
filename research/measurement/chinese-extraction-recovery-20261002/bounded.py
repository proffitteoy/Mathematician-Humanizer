#!/usr/bin/env python3
"""Two-CPU,2GiB tree RSS,1GiB new derived disk,aggregate120min wall watchdog."""
import argparse,json,os,pathlib,signal,subprocess,time
import psutil
ap=argparse.ArgumentParser();ap.add_argument('--phase',required=True);ap.add_argument('--wall-limit',type=float,default=7200);ap.add_argument('command',nargs=argparse.REMAINDER);a=ap.parse_args()
root=pathlib.Path(__file__).resolve().parents[1]
command=a.command[1:] if a.command[0]=='--' else a.command
cores=sorted(os.sched_getaffinity(0))[:2]
env={**os.environ,'OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','NUMEXPR_NUM_THREADS':'2','TOKENIZERS_PARALLELISM':'false','PYTHONDONTWRITEBYTECODE':'1'}
start=time.monotonic();peak=0;cpu=0;reason=None;disk=0;lastdisk=-10
p=subprocess.Popen(command,env=env,preexec_fn=lambda:os.sched_setaffinity(0,cores),start_new_session=True)
while p.poll() is None:
    elapsed=time.monotonic()-start
    try:
        ps=[psutil.Process(p.pid)]+psutil.Process(p.pid).children(recursive=True)
        rss=sum(q.memory_info().rss for q in ps);peak=max(peak,rss)
        cpu=max(cpu,sum(q.cpu_times().user+q.cpu_times().system for q in ps))
        if elapsed-lastdisk>=5:
            disk=sum(q.stat().st_size for q in root.rglob('*') if q.is_file());lastdisk=elapsed
        if rss>2*1024**3:reason='2_GiB_tree_RSS_limit'
        if disk>1024**3:reason='1_GiB_new_derived_disk_limit'
        if elapsed>a.wall_limit:reason='authorized_wall_time_limit'
        if reason:os.killpg(p.pid,signal.SIGKILL)
    except psutil.NoSuchProcess:pass
    time.sleep(.1)
p.wait()
r={'phase':a.phase,'affinity_cores':cores,'elapsed_seconds':time.monotonic()-start,'peak_process_tree_rss_bytes_sampled_100ms':peak,
 'cpu_seconds_sampled':cpu,'exit_code':p.returncode,'stopped_reason':reason,'rss_limit_bytes':2*1024**3,'wall_limit_seconds':a.wall_limit,'derived_bytes_sampled':disk}
(root/'public'/f'{a.phase}_resource_receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
raise SystemExit(p.returncode)
