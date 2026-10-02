#!/usr/bin/env python3
"""Phase watchdog and explicit CPU reconciliation; no model or feature loading."""
import argparse,json,os,signal,subprocess,time
from pathlib import Path
from bounded_profile import process_tree

ROOT=Path(__file__).resolve().parent

def events(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x] if path.exists() else []

def consumed(rows):
    costs={}
    for e in rows:costs[e['run_id']]=max(costs.get(e['run_id'],0),e.get('cpu_seconds',0),e.get('cpu_seconds_current_fit',0))
    return sum(costs.values())

def append(path,row):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as f:f.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--approval',required=True);ap.add_argument('--metrics',required=True);ap.add_argument('command',nargs=argparse.REMAINDER);a=ap.parse_args()
    approval=json.loads(Path(a.approval).read_text())
    if not approval.get('approved') or not approval.get('optimizer_fits_approved'):raise PermissionError('Explicit phase optimizer authorization required')
    cpu_limit=approval['max_phase_cpu_seconds'];wall_limit=approval['max_phase_wall_seconds']
    if not 0<cpu_limit<=18*3600 or not 0<wall_limit<=18*3600:raise ValueError('Phase cannot exceed18CPU/wall hours')
    command=a.command[1:] if a.command and a.command[0]=='--' else a.command
    if not command:raise ValueError('Runner command required')
    cores=sorted(os.sched_getaffinity(0))[:2];private=ROOT/'private/staged';private.mkdir(parents=True,exist_ok=True)
    ledger=private/'fit_ledger.jsonl';before=consumed(events(ledger));identity=str(time.time_ns());journal=private/('watchdog.'+identity+'.jsonl')
    if before>=24*3600:raise RuntimeError('Original cumulative CPU budget exhausted')
    env={**os.environ,'OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','NUMEXPR_NUM_THREADS':'2'}
    p=subprocess.Popen(command,env=env,preexec_fn=lambda:os.sched_setaffinity(0,cores),start_new_session=True)
    start=time.monotonic();peak=0;peak_cpu=0.;seen={};reason=None;last=0
    while p.poll() is None:
        rss,cpu=process_tree(p.pid,seen);peak=max(peak,rss);peak_cpu=max(peak_cpu,cpu);elapsed=time.monotonic()-start
        if elapsed-last>=10:
            append(journal,{'event':'resource_heartbeat','pid':p.pid,'wall_seconds':elapsed,'cpu_seconds':cpu,'rss_bytes':rss});last=elapsed
        if rss>2*1024**3:reason='2GiB_process_tree_RSS'
        if cpu>cpu_limit:reason='phase_CPU_limit'
        if before+cpu>24*3600:reason='original_global_CPU_limit'
        if elapsed>wall_limit:reason='phase_wall_limit'
        if reason:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        time.sleep(.05)
    # Charge a killed/unfinished interval to its exact current run when the
    # runner's identity marker belongs to this PID. No previous CPU is erased.
    active_path=private/'ACTIVE_RUN.json'
    if active_path.exists():
        active=json.loads(active_path.read_text())
        if active.get('process_pid')==p.pid:
            actual=active.get('prior_run_cpu_seconds',0)+max(0,peak_cpu-active['process_cpu_seconds_at_start'])
            append(ledger,{'event':'watchdog_cpu_reconciliation','run_id':active['run_id'],'cpu_seconds':actual,
                          'phase_id':approval['phase_id'],'watchdog_pid':p.pid,'interruption_reason':reason})
    accounted=consumed(events(ledger))-before
    if peak_cpu>accounted:
        append(ledger,{'event':'nonfit_resource_cpu','run_id':'resource.watchdog.'+identity,'cpu_seconds':peak_cpu-accounted,
                       'purpose':'Process startup, data loading, analytic baseline and other uncharged phase overhead'})
    result={'command':command,'phase_id':approval['phase_id'],'affinity_cores':cores,'elapsed_seconds':time.monotonic()-start,
            'peak_process_tree_rss_bytes_sampled_50ms':peak,'cpu_seconds_sampled':peak_cpu,'exit_code':p.returncode,'stopped_reason':reason,
            'global_cpu_seconds_used':consumed(events(ledger)),'global_cpu_seconds_remaining':24*3600-consumed(events(ledger)),
            'rss_limit_bytes':2*1024**3,'phase_cpu_limit_seconds':cpu_limit,'phase_wall_limit_seconds':wall_limit,
            'original_global_cpu_limit_seconds':24*3600}
    Path(a.metrics).parent.mkdir(parents=True,exist_ok=True);Path(a.metrics).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
    raise SystemExit(p.returncode)

if __name__=='__main__':main()
